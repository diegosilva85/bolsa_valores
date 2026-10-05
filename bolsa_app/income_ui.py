"""Consulta anual de proventos e cache na própria carteira Excel."""
from datetime import date
from decimal import Decimal
from threading import Event
from tkinter import Canvas, Frame, Label, StringVar, messagebox, simpledialog, ttk
from .design import BG, SURFACE, FG, MUTED, ACCENT
from .income import BrapiIncomeProvider, TYPES, generate_income, history_key, monthly_totals

MONTHS = ('Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto',
          'Setembro', 'Outubro', 'Novembro', 'Dezembro')


class IncomePanel:
    def __init__(self, notebook, owner):
        from .portfolio_ui import table
        self.owner = owner
        self.busy = False
        self.cancel = Event()
        self.provider = BrapiIncomeProvider()
        self.frame = Frame(notebook, bg=BG)
        notebook.add(self.frame, text='◈ Proventos recebidos')
        bar = Frame(self.frame, bg=BG)
        bar.pack(fill='x', padx=10, pady=10)
        Label(bar, text='Ano do pagamento', bg=BG, fg=MUTED).pack(side='left')
        self.year = StringVar(value=str(date.today().year))
        self.selector = ttk.Combobox(bar, textvariable=self.year, state='readonly', width=7)
        self.selector.pack(side='left', padx=8)
        self.selector.bind('<<ComboboxSelected>>', lambda _: self.load_year())
        self.regenerate = ttk.Button(bar, text='↻ Gerar novamente', command=lambda: self.load_year(force=True))
        self.regenerate.pack(side='left')
        ttk.Button(bar, text='Acesso brapi', command=self.configure).pack(side='right')
        ttk.Button(bar, text='Avisos da consulta', command=self.show_warnings).pack(side='right', padx=6)
        self.status = StringVar(value='Selecione um ano para consultar.')
        Label(self.frame, textvariable=self.status, bg=BG, fg=ACCENT, wraplength=980, justify='left').pack(fill='x', padx=12)
        Label(self.frame, text='Valores BRUTOS estimados pelo histórico, não créditos bancários confirmados. '
              'JCP sem desconto automático de IR. Amortizações não alteram o custo por esta aba.',
              bg=BG, fg=MUTED, wraplength=980, justify='left').pack(fill='x', padx=12, pady=5)
        self.totals = StringVar()
        Label(self.frame, textvariable=self.totals, bg=BG, fg=FG, font=('Sans', 11, 'bold'), wraplength=980).pack(fill='x', pady=5)
        tabs = ttk.Notebook(self.frame)
        tabs.pack(fill='both', expand=True, padx=10, pady=5)
        monthly, detail = Frame(tabs, bg=BG), Frame(tabs, bg=BG)
        tabs.add(monthly, text='Mês a mês')
        tabs.add(detail, text='Lançamentos e revisão')
        self.chart = Canvas(monthly, height=100, bg=SURFACE, highlightthickness=0)
        self.chart.pack(fill='x', pady=6)
        self.chart.bind('<Configure>', lambda _: self.draw())
        self.summary = table(monthly, [('month', 'Mês', 95), ('div', 'Dividendos', 120), ('jcp', 'JCP', 110),
            ('fii', 'Rendimentos FII', 140), ('amort', 'Amortizações', 130), ('other', 'Outros', 110), ('total', 'Total bruto', 140)], height=6)
        self.details = table(detail, [('pay', 'Pagamento', 100), ('ticker', 'Ativo', 100), ('type', 'Tipo', 130),
            ('record', 'Data com', 100), ('qty', 'Quantidade', 100), ('unit', 'Por unidade', 115),
            ('gross', 'Bruto', 115), ('state', 'Situação', 145), ('note', 'Observação', 400)], height=8)
        self.last_warnings = ''
        self.refresh()
        initial_job = self.frame.after(200, self.load_year)
        def destroyed(event):
            if event.widget == self.frame:
                self.cancel.set()
                self.frame.after_cancel(initial_job)
        self.frame.bind('<Destroy>', destroyed)

    def configure(self):
        token = simpledialog.askstring('Acesso brapi', 'Token brapi (fica só nesta sessão; opcionalmente use BRAPI_TOKEN no ambiente).\n'
            'Ações: acesso a includeRaw/rawRate; FIIs: acesso ao histórico de rendimentos.\n'
            'Consulte seu plano em brapi.dev. Nenhuma contratação é feita pelo app.', show='*', parent=self.owner.window)
        if token is not None:
            self.provider.token = token.strip()

    def show_warnings(self):
        period = self.owner.store.income_periods.get(int(self.year.get()), {})
        messagebox.showinfo('Avisos dos proventos', self.last_warnings or period.get('warnings') or
            'Sem erros relatados pela consulta. A ausência de eventos não garante cobertura histórica completa. '
            'Conferir datas, valores e créditos no extrato. Dados de EUA não estão cobertos por esta fonte.', parent=self.owner.window)

    def refresh(self):
        store = self.owner.store
        first = min([t.day.year for t in store.trades] + [date.today().year])
        years = sorted(set(range(first, date.today().year + 1)) | set(store.income_periods), reverse=True)
        self.selector.configure(values=years)
        self.render()

    def load_year(self, force=False):
        if not self.owner.alive or self.busy:
            return
        year = int(self.year.get())
        store = self.owner.store
        self.last_warnings = ''
        if year in store.income_periods and not force:
            self.render()
            return
        if force and year in store.income_periods and not messagebox.askyesno('Gerar novamente',
            f'Consultar {year} novamente e substituir os lançamentos automáticos desse ano? '
            'A versão anterior ficará no backup do Excel.', parent=self.owner.window):
            return
        self.busy = True
        self.regenerate.state(['disabled'])
        self.selector.state(['disabled'])
        self.status.set(f'Consultando proventos de {year} e reconstruindo posições nas datas de direito…')
        trades, events = list(store.trades), list(store.events)
        key, fingerprint = history_key(trades, events), store.fingerprint
        provider = BrapiIncomeProvider(self.provider.token)
        def loaded(result, error):
            if not self.owner.alive:
                return
            self.busy = False
            self.regenerate.state(['!disabled'])
            self.selector.state(['!disabled', 'readonly'])
            try:
                if error:
                    raise ValueError(str(error))
                if key != history_key(store.trades, store.events) or fingerprint != store.fingerprint:
                    raise ValueError('Carteira alterada durante a consulta. Gere novamente com o histórico atual.')
                rows, period, successful = result
                self.last_warnings = period['warnings']
                store.save_income_year(result)
                self.render()
            except Exception as exc:
                self.status.set(str(exc))
        self.owner.app.submit(loaded, generate_income, trades, events, year, provider, None, self.cancel)

    def render(self):
        from .portfolio_ui import money
        year = int(self.year.get())
        store = self.owner.store
        period = store.income_periods.get(year)
        rows = [r for r in store.income if r.pay_day.year == year]
        self.months = monthly_totals(rows, year)
        self.summary.delete(*self.summary.get_children())
        for month, entries in self.months.items():
            self.summary.insert('', 'end', values=(MONTHS[month-1], *[money(entries[k]) for k in TYPES], money(sum(entries.values()))))
        self.details.delete(*self.details.get_children())
        for r in sorted(rows, key=lambda r: (r.pay_day, r.ticker, r.type)):
            state = 'Revisar' if r.review else 'Previsto' if r.pay_day > date.today() else 'Pago (estimado)'
            self.details.insert('', 'end', values=(r.pay_day.strftime('%d/%m/%Y'), r.ticker, r.type,
                r.record_day.strftime('%d/%m/%Y'), str(r.quantity), money(r.unit, r.currency), money(r.gross, r.currency), state, r.note))
        paid = sum((sum(v.values()) for v in self.months.values()), Decimal(0))
        scheduled = sum((r.gross for r in rows if r.pay_day > date.today() and not r.review), Decimal(0))
        review = sum((r.gross for r in rows if r.review), Decimal(0))
        self.totals.set(f'Bruto estimado até hoje: {money(paid)}   •   Previsto: {money(scheduled)}   •   A revisar (fora do total): {money(review)}')
        if not self.busy:
            if period:
                stale = period['history'] != history_key(store.trades, store.events)
                self.status.set(('HISTÓRICO ALTERADO — gere novamente. ' if stale else 'Carregado do Excel. ') +
                    f"{period['status']} em {period['generated'].replace('T', ' ')}. " +
                    ('Há avisos; os totais podem estar incompletos.' if period['warnings'] else 'Use Gerar novamente para buscar revisões.'))
            else:
                self.status.set('Ano ainda não consultado. Ao selecionar, o app busca e salva no Excel.')
        self.draw()

    def draw(self):
        self.chart.delete('all')
        if not hasattr(self, 'months'):
            return
        width, height = self.chart.winfo_width(), self.chart.winfo_height()
        peak = max([sum(v.values()) for v in self.months.values()] + [Decimal(1)])
        step = max(1, (width - 30) / 12)
        for index, entries in enumerate(self.months.values()):
            x = 15 + index * step
            top = height - 25 - float(sum(entries.values()) / peak) * (height - 40)
            self.chart.create_rectangle(x+6, top, x+step-6, height-25, fill=ACCENT, outline='')
            self.chart.create_text(x+step/2, height-12, text=MONTHS[index][:3], fill=MUTED, font=('Sans', 9))
