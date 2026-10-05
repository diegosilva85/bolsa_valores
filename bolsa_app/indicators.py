"""Indicadores Yahoo Finance; grupos inspirados no Status Invest."""
from datetime import datetime, timezone
import math
from time import monotonic
import yfinance as yf


def numeric(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def ratio(a, b):
    a, b = numeric(a), numeric(b)
    return a / b if a is not None and b is not None and b != 0 else None


def rows_from_info(info, kind):
    def field(key):
        return numeric(info.get(key))
    def row(group, name, key, fmt, note):
        return (group, name, field(key), fmt, note)
    currency = info.get('currency') or 'moeda não informada'
    if kind in ('forex', 'crypto', 'Índice'):
        return []
    valuation = [
        row('Valuation', 'P/L (12 meses)', 'trailingPE', 'multiple', 'Preço / lucro por ação dos últimos 12 meses.'),
        row('Valuation', 'P/VP', 'priceToBook', 'multiple', 'Preço / valor patrimonial por ação.'),
        row('Valuation', 'Dividend yield (12 meses)', 'trailingAnnualDividendYield', 'percent', 'Dividendos anuais passados / preço; não é projeção.'),
        row('Valuation', 'LPA (12 meses)', 'trailingEps', currency, 'Lucro por ação reportado pelo provedor.'),
        row('Valuation', 'VPA', 'bookValue', currency, 'Valor patrimonial por ação reportado pelo provedor.'),
    ]
    if kind in ('fii', 'etf', 'us-etf', 'fund', 'fi-infra', 'fi-agro', 'fip', 'fidc'):
        return [r for r in valuation if r[1] in ('P/VP', 'Dividend yield (12 meses)')] + [
            row('Valuation', 'Valor patrimonial por cota (NAV)', 'navPrice', currency, 'NAV reportado; pode não estar disponível para fundos B3.')]
    debt, cash = field('totalDebt'), field('totalCash')
    net = debt - cash if debt is not None and cash is not None else None
    return valuation + [
        row('Valuation', 'EV/EBITDA', 'enterpriseToEbitda', 'multiple', 'Valor da firma / EBITDA; múltiplo fornecido pelo Yahoo.'),
        row('Valuation', 'P/Receita (12 meses)', 'priceToSalesTrailing12Months', 'multiple', 'Valor de mercado / receita dos últimos 12 meses.'),
        row('Valuation', 'Valor de mercado', 'marketCap', currency, 'Valor de mercado na moeda de cotação.'),
        ('Endividamento', 'Dívida líquida / EBITDA', ratio(net, field('ebitda')), 'multiple',
         '(Dívida total − caixa total) / EBITDA; calculado com dados do provedor, pode diferir da dívida ajustada.'),
        row('Endividamento', 'Dívida total / patrimônio', 'debtToEquity', 'percent_points', 'Percentual reportado pelo Yahoo; dívida total / patrimônio.'),
        row('Endividamento', 'Liquidez corrente', 'currentRatio', 'multiple', 'Ativo circulante / passivo circulante.'),
        row('Endividamento', 'Liquidez seca (quick ratio)', 'quickRatio', 'multiple', 'Índice de liquidez sem estoques reportado pelo provedor.'),
        row('Eficiência', 'Margem bruta', 'grossMargins', 'percent', 'Lucro bruto / receita.'),
        row('Eficiência', 'Margem EBITDA', 'ebitdaMargins', 'percent', 'EBITDA / receita.'),
        row('Eficiência', 'Margem operacional', 'operatingMargins', 'percent', 'Lucro operacional / receita.'),
        row('Eficiência', 'Margem líquida', 'profitMargins', 'percent', 'Lucro líquido / receita.'),
        row('Rentabilidade', 'ROE', 'returnOnEquity', 'percent', 'Retorno sobre o patrimônio líquido, conforme o provedor.'),
        row('Rentabilidade', 'ROA', 'returnOnAssets', 'percent', 'Retorno sobre os ativos, conforme o provedor.'),
    ]


class IndicatorsProvider:
    def __init__(self):
        self.cache = {}

    def get(self, asset):
        if asset.kind in ('forex', 'crypto', 'Índice'):
            return {'rows': [], 'note': 'Indicadores empresariais de valuation, dívida e eficiência não se aplicam a moedas, criptomoedas ou índices.', 'time': datetime.now()}
        cached = self.cache.get(asset.symbol)
        if cached and monotonic() - cached[0] < 300:
            return cached[1]
        info = yf.Ticker(asset.symbol).get_info()
        if not info or len(info) < 3:
            raise ValueError('O provedor não retornou indicadores para este ativo.')
        date = info.get('mostRecentQuarter')
        period = datetime.fromtimestamp(date, timezone.utc).strftime('%d/%m/%Y') if numeric(date) else 'não informado'
        data = {'rows': rows_from_info(info, asset.kind), 'time': datetime.now(),
                'note': f'Último trimestre informado: {period}. Fonte: Yahoo Finance. Períodos e metodologias podem diferir do Status Invest. — significa dado indisponível; não é zero.'}
        self.cache[asset.symbol] = (monotonic(), data)
        return data


def formatted(value, fmt):
    if value is None:
        return '—'
    if fmt == 'percent':
        value *= 100
    suffix = '%' if fmt in ('percent', 'percent_points') else 'x' if fmt == 'multiple' else ' ' + fmt
    return f'{value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') + suffix


