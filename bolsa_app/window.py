from __future__ import annotations

import queue
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
import json
import math
from tkinter import BOTH, LEFT, RIGHT, X, Canvas, Frame, Label, StringVar, Tk, Toplevel, messagebox
from tkinter import ttk

from .market_data import HISTORY_RANGES, MarketSnapshot, YahooFinanceProvider
from .catalog import Asset, Catalog, IBOV, DATA_DIR, save_json, search_global

BACKGROUND, CARD, GRID = "#0b1120", "#111827", "#263244"
TEXT, MUTED, BLUE = "#e5e7eb", "#94a3b8", "#38bdf8"
GREEN, RED = "#22c55e", "#ef4444"


class MarketChart(Canvas):
    def __init__(self, parent) -> None:
        super().__init__(parent, background=CARD, highlightthickness=0)
        self.snapshot: MarketSnapshot | None = None
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_snapshot(self, snapshot: MarketSnapshot) -> None:
        self.snapshot = snapshot
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if width < 140 or height < 100:
            return

        left, right, top, bottom = 76, 22, 24, 48
        plot_width, plot_height = width - left - right, height - top - bottom
        for index in range(5):
            y = top + plot_height * index / 4
            self.create_line(left, y, width - right, y, fill=GRID)

        if not self.snapshot or not self.snapshot.prices:
            self.create_text(width / 2, height / 2, text="Aguardando cotações…", fill=MUTED)
            return

        prices = self.snapshot.prices
        low, high = min(prices), max(prices)
        margin = max((high - low) * 0.08, 1.0)
        low, high = low - margin, high + margin
        price_range = high - low

        for index in range(5):
            value = high - price_range * index / 4
            y = top + plot_height * index / 4
            label = f"{value:,.4f}" if abs(value) < 10 else f"{value:,.2f}" if abs(value) < 1000 else f"{value:,.0f}"
            label = label.replace(',', 'X').replace('.', ',').replace('X', '.')
            self.create_text(left - 10, y, text=label, fill=MUTED, anchor="e", font=("Sans", 9))

        timestamps = self.snapshot.timestamps
        moments = [timestamp.timestamp() for timestamp in timestamps]
        first_moment, last_moment = moments[0], moments[-1]
        time_range = max(last_moment - first_moment, 1.0)
        points: list[float] = []
        for moment, price in zip(moments, prices):
            x = left + plot_width * (moment - first_moment) / time_range
            y = top + (high - price) / price_range * plot_height
            points.extend((x, y))
        if len(points) >= 4:
            self.create_line(*points, fill=BLUE, width=3, smooth=False)
        else:
            x, y = points
            self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=BLUE, outline=BLUE)

        for index in range(5):
            x = left + plot_width * index / 4
            tick_moment = first_moment + time_range * index / 4
            tick_time = datetime.fromtimestamp(tick_moment, tz=timestamps[0].tzinfo)
            label = self._format_time_label(tick_time, time_range)
            self.create_text(x, height - 20, text=label, fill=MUTED, font=("Sans", 9))

    @staticmethod
    def _format_time_label(timestamp: datetime, span_seconds: float) -> str:
        if span_seconds <= 2 * 86_400:
            return timestamp.strftime("%H:%M")
        if span_seconds <= 45 * 86_400:
            return timestamp.strftime("%d/%m")
        if span_seconds <= 550 * 86_400:
            return timestamp.strftime("%b/%y").lower()
        return timestamp.strftime("%m/%Y")



