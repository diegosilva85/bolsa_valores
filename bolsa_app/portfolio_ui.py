"""Janelas da carteira e gráficos de composição em Tkinter."""
import colorsys
import hashlib
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from tkinter import BOTH, LEFT, RIGHT, X, Canvas, Frame, Label, StringVar, Toplevel, filedialog, messagebox
from tkinter import ttk

from .portfolio import CLASSES, ExcelPortfolio, Trade, positions, currency_for, symbol_for

BG, FG, MUTED = '#111827', '#e5e7eb', '#94a3b8'
CLASS_MAP = {'stock': 'Ações', 'unit': 'Ações', 'fii': 'FIIs', 'etf': 'ETFs',
             'bdr': 'BDRs', 'fi-agro': 'FIagro', 'fi-infra': 'FI-Infra',
             'crypto': 'Criptomoedas', 'us-stock': 'Ações EUA', 'us-etf': 'ETFs EUA', 'forex': 'Moedas'}


def money(value, currency='BRL'):
    if value is None:
        return '—'
    digits = 6 if value != 0 and abs(value) < 1 else 2
    return ('US$ ' if currency == 'USD' else 'R$ ') + f'{value:,.{digits}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def percent(value, total):
    return '—' if value is None or total is None or total <= 0 else f'{value / total * 100:.2f}%'.replace('.', ',')


def color(key):
    hue = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xffffffff
    return '#%02x%02x%02x' % tuple(round(c * 255) for c in colorsys.hsv_to_rgb(hue, .63, .91))


class Pie(Canvas):
    def __init__(self, parent, command=None):
        super().__init__(parent, bg=BG, highlightthickness=0, width=310, height=230)
        self.items, self.command = [], command
        self.note = 'Sem posições'
        self.bind('<Configure>', lambda _: self.draw())

    def set(self, items, note='Sem posições'):
        self.items, self.note = items, note
        self.draw()

    def draw(self):
        self.delete('all')
        total = sum((v for _, v in self.items), Decimal(0))
        w, h = self.winfo_width(), self.winfo_height()
        if total <= 0:
            self.create_text(w / 2, h / 2, text=self.note, fill=MUTED, width=max(w - 20, 100))
            return
        size = max(10, min(w - 30, h - 30))
        left, top = (w - size) / 2, (h - size) / 2
        start = 90
        for key, value in self.items:
            extent = float(value / total * 360)
            if extent <= 0:
                continue
            if extent >= 359.999999:
                item = self.create_oval(left, top, left+size, top+size, fill=color(key), outline=BG)
            else:
                item = self.create_arc(left, top, left+size, top+size, start=start, extent=extent,
                                       fill=color(key), outline=BG, width=2)
            if self.command:
                self.tag_bind(item, '<Button-1>', lambda _, k=key: self.command(k))
            start += extent


def table(parent, columns, height=8):
    style = ttk.Style(parent)
    style.configure('Portfolio.Treeview', background=BG, fieldbackground=BG, foreground=FG, rowheight=24)
    style.configure('Portfolio.Treeview.Heading', background='#25354c', foreground=FG, padding=6)
    style.map('Portfolio.Treeview', background=[('selected', '#31445e')], foreground=[('selected', '#ffffff')])
    frame = Frame(parent, bg=BG)
    frame.pack(fill=BOTH, expand=True, pady=5)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show='headings', height=height, style='Portfolio.Treeview',
                        selectmode='browse')
    for key, label, width in columns:
        tree.heading(key, text=label)
        tree.column(key, width=width, minwidth=65, anchor='w' if key in ('name', 'ticker', 'kind', 'day', 'stamp') else 'e')
    vertical = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
    horizontal = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
    vertical.pack(side=RIGHT, fill='y')
    horizontal.pack(side='bottom', fill=X)
    tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    tree.pack(fill=BOTH, expand=True)
    return tree


