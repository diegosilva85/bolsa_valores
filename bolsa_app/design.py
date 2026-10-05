"""Tema financeiro compartilhado; mantém navegação nativa por teclado do ttk."""
from tkinter import Frame, Canvas, Label, ttk
from PIL import Image, ImageDraw, ImageTk

BG, SURFACE, EDGE = '#0b1120', '#111827', '#263244'
FG, MUTED, ACCENT = '#e5e7eb', '#94a3b8', '#38bdf8'


def rounded_image(color, size=(32, 32), radius=10, outline=None):
    image = Image.new('RGBA', (size[0] * 3, size[1] * 3))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, size[0]*3-2, size[1]*3-2), radius=radius*3,
                           fill=color, outline=outline, width=3)
    return image.resize(size, Image.Resampling.LANCZOS)


def install_theme(root):
    style = ttk.Style(root)
    if 'finance' not in style.theme_names():
        style.theme_create('finance', parent='clam')
    style.theme_use('finance')
    root.option_add('*Font', 'Sans 10')
    for key, value in [('Background', BG), ('Foreground', FG), ('Entry.background', SURFACE),
                       ('Entry.foreground', FG), ('Entry.insertBackground', ACCENT),
                       ('Listbox.background', SURFACE), ('Listbox.foreground', FG),
                       ('Listbox.selectBackground', '#174869')]:
        root.option_add('*' + key, value)
    style.configure('.', background=BG, foreground=FG, font=('Sans', 10), borderwidth=0)
    images = []
    def element(name, colors, radius=10, size=(24, 24), border=10):
        items = [ImageTk.PhotoImage(rounded_image(c, size=size, radius=radius), master=root) for c in colors]
        images.extend(items)
        style.element_create(name, 'image', items[0], ('disabled', items[-1]),
                             ('pressed', items[2]), ('active', items[1]), ('selected', items[2]),
                             ('focus', items[1]), border=border, sticky='nsew')
    element('Finance.button', ['#22334c', '#305675', '#12638a', '#172235'])
    style.layout('TButton', [('Finance.button', {'sticky':'nsew', 'children':[
        ('Button.padding', {'sticky':'nsew', 'children':[('Button.label', {'sticky':'nsew'})]})]})])
    style.configure('TButton', padding=(5, 2), foreground=FG, anchor='center')
    style.map('TButton', foreground=[('disabled', '#66778d')])
    element('Finance.tab', ['#172235', '#223d57', '#12638a', '#172235'])
    style.layout('TNotebook.Tab', [('Finance.tab', {'sticky':'nsew', 'children':[
        ('Notebook.padding', {'sticky':'nsew', 'children':[('Notebook.label', {'sticky':'nsew'})]})]})])
    style.configure('TNotebook', background=BG, borderwidth=0, tabmargins=(4, 6, 4, 8))
    style.layout('TNotebook', [('Notebook.client', {'sticky': 'nsew'})])
    style.configure('TNotebook', bordercolor=BG, lightcolor=BG, darkcolor=BG)
    style.configure('TNotebook.Tab', padding=(10, 3), foreground=MUTED)
    style.map('TNotebook.Tab', foreground=[('selected', '#ffffff'), ('active', FG)])
    for name in ('TEntry', 'TCombobox'):
        style.configure(name, fieldbackground=SURFACE, foreground=FG, insertcolor=FG,
                        padding=7, bordercolor=EDGE, arrowcolor=ACCENT)
        style.map(name, fieldbackground=[('readonly', SURFACE)], foreground=[('readonly', FG)])
    for orientation in ('Vertical', 'Horizontal'):
        name = orientation + '.TScrollbar'
        element(orientation + '.Scrollbar.thumb', ['#38516d', '#527b9e', ACCENT, '#22334c'],
                radius=5, size=(12, 24) if orientation == 'Vertical' else (24, 12), border=4)
        style.layout(name, [(orientation + '.Scrollbar.trough', {'sticky':'ns' if orientation == 'Vertical' else 'ew',
            'children':[(orientation + '.Scrollbar.thumb', {'sticky':'nsew', 'expand': '1'})]})])
        style.configure(name, troughcolor=BG, borderwidth=0, arrowsize=12, width=12)
    style.configure('Treeview', background=SURFACE, fieldbackground=SURFACE, foreground=FG,
                    rowheight=32, borderwidth=0)
    style.configure('Treeview.Heading', background='#1c2c42', foreground=MUTED, padding=9)
    style.map('Treeview', background=[('selected', '#164765')], foreground=[('selected', '#ffffff')])
    root._finance_images = images


class RoundedFrame(Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        fill = self.cget('background')
        try:
            backdrop = parent.cget('background')
        except Exception:
            backdrop = BG
        image = Image.new('RGB', (36, 36), backdrop)
        image.paste(rounded_image(fill, (36, 36), 14), (0, 0), rounded_image(fill, (36, 36), 14))
        self._corners = []
        for box, anchor, x, y in [((0,0,14,14),'nw',0,0), ((22,0,36,14),'ne',1,0),
                                   ((0,22,14,36),'sw',0,1), ((22,22,36,36),'se',1,1)]:
            photo = ImageTk.PhotoImage(image.crop(box))
            label = Label(self, image=photo, borderwidth=0, highlightthickness=0)
            label.place(relx=x, rely=y, anchor=anchor, bordermode='outside')
            self._corners.append((label, photo))


class ScrollArea(Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self.canvas = Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True)
        self.body = Frame(self.canvas, bg=BG)
        item = self.canvas.create_window(0, 0, window=self.body, anchor='nw')
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.body.bind('<Configure>', lambda _: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(item, width=e.width))
        top = self.winfo_toplevel()
        self._bindings = []
        def wheel(event):
            widget = event.widget
            while widget is not None and widget != self:
                widget = getattr(widget, 'master', None)
            if widget == self:
                delta = -1 if event.num == 4 else 1 if event.num == 5 else (-1 if event.delta > 0 else 1)
                self.canvas.yview_scroll(delta * 3, 'units')
                return 'break'
        for sequence in ('<Button-4>', '<Button-5>', '<MouseWheel>'):
            self._bindings.append((sequence, top.bind(sequence, wheel, add='+')))
        def cleanup(event):
            if event.widget == self:
                for sequence, ident in self._bindings:
                    top.unbind(sequence, ident)
        self.bind('<Destroy>', cleanup)