class QuoteCard(Frame):
    def __init__(self, parent, app, asset, period="Hoje", removable=False):
        super().__init__(parent, background=CARD, padx=10, pady=8)
        self.app, self.asset = app, asset
        self.alive, self.loading = True, False
        self.generation = 0
        self.snapshot = None
        self.display_currency = asset.currency
        self.fx = None
        head = Frame(self, background=CARD)
        head.pack(fill=X)
        Label(head, text=asset.ticker.replace(".SA", ""), bg=CARD, fg=TEXT,
              font=("Sans", 12, "bold")).pack(side=LEFT)
        if removable:
            ttk.Button(head, text="×", width=3, command=lambda: app.remove(self)).pack(side=RIGHT)
            ttk.Button(head, text="Ampliar", command=lambda: app.preview(asset)).pack(side=RIGHT)
        Label(self, text=asset.name, bg=CARD, fg=MUTED, anchor="w").pack(fill=X)
        price_row = Frame(self, bg=CARD)
        price_row.pack(fill=X)
        self.price = Label(price_row, text="—", bg=CARD, fg=TEXT, font=("Sans", 19, "bold"))
        self.price.pack(anchor="w")
        if asset.currency == 'USD':
            self.currency_button = ttk.Button(price_row, text='Ver em R$', command=self.toggle_currency)
            self.price.pack(side=LEFT)
            self.currency_button.pack(side=LEFT, padx=8)
        self.change = Label(self, text="Variação no período: —", bg=CARD, fg=MUTED)
        self.change.pack(anchor="w")
        controls = Frame(self, bg=CARD)
        controls.pack(fill=X, pady=3)
        self.period = StringVar(value=period)
        selector = ttk.Combobox(controls, textvariable=self.period, values=list(HISTORY_RANGES),
                               state="readonly", width=18)
        selector.pack(side=LEFT)
        selector.bind("<<ComboboxSelected>>", self.period_changed)
        ttk.Button(controls, text="↻", width=3, command=self.refresh).pack(side=RIGHT)
        self.chart = MarketChart(self)
        self.chart.configure(width=200, height=150)
        self.chart.pack(fill=BOTH, expand=True)
        self.status = Label(self, text="Aguardando atualização", bg=CARD, fg=MUTED,
                            anchor="w", wraplength=290)
        self.status.pack(fill=X)
        self.refresh()

    def period_changed(self, _event=None, save=True):
        self.snapshot = None
        self.chart.snapshot = None
        self.chart.redraw()
        self.price.config(text="—")
        self.change.config(text="Variação no período: —", fg=MUTED)
        self.refresh(force=True)
        if save:
            self.app.save()

    def refresh(self, force=False):
        if not self.alive or (self.loading and not force):
            return
        self.generation += 1
        version = self.generation
        self.loading = True
        self.status.config(text="Consultando " + self.period.get().lower() + "…")
        self.app.submit(
            lambda result, error: self.receive(version, result, error),
            self.app.provider.history, self.period.get(), self.asset.symbol, self.asset.name)

    def receive(self, version, snapshot, error):
        if not self.alive or version != self.generation:
            return
        self.loading = False
        if error:
            self.status.config(text="Sem cotação disponível: " + str(error))
            return
        self.snapshot = snapshot
        self.draw_snapshot()
        if self.asset.currency == 'USD' and self.display_currency == 'BRL':
            self.app.submit(self.refresh_fx_received, self.app.provider.usd_brl)

    def refresh_fx_received(self, result, error):
        if self.alive and self.display_currency == 'BRL':
            self.fx_received(result, error)

    def draw_snapshot(self):
        snapshot = self.snapshot
        if snapshot is None:
            return
        if self.display_currency == 'BRL' and self.asset.currency == 'USD':
            if self.fx is None:
                return
            snapshot = self.app.provider.converted(snapshot, self.fx[0])
        self.chart.set_snapshot(snapshot)
        digits = 6 if self.asset.kind == 'forex' else 2
        value = f"{snapshot.last_price:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        prefix = 'US$ ' if self.display_currency == 'USD' else 'R$ '
        self.price.config(text=(value + " pts") if self.asset.ticker.startswith("^") else prefix + value)
        self.change.config(text=f"Variação no período: {snapshot.change_percent:+.2f}%".replace(".", ","),
                           fg=GREEN if snapshot.change >= 0 else RED)
        stamp = snapshot.timestamps[-1].strftime("%d/%m/%Y %H:%M")
        self.status.config(text=f"Último dado: {stamp} • Brasília")
        if self.asset.kind == 'forex':
            self.status.config(text=f"1 {self.asset.ticker.split('/')[0]} = R$ {value}\nÚltimo dado: {stamp} • Brasília")
        if self.asset.currency == 'USD' and self.display_currency == 'BRL':
            self.status.config(text=f"{stamp} • USD/BRL {self.fx[0]:.4f} ({self.fx[1]:%d/%m})\nSérie convertida pelo mesmo câmbio; não é retorno cambial histórico.")

    def toggle_currency(self):
        if self.display_currency == 'BRL':
            self.display_currency = 'USD'
            self.currency_button.config(text='Ver em R$')
            self.draw_snapshot()
            return
        self.currency_button.config(state='disabled')
        self.app.submit(self.fx_received, self.app.provider.usd_brl)

    def fx_received(self, result, error):
        if not self.alive:
            return
        self.currency_button.config(state='normal')
        if error:
            self.status.config(text='Conversão indisponível: ' + str(error))
            return
        self.fx = result
        self.display_currency = 'BRL'
        self.currency_button.config(text='Ver em US$')
        self.draw_snapshot()

    def dispose(self):
        self.alive = False
        self.destroy()