def choose_portfolio(app, create):
    options = dict(parent=app.root, filetypes=[('Carteira Excel', '*.xlsx')])
    path = (filedialog.asksaveasfilename(title='Criar carteira', defaultextension='.xlsx',
                                       initialfile='Minha carteira.xlsx', **options) if create else
            filedialog.askopenfilename(title='Abrir carteira', **options))
    if not path:
        return
    path = str(Path(path).resolve())
    if not hasattr(app, 'portfolios'):
        app.portfolios = {}
    if path in app.portfolios and app.portfolios[path].window.winfo_exists():
        app.portfolios[path].window.lift()
        return
    try:
        store = ExcelPortfolio(path)
        if create:
            if store.path.exists():
                raise ValueError('Escolha um novo nome para criar a carteira; arquivos existentes devem ser abertos.')
            store.write([])
        else:
            store.load()
        app.portfolios[path] = PortfolioWindow(app, store)
    except Exception as exc:
        messagebox.showerror('Carteira', str(exc), parent=app.root)


class PortfolioWindow:
    def __init__(self, app, store):
        self.app, self.store = app, store
        self.window = Toplevel(app.root)
        self.window.title('Carteira — ' + store.path.stem)
        self.window.geometry('1100x850')
        self.window.minsize(850, 640)
        self.window.configure(bg=BG)
        self.alive, self.version = True, 0
        self.quotes, self.errors, self.details = {}, {}, []
        self.holdings = positions(store.trades, store.events)
        self.fx = None
        self.display_currency = 'BRL'
        self.native_prices = True
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        bar = Frame(self.window, bg=BG, padx=12, pady=10)
        bar.pack(fill=X)
        for label, command in [('Lançar compra/venda', self.trade_dialog),
                               ('Atualizar cotações', self.refresh), ('Recarregar Excel', self.reload)]:
            ttk.Button(bar, text=label, command=command).pack(side=LEFT, padx=4)
        total_row = Frame(self.window, bg=BG)
        total_row.pack(fill=X)
        self.total = Label(total_row, bg=BG, fg=FG, font=('Sans', 22, 'bold'))
        self.total.pack(anchor='w', padx=16)
        self.total.pack(side=LEFT)
        self.currency_button = ttk.Button(total_row, text='Total em US$', command=self.toggle_currency)
        self.currency_button.pack(side=LEFT)
        self.price_button = ttk.Button(bar, text='Cotações em R$', command=self.toggle_prices)
        self.price_button.pack(side=LEFT, padx=4)
        self.status = Label(self.window, bg=BG, fg=MUTED, wraplength=1000, anchor='w')
        self.status.pack(fill=X, padx=16)
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=BOTH, expand=True, padx=12, pady=8)
        summary = Frame(notebook, bg=BG)
        notebook.add(summary, text='Composição')
        charts = Frame(summary, bg=BG)
        charts.pack(fill=X)
        self.class_pie, self.asset_pie = None, None
        for title, attribute, command in [('Por classe · clique para detalhar', 'class_pie', self.open_class),
                                           ('Por ativo · cores na lista abaixo', 'asset_pie', None)]:
            group = Frame(charts, bg=BG)
            group.pack(side=LEFT, fill=BOTH, expand=True)
            Label(group, text=title, bg=BG, fg=FG).pack()
            pie = Pie(group, command)
            pie.pack(fill=BOTH, expand=True)
            setattr(self, attribute, pie)
        self.classes = table(summary, [('kind','Classe (clique para abrir)',180), ('value','Valor atual',160),
                                       ('pct','% da carteira',120)], height=4)
        self.classes.bind('<<TreeviewSelect>>', self.class_selected)
        self.assets = table(summary, [('ticker','Ativo / cor',110), ('kind','Classe',100), ('qty','Quantidade',100),
                                      ('price','Cotação',120), ('value','Valor atual',140),
                                      ('pct','% da carteira',110), ('stamp','Data da cotação',180)], height=7)
        self.bind_asset_info(self.assets)
        operations = Frame(notebook, bg=BG)
        notebook.add(operations, text='Operações registradas')
        from .events_ui import EventsPanel
        self.events_panel = EventsPanel(notebook, self)
        self.trades_tree = table(operations, [('day','Data',100), ('ticker','Ativo',100), ('kind','Classe',100),
                                            ('side','Operação',90), ('qty','Quantidade',110), ('price','Preço unitário',130),
                                            ('value','Valor da operação',150)], height=15)
        ttk.Button(operations, text='Excluir operação selecionada', command=self.delete_trade).pack(pady=6)
        Label(self.window, text=str(store.path), bg=BG, fg=MUTED, wraplength=1000).pack(fill=X, pady=5)
        self.render_trades()
        self.refresh()

    def close(self):
        self.alive = False
        self.version += 1
        for dialog, *_ in self.details:
            if dialog.winfo_exists():
                dialog.destroy()
        self.window.destroy()

    def reload(self):
        try:
            self.store.load()
            self.holdings = positions(self.store.trades, self.store.events)
            self.render_trades()
            self.refresh()
        except Exception as exc:
            messagebox.showerror('Recarregar Excel', str(exc), parent=self.window)

    def refresh(self):
        self.version += 1
        version = self.version
        self.quotes, self.errors = {}, {}
        self.pending = set(self.holdings)
        self.fx = None
        if any(currency_for(p.kind) == 'USD' for p in self.holdings.values()) or self.display_currency == 'USD':
            self.pending.add('USD/BRL')
            self.app.submit(lambda result, error: self.received_fx(version, result, error), self.app.provider.usd_brl)
        self.render()
        for ticker, p in self.holdings.items():
            self.app.submit(lambda result, error, key=ticker: self.received(version, key, result, error),
                            self.app.provider.history, 'Hoje', symbol_for(ticker, p.kind), p.name)

    def received_fx(self, version, result, error):
        if not self.alive or version != self.version:
            return
        self.pending.discard('USD/BRL')
        if error:
            self.errors['USD/BRL'] = str(error)
        else:
            self.fx = (Decimal(str(result[0])), result[1])
        self.render()

    def toggle_currency(self):
        self.display_currency = 'USD' if self.display_currency == 'BRL' else 'BRL'
        self.currency_button.config(text='Total em R$' if self.display_currency == 'USD' else 'Total em US$')
        if self.fx is None and self.holdings:
            version = self.version
            self.pending.add('USD/BRL')
            self.app.submit(lambda r, e: self.received_fx(version, r, e), self.app.provider.usd_brl)
        self.render()

    def toggle_prices(self):
        self.native_prices = not self.native_prices
        self.price_button.config(text='Cotações em R$' if self.native_prices else 'Cotações na moeda original')
        self.render()

    def convert(self, value, source, target):
        if value is None or source == target:
            return value
        if self.fx is None:
            return None
        return value * self.fx[0] if target == 'BRL' else value / self.fx[0]

    def received(self, version, ticker, result, error):
        if not self.alive or self.version != version:
            return
        self.pending.discard(ticker)
        if error:
            self.errors[ticker] = str(error)
        else:
            value = Decimal(str(result.last_price))
            if not value.is_finite() or value <= 0:
                self.errors[ticker] = 'Preço inválido'
            else:
                self.quotes[ticker] = (value, result.timestamps[-1])
        self.render()

    def values(self, holdings):
        return {key: self.convert(p.quantity * self.quotes[key][0], currency_for(p.kind), self.display_currency) if key in self.quotes else None
                for key, p in holdings.items()}

    def render(self):
        values = self.values(self.holdings)
        complete = all(v is not None for v in values.values())
        total = sum(values.values(), Decimal(0)) if complete else None
        self.total.config(text='Valor atual: ' + (money(total, self.display_currency) if complete else 'incompleto'))
        if self.pending:
            text = f'Consultando {len(self.pending)} ativo(s)…'
        elif self.errors:
            text = 'Sem cotação: ' + ', '.join(self.errors) + '. Total e percentuais indisponíveis; tente atualizar.'
        elif not self.holdings:
            text = 'Carteira sem posições. Registre sua primeira compra.'
        else:
            text = 'Quantidade em posição × última cotação. Percentuais sobre o valor atual; não incluem saldo em caixa.'
        if self.fx:
            text += f' • USD/BRL {self.fx[0]:.4f} de {self.fx[1]:%d/%m/%Y}'
        self.status.config(text=text)
        grouped = defaultdict(list)
        for key, p in self.holdings.items():
            grouped[p.kind].append(values[key])
        self.classes.delete(*self.classes.get_children())
        class_values = []
        for kind, entries in sorted(grouped.items()):
            value = sum(entries, Decimal(0)) if all(v is not None for v in entries) else None
            self.classes.tag_configure(kind, foreground=color(kind))
            self.classes.insert('', 'end', iid=kind, values=('● ' + kind, money(value, self.display_currency), percent(value, total)), tags=(kind,))
            if value is not None:
                class_values.append((kind, value))
        unavailable = 'Aguardando todas as cotações para calcular a composição.' if not complete else 'Sem posições'
        self.class_pie.set(class_values if complete else [], unavailable)
        self.asset_pie.set(list(values.items()) if complete else [], unavailable)
        self.fill_assets(self.assets, self.holdings, total)
        self.details = [entry for entry in self.details if entry[0].winfo_exists()]
        for entry in self.details:
            self.render_detail(entry)

    def fill_assets(self, tree, holdings, total):
        tree.delete(*tree.get_children())
        values = self.values(holdings)
        for ticker, p in sorted(holdings.items()):
            quote, stamp = self.quotes.get(ticker, (None, None))
            quote_currency = currency_for(p.kind) if self.native_prices else 'BRL'
            quote = self.convert(quote, currency_for(p.kind), quote_currency)
            tree.tag_configure(ticker, foreground=color(ticker))
            tree.insert('', 'end', iid=ticker, values=('● '+ticker, p.kind, str(p.quantity), money(quote, quote_currency), money(values[ticker], self.display_currency),
                                         percent(values[ticker], total), stamp.strftime('%d/%m/%Y %H:%M') if stamp else 'Sem cotação'),
                        tags=(ticker,))

    def bind_asset_info(self, tree):
        from tkinter import Menu
        menu = Menu(tree, tearoff=False)
        def info():
            selected = tree.selection()
            if not selected or selected[0] not in self.holdings:
                return
            from .catalog import Asset
            p = self.holdings[selected[0]]
            kind = next((k for k, value in CLASS_MAP.items() if value == p.kind), 'stock')
            self.app.show_info(Asset(p.ticker, p.name, kind))
        menu.add_command(label='Informações e indicadores', command=info)
        def clicked(event):
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                try:
                    menu.tk_popup(event.x_root, event.y_root)
                finally:
                    menu.grab_release()
        tree.bind('<ButtonRelease-1>', clicked)
        tree.bind('<Button-3>', clicked)
        tree.bind('<Return>', lambda _: info())

    def class_selected(self, _event=None):
        selection = self.classes.selection()
        if selection:
            kind = selection[0]
            self.classes.selection_remove(kind)
            self.open_class(kind)

    def open_class(self, kind):
        for entry in self.details:
            if entry[1] == kind and entry[0].winfo_exists():
                entry[0].lift()
                return
        dialog = Toplevel(self.window)
        dialog.title('Composição — ' + kind)
        dialog.geometry('1000x660')
        dialog.configure(bg=BG)
        title = Label(dialog, bg=BG, fg=FG, font=('Sans', 19, 'bold'))
        title.pack(pady=12)
        pie = Pie(dialog)
        pie.pack(fill=BOTH, expand=True)
        Label(dialog, text='Percentuais dentro desta classe • mesmas cores por ativo em toda a carteira', bg=BG, fg=MUTED).pack()
        tree = table(dialog, [('ticker','Ativo / cor',110), ('kind','Classe',100), ('qty','Quantidade',100),
                              ('price','Cotação',120), ('value','Valor atual',140), ('pct','% da classe',110),
                              ('stamp','Data da cotação',180)])
        self.bind_asset_info(tree)
        entry = (dialog, kind, title, pie, tree)
        self.details.append(entry)
        self.render_detail(entry)

    def render_detail(self, entry):
        _, kind, title, pie, tree = entry
        subset = {key: p for key, p in self.holdings.items() if p.kind == kind}
        values = self.values(subset)
        complete = all(v is not None for v in values.values())
        total = sum(values.values(), Decimal(0)) if complete else None
        title.config(text=kind + ' · ' + (money(total, self.display_currency) if complete else 'Cotação incompleta'))
        pie.set(list(values.items()) if complete else [], 'Sem posições' if complete else 'Aguardando cotações')
        self.fill_assets(tree, subset, total)

    def render_trades(self):
        self.events_panel.render()
        self.trades_tree.delete(*self.trades_tree.get_children())
        for t in self.store.trades:
            self.trades_tree.insert('', 'end', iid=t.id, values=(t.day.strftime('%d/%m/%Y'), t.ticker, t.kind,
                                    t.side, str(t.quantity), money(t.price, t.currency), money(t.quantity*t.price, t.currency)))

    def delete_trade(self):
        selected = self.trades_tree.selection()
        if not selected:
            return
        if not messagebox.askyesno('Excluir operação', 'Excluir o lançamento selecionado? A cópia anterior ficará no arquivo .backup.xlsx.', parent=self.window):
            return
        try:
            self.store.write([t for t in self.store.trades if t.id != selected[0]])
            self.holdings = positions(self.store.trades, self.store.events)
            self.render_trades()
            self.refresh()
        except Exception as exc:
            messagebox.showerror('Operação não excluída', str(exc), parent=self.window)

    def trade_dialog(self):
        dialog = Toplevel(self.window)
        dialog.title('Registrar compra ou venda')
        dialog.geometry('530x460')
        fields = {}
        defaults = {'Ticker': '', 'Nome': '', 'Classe': 'Ações', 'Operação': 'Compra',
                    'Data (DD/MM/AAAA)': date.today().strftime('%d/%m/%Y'), 'Quantidade': '', 'Preço unitário': ''}
        for row, (name, value) in enumerate(defaults.items()):
            Label(dialog, text=name).grid(row=row, column=0, sticky='w', padx=12, pady=10)
            fields[name] = StringVar(value=value)
            if name in ('Classe', 'Operação', 'Ticker'):
                choices = CLASSES if name == 'Classe' else ('Compra','Venda') if name == 'Operação' else []
                widget = ttk.Combobox(dialog, textvariable=fields[name], values=choices,
                                      state='normal' if name == 'Ticker' else 'readonly', width=30)
            else:
                widget = ttk.Entry(dialog, textvariable=fields[name], width=32)
            widget.grid(row=row, column=1, sticky='ew', padx=12)
            if name == 'Ticker':
                ticker_box = widget
        def suggest(*_):
            query = fields['Ticker'].get().strip().upper()
            matches = self.app.catalog.search(query)
            ticker_box['values'] = [a.ticker for a in matches if not a.ticker.startswith('^')]
            exact = next((a for a in self.app.catalog.assets if a.ticker in (query, query + '-USD', query + '/BRL')), None)
            if exact:
                fields['Nome'].set(exact.name)
                fields['Classe'].set(CLASS_MAP.get(exact.kind, 'Outros'))
        fields['Ticker'].trace_add('write', suggest)
        price_currency = StringVar()
        def update_currency(*_):
            if fields['Classe'].get() == 'Moedas':
                price_currency.set('Quantidade em moeda estrangeira; preço em R$ por unidade. Ex.: 100 USD a R$ 5,00 cada.')
                return
            price_currency.set('Preço por unidade em ' + ('US$ (dólares)' if currency_for(fields['Classe'].get()) == 'USD' else 'R$ (reais)') + '. Quantidades fracionárias são aceitas.')
        fields['Classe'].trace_add('write', update_currency)
        update_currency()
        Label(dialog, textvariable=price_currency, wraplength=490).grid(row=7,column=0,columnspan=2,pady=10)
        def save():
            try:
                t = Trade.make(fields['Data (DD/MM/AAAA)'].get(), fields['Ticker'].get(), fields['Nome'].get(),
                               fields['Classe'].get(), fields['Operação'].get(), fields['Quantidade'].get(),
                               fields['Preço unitário'].get())
                self.store.add(t)
                self.holdings = positions(self.store.trades, self.store.events)
                self.render_trades()
                self.refresh()
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror('Não foi possível salvar', str(exc), parent=dialog)
        ttk.Button(dialog, text='Salvar operação no Excel', command=save).grid(row=8,column=0,columnspan=2,pady=12)
        dialog.columnconfigure(1, weight=1)
