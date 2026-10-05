"""Registro manual e prévia de eventos corporativos."""
from datetime import date
from tkinter import Frame, Label, StringVar, Toplevel, messagebox, ttk
from .portfolio import CLASSES, EVENT_TYPES, CorporateEvent, positions, currency_for


class EventsPanel:
    def __init__(self, notebook, owner):
        from .portfolio_ui import table
        self.owner = owner
        self.frame = Frame(notebook)
        notebook.add(self.frame, text='Eventos e custo ajustado')
        bar = Frame(self.frame)
        bar.pack(fill='x')
        ttk.Button(bar, text='Registrar evento corporativo', command=self.dialog).pack(side='left', padx=8, pady=8)
        ttk.Button(bar, text='Excluir evento selecionado', command=self.delete).pack(side='left')
        Label(self.frame, text='Lançamento manual, sem B3. Eventos no mesmo dia seguem a ordem de registro, antes/depois das operações.', wraplength=800).pack()
        self.tree = table(self.frame, [('day', 'Data', 100), ('type', 'Evento', 160), ('source', 'Origem', 100), ('target', 'Destino', 100), ('factor', 'Fator', 80), ('timing', 'Momento', 80)], height=7)
        Label(self.frame, text='Posição atual recalculada · custos na moeda original · frações preservadas').pack()
        self.costs = table(self.frame, [('ticker', 'Ativo', 100), ('name', 'Nome', 200), ('qty', 'Quantidade', 120), ('cost', 'Custo total', 140), ('avg', 'Custo médio', 140)], height=7)
        Label(self.frame, text='Liquidações: dinheiro histórico (não é saldo disponível); frações a conferir no extrato, fora da posição negociável.').pack()
        self.settlements = table(self.frame, [('source', 'Origem', 90), ('target', 'Destino', 90), ('old', 'Custo encerrado', 130), ('new', 'Custo recebido', 130), ('cash', 'Dinheiro líquido', 130), ('fraction', 'Diferença fracionária', 170)], height=4)

    def render(self):
        from .portfolio_ui import money
        self.tree.delete(*self.tree.get_children())
        for e in self.owner.store.events:
            self.tree.insert('', 'end', iid=e.id, values=(e.day.strftime('%d/%m/%Y'), e.type, e.source, e.target, str(e.factor), e.timing))
        self.costs.delete(*self.costs.get_children())
        settlements = []
        for p in positions(self.owner.store.trades, self.owner.store.events, settlements).values():
            currency = currency_for(p.kind)
            self.costs.insert('', 'end', values=(p.ticker, p.name, str(p.quantity), money(p.cost, currency), money(p.cost / p.quantity, currency)))
        self.settlements.delete(*self.settlements.get_children())
        for item in settlements:
            self.settlements.insert('', 'end', values=(item['source'], item['target'], money(item['old_cost'], item['currency']), money(item['received_cost'], item['currency']), money(item['cash'], item['currency']), str(item['fraction'])))

    def changed(self):
        self.owner.holdings = positions(self.owner.store.trades, self.owner.store.events)
        self.owner.render_trades()
        self.owner.refresh()

    def delete(self):
        selected = self.tree.selection()
        if not selected or not messagebox.askyesno('Excluir evento', 'Recalcular toda a carteira sem este evento?', parent=self.owner.window):
            return
        try:
            store = self.owner.store
            store.write(store.trades, [e for e in store.events if e.id != selected[0]])
            self.changed()
        except Exception as exc:
            messagebox.showerror('Não foi possível excluir', str(exc), parent=self.owner.window)

    def dialog(self):
        dialog = Toplevel(self.owner.window)
        dialog.title('Evento corporativo manual')
        fields = {}
        definitions = [('day', 'Data efetiva', date.today().strftime('%d/%m/%Y'), None),
                       ('type', 'Tipo', EVENT_TYPES[0], EVENT_TYPES),
                       ('source', 'Ticker de origem', '', None), ('kind', 'Classe de origem', 'Ações', CLASSES),
                       ('target', 'Ticker de destino', '', None), ('name', 'Nome de destino', '', None),
                       ('target_kind', 'Classe de destino', 'Ações', CLASSES),
                       ('factor', 'Fator (novas unidades / antigas)', '1', None),
                       ('cost_percent', '% do custo transferido na cisão', '0', None),
                       ('amount', 'Valor unitário (bonificação/amortização)', '0', None),
                       ('timing', 'Em relação às operações do dia', 'Antes', ('Antes', 'Depois')),
                       ('received_quantity', 'Liquidação: quantidade efetivamente creditada', '0', None),
                       ('received_price', 'Liquidação: custo por cota recebida (informe)', '0', None),
                       ('cash', 'Liquidação: dinheiro líquido TOTAL recebido', '0', None)]
        for row, (key, label, default, choices) in enumerate(definitions):
            Label(dialog, text=label).grid(row=row, column=0, sticky='w', padx=10, pady=3)
            fields[key] = StringVar(value=default)
            widget = ttk.Combobox(dialog, textvariable=fields[key], values=choices, state='readonly') if choices else ttk.Entry(dialog, textvariable=fields[key])
            widget.grid(row=row, column=1, padx=10, sticky='ew')
        fields['kind'].trace_add('write', lambda *_: fields['target_kind'].set(fields['kind'].get()))
        help_text = ('Split 1→10: fator 10; grupamento 10→1: 0,1. Incorporação/cisão: unidades recebidas por unidade antiga. '
                     'Bonificação de 10%: fator 0,1 e custo informado por nova unidade. Amortização: redução de custo por unidade existente. '
                     'Troca de nome: repita o ticker. Destino vazio mantém a origem. Valores na moeda do ativo. '
                     'Liquidação: informe quantidade creditada, custo do informe e dinheiro líquido total (não por cota). '
                     'A diferença fracionária fica apenas no histórico; dinheiro não entra no total dos ativos. Não calcula impostos. '
                     'Nos demais eventos, deixe os três campos de liquidação zerados.')
        Label(dialog, text=help_text, wraplength=680, justify='left').grid(row=14, column=0, columnspan=2, padx=10, pady=10)
        def save():
            try:
                event = CorporateEvent.make(**{k: v.get() for k, v in fields.items()})
                store = self.owner.store
                proposed = [*store.events, event]
                settlements = []
                holdings = positions(store.trades, proposed, settlements)
                preview = '\n'.join(f'{p.ticker}: {p.quantity} unidades; custo {p.cost} {currency_for(p.kind)}' for p in holdings.values()) or 'Sem posição aberta.'
                for item in settlements:
                    if item['id'] == event.id:
                        preview += (f"\nCusto antigo encerrado: {item['old_cost']} {item['currency']}"
                                    f"\nDinheiro líquido histórico: {item['cash']} {item['currency']}"
                                    f"\nDiferença fracionária a conferir: {item['fraction']}"
                                    '\nO custo recebido é independente do custo antigo. Não há apuração tributária.')
                if not messagebox.askyesno('Conferir posição resultante', preview + '\n\nSalvar evento e recalcular a carteira?', parent=dialog):
                    return
                store.write(store.trades, proposed)
                self.changed()
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror('Evento não salvo', str(exc), parent=dialog)
        ttk.Button(dialog, text='Conferir e salvar no Excel', command=save).grid(row=15, column=0, columnspan=2, pady=12)