class DashboardTab:
    def __init__(self, notebook):
        self.frame = Frame(notebook, bg=BACKGROUND)
        self.canvas = Canvas(self.frame, bg=BACKGROUND, highlightthickness=0)
        scroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        scroll.pack(side=RIGHT, fill="y")
        self.canvas.pack(fill=BOTH, expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.body = Frame(self.canvas, bg=BACKGROUND)
        self.window = self.canvas.create_window(0, 0, anchor="nw", window=self.body)
        self.cards = []
        self.canvas.bind("<Configure>", lambda event: self.layout())
        self.body.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

    def layout(self):
        count = len(self.cards)
        columns = min(3, max(1, count))
        rows = max(1, math.ceil(count / columns))
        for i in range(3):
            self.body.columnconfigure(i, weight=1 if i < columns else 0, uniform="cards", minsize=0)
        for i in range(12):
            self.body.rowconfigure(i, weight=1 if i < rows else 0, minsize=0)
        self.canvas.itemconfigure(self.window, width=max(1, self.canvas.winfo_width()),
                                  height=max(self.canvas.winfo_height(), rows * 330))
        for i, card in enumerate(self.cards):
            card.grid(row=i // columns, column=i % columns, sticky="nsew", padx=5, pady=5)


class MainWindow:
    def __init__(self, root: Tk):
        self.root = root
        self.provider = YahooFinanceProvider()
        self.catalog = Catalog()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.results = queue.Queue()
        self.tabs, self.previews = [], []
        self.closed = False
        self.state_path = DATA_DIR / "dashboard.json"
        root.title("Bolsa Brasil — Painel B3")
        root.geometry("1200x800")
        root.minsize(960, 580)
        root.configure(bg=BACKGROUND)
        style = ttk.Style(root)
        style.theme_use("clam")
        header = Frame(root, bg=BACKGROUND, padx=16, pady=12)
        header.pack(fill=X)
        Label(header, text="BOLSA BRASIL", bg=BACKGROUND, fg=TEXT,
              font=("Sans", 16, "bold")).pack(side=LEFT)
        ttk.Button(header, text="+ Acrescentar gráfico/cotação", command=self.search_window).pack(side=RIGHT)
        ttk.Button(header, text="Atualizar", command=self.refresh_all).pack(side=RIGHT, padx=8)
        from .portfolio_ui import choose_portfolio
        ttk.Button(header, text="Criar carteira", command=lambda: choose_portfolio(self, True)).pack(side=RIGHT, padx=4)
        ttk.Button(header, text="Abrir carteira", command=lambda: choose_portfolio(self, False)).pack(side=RIGHT, padx=4)
        period_bar = Frame(root, bg=BACKGROUND, padx=16, pady=6)
        period_bar.pack(fill=X)
        Label(period_bar, text="Período de todos os gráficos da aba:", bg=BACKGROUND, fg=MUTED).pack(side=LEFT)
        self.tab_period = StringVar(value="Hoje")
        ttk.Combobox(period_bar, textvariable=self.tab_period, values=list(HISTORY_RANGES),
                     state="readonly", width=20).pack(side=LEFT, padx=8)
        ttk.Button(period_bar, text="Aplicar à aba", command=self.apply_tab_period).pack(side=LEFT)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=BOTH, expand=True, padx=10)
        # Eventos dos filhos chegam ao toplevel: inclui cartões e o Canvas do gráfico.
        # X11 usa Button-4/5; Windows e macOS usam MouseWheel.
        for sequence in ('<Button-4>', '<Button-5>', '<MouseWheel>'):
            root.bind(sequence, self.scroll_dashboard, add='+')
        self.footer = StringVar(value="Carregando catálogo B3…")
        Label(root, textvariable=self.footer, bg=BACKGROUND, fg=MUTED).pack(fill=X, pady=8)
        self.restore()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(80, self.poll)
        root.after(60000, self.auto_refresh)
        self.submit(self.catalog_loaded, self.catalog.refresh)

    def scroll_dashboard(self, event):
        if event.state & 0x0001:  # Shift fica reservado à rolagem horizontal.
            return
        widget = event.widget
        if isinstance(widget, (ttk.Combobox, ttk.Scrollbar)):
            return
        selected = self.notebook.select()
        tab = next((tab for tab in self.tabs if str(tab.frame) == selected), None)
        if tab is None:
            return
        while widget is not None and widget != tab.frame:
            widget = getattr(widget, 'master', None)
        if widget is None or tab.canvas.yview() == (0.0, 1.0):
            return
        if event.num in (4, 5):
            steps = -3 if event.num == 4 else 3
        elif event.delta:
            magnitude = max(1, int(abs(event.delta) / 120))
            steps = -3 * magnitude if event.delta > 0 else 3 * magnitude
        else:
            return
        tab.canvas.yview_scroll(steps, 'units')
        return 'break'

    def submit(self, callback, function, *args):
        future = self.executor.submit(function, *args)
        def done(future):
            try:
                result, error = future.result(), None
            except Exception as exc:
                result, error = None, exc
            self.results.put((callback, result, error))
        future.add_done_callback(done)

    def apply_tab_period(self):
        selected = self.notebook.select()
        for tab in self.tabs:
            if str(tab.frame) == selected:
                for card in tab.cards:
                    card.period.set(self.tab_period.get())
                    card.period_changed(save=False)
                self.save()
                break

    def poll(self):
        if self.closed:
            return
        for _ in range(100):
            try:
                callback, result, error = self.results.get_nowait()
            except queue.Empty:
                break
            callback(result, error)
        self.root.after(80, self.poll)

    def catalog_loaded(self, result, error):
        if error:
            self.footer.set(f"Catálogo offline ({len(self.catalog.assets)} ativos salvos). {error}")
        else:
            self.catalog.merge(result)
            self.footer.set(f"Catálogo: {len(result)} ativos • Cotações Yahoo Finance, sujeitas a atraso.")
        if getattr(self, "search_dialog", None) and self.search_dialog.winfo_exists():
            self.update_search()

    def add(self, asset, period="Hoje", save=True):
        for tab in self.tabs:
            if any(c.asset.ticker == asset.ticker for c in tab.cards):
                self.notebook.select(tab.frame)
                return False
        tab = next((t for t in self.tabs if len(t.cards) < 12), None)
        if tab is None:
            if len(self.tabs) >= 4:
                messagebox.showinfo("Painel completo", "Limite de 48 ativos: 12 por aba e 4 abas.",
                                    parent=self.root)
                return False
            tab = DashboardTab(self.notebook)
            self.tabs.append(tab)
            self.notebook.add(tab.frame, text=f"Aba {len(self.tabs)}")
        tab.cards.append(QuoteCard(tab.body, self, asset, period, removable=True))
        tab.layout()
        self.notebook.select(tab.frame)
        self.update_titles()
        if save:
            self.save()
        return True

    def update_titles(self):
        for i, tab in enumerate(self.tabs, 1):
            self.notebook.tab(tab.frame, text=f"Aba {i} · {len(tab.cards)}/12")

    def remove(self, card):
        for tab in self.tabs:
            if card in tab.cards:
                tab.cards.remove(card)
                card.dispose()
                tab.layout()
                break
        self.update_titles()
        self.save()

    def save(self):
        try:
            save_json(self.state_path, [[{"asset": asdict(c.asset), "period": c.period.get()}
                                       for c in t.cards] for t in self.tabs])
        except OSError as exc:
            self.footer.set(f"Não foi possível salvar o painel: {exc}")

    def restore(self):
        try:
            pages = json.loads(self.state_path.read_text())
            for page in pages[:4]:
                tab = DashboardTab(self.notebook)
                self.tabs.append(tab)
                self.notebook.add(tab.frame, text=f"Aba {len(self.tabs)}")
                for row in page[:12]:
                    asset = Asset(**row["asset"])
                    period = row.get("period", "Hoje")
                    if period not in HISTORY_RANGES:
                        period = "Hoje"
                    tab.cards.append(QuoteCard(tab.body, self, asset, period, removable=True))
                tab.layout()
            self.update_titles()
        except (OSError, ValueError, TypeError, KeyError):
            pass
        if not self.tabs:
            self.add(IBOV, save=False)

    def search_window(self):
        if getattr(self, "search_dialog", None) and self.search_dialog.winfo_exists():
            self.search_dialog.lift()
            return
        dialog = self.search_dialog = Toplevel(self.root)
        dialog.title("Buscar ativos — B3, EUA, criptomoedas e câmbio")
        dialog.geometry("720x520")
        self.query = StringVar()
        Label(dialog, text="Digite ao menos 3 caracteres do ticker ou nome").pack(pady=10)
        entry = ttk.Entry(dialog, textvariable=self.query, font=("Sans", 13))
        entry.pack(fill=X, padx=16)
        entry.focus_set()
        ttk.Button(dialog, text='Buscar online (também tickers de 1 ou 2 letras)',
                   command=self.search_online).pack(pady=5)
        entry.bind('<Return>', lambda _: self.search_online())
        self.search_job = None
        self.search_version = 0
        self.search_info = StringVar()
        Label(dialog, textvariable=self.search_info).pack(pady=8)
        area = Frame(dialog)
        area.pack(fill=BOTH, expand=True, padx=16, pady=8)
        self.matches = ttk.Treeview(area, columns=("ticker", "name", "kind"), show="headings",
                                    selectmode="browse")
        for column, title, width in (("ticker", "Ticker", 100), ("name", "Nome", 390), ("kind", "Tipo", 90)):
            self.matches.heading(column, text=title)
            self.matches.column(column, width=width)
        scroll = ttk.Scrollbar(area, orient="vertical", command=self.matches.yview)
        scroll.pack(side=RIGHT, fill="y")
        self.matches.configure(yscrollcommand=scroll.set)
        self.matches.pack(fill=BOTH, expand=True)
        self.matches.bind("<<TreeviewSelect>>", self.open_match)
        self.query.trace_add("write", lambda *_: self.search_changed())
        self.update_search()

    def search_changed(self):
        self.search_version += 1
        if self.search_job:
            self.root.after_cancel(self.search_job)
            self.search_job = None
        self.update_search()
        if len(self.query.get().strip()) >= 3:
            self.search_job = self.root.after(500, self.search_online)

    def search_online(self):
        self.search_job = None
        if not self.search_dialog.winfo_exists():
            return
        query = self.query.get().strip()
        if not query:
            return
        self.search_version += 1
        version, dialog = self.search_version, self.search_dialog
        self.search_info.set('Buscando EUA e criptomoedas…')
        def done(result, error):
            if not dialog.winfo_exists() or dialog != self.search_dialog or version != self.search_version:
                return
            if error:
                self.search_info.set('Busca online indisponível; resultados locais mantidos.')
                return
            self.catalog.merge(result)
            self.update_search()
            if len(query) < 3:
                self.search_results = result
                for i, a in enumerate(result):
                    self.matches.insert('', 'end', iid=str(i), values=(a.ticker, a.name, a.kind))
            self.search_info.set(f'{len(self.search_results)} resultados • B3 / EUA / cripto / câmbio')
        self.submit(done, search_global, query)

    def update_search(self):
        self.matches.delete(*self.matches.get_children())
        self.search_results = self.catalog.search(self.query.get())
        for i, asset in enumerate(self.search_results):
            self.matches.insert("", "end", iid=str(i), values=(asset.ticker, asset.name, asset.kind))
        self.search_info.set(
            f"{len(self.search_results)} resultados • {len(self.catalog.assets)} ativos no catálogo"
            if len(self.query.get().strip()) >= 3 else "Sugestões aparecem a partir do terceiro caractere.")

    def open_match(self, _event=None):
        selected = self.matches.selection()
        if selected:
            asset = self.search_results[int(selected[0])]
            self.matches.selection_remove(*selected)
            self.preview(asset)

    def preview(self, asset):
        dialog = Toplevel(self.root)
        dialog.title(f"{asset.ticker} — {asset.name}")
        dialog.geometry("920x650")
        card = QuoteCard(dialog, self, asset)
        card.pack(fill=BOTH, expand=True)
        self.previews.append(card)
        button = ttk.Button(dialog, text="Acrescentar à tela inicial")
        button.configure(command=lambda: button.configure(text="Adicionado ao painel", state="disabled")
                         if self.add(asset, card.period.get()) else None)
        button.pack(pady=10)
        def close():
            self.previews.remove(card)
            card.dispose()
            dialog.destroy()
        dialog.protocol("WM_DELETE_WINDOW", close)

    def refresh_all(self):
        for tab in self.tabs:
            for card in tab.cards:
                card.refresh()
        for card in self.previews:
            card.refresh()

    def auto_refresh(self):
        self.refresh_all()
        self.root.after(60000, self.auto_refresh)

    def close(self):
        self.save()
        self.closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()