def open_indicators(app, asset):
    from tkinter import Toplevel, Label, Frame, BOTH, X, StringVar
    from tkinter import ttk
    from .design import BG, SURFACE, FG, MUTED, ACCENT, RoundedFrame, ScrollArea
    from .logos import badge
    dialog = Toplevel(app.root)
    dialog.title('Informações — ' + asset.ticker)
    dialog.geometry('1080x760')
    dialog.minsize(680, 480)
    dialog.configure(bg=BG)
    heading = Frame(dialog, bg=BG)
    heading.pack(fill=X, padx=20, pady=(20, 8))
    badge(heading, app, asset, size=48, background=BG).pack(side='left', padx=(0, 12))
    Label(heading, text=f'{asset.ticker} · {asset.name}', bg=BG, fg=FG, font=('Sans', 17, 'bold')).pack(side='left')
    status = StringVar(value='Consultando indicadores…')
    Label(dialog, textvariable=status, wraplength=950, justify='left').pack(fill=X, padx=14, pady=8)
    tabs = ttk.Notebook(dialog)
    tabs.pack(fill=BOTH, expand=True, padx=12, pady=10)
    def loaded(result, error):
        if not dialog.winfo_exists():
            return
        if error:
            status.set('Não foi possível consultar: ' + str(error))
            return
        status.set(result['note'] + f"\nConsulta: {result['time']:%d/%m/%Y %H:%M} • atualização em cache por até 5 minutos.")
        for group in dict.fromkeys(r[0] for r in result['rows']):
            area = ScrollArea(tabs)
            symbols = {'Valuation': '◆', 'Endividamento': '⚖', 'Eficiência': '◴', 'Rentabilidade': '↗'}
            tabs.add(area, text=symbols[group] + '  ' + group)
            cards = []
            for category, name, value, fmt, note in result['rows']:
                if category == group:
                    card = RoundedFrame(area.body, bg=SURFACE, padx=18, pady=16)
                    Label(card, text=symbols[group] + '  ' + name, bg=SURFACE, fg=MUTED,
                          font=('Sans', 10, 'bold'), anchor='w', wraplength=260).pack(fill=X)
                    Label(card, text=formatted(value, fmt), bg=SURFACE, fg=ACCENT if value is not None else MUTED,
                          font=('Sans', 21, 'bold'), anchor='w').pack(fill=X, pady=(12, 8))
                    description = Label(card, text=note, bg=SURFACE, fg=MUTED, justify='left', anchor='nw', wraplength=260)
                    description.pack(fill=X)
                    cards.append((card, description))
            def layout(event, area=area, cards=cards):
                count = max(1, min(3, event.width // 300))
                for col in range(3):
                    area.body.columnconfigure(col, weight=1 if col < count else 0, uniform='cards' if col < count else '')
                for index, (card, description) in enumerate(cards):
                    card.grid(row=index // count, column=index % count, sticky='nsew', padx=7, pady=7)
                    description.configure(wraplength=max(180, event.width // count - 54))
            area.canvas.bind('<Configure>', layout, add='+')
    app.submit(loaded, app.indicators.get, asset)
