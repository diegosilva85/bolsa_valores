"""Logos em cache local; rede e decodificação nunca rodam na thread do Tk."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from threading import Event, Lock
from urllib.request import Request, urlopen
from PIL import Image, ImageOps, ImageTk
from .catalog import DATA_DIR


class LogoCache:
    def __init__(self, directory=None):
        self.directory = Path(directory or DATA_DIR / 'logos')
        self.lock = Lock()
        self.failed = set()
        self.stop = Event()

    def get(self, asset):
        ticker = asset.ticker.removesuffix('.SA')
        # Hosts fixos: nunca usa URLs arbitrárias vindas da planilha.
        if asset.kind == 'crypto' and re.fullmatch(r'[A-Z0-9]{2,15}-USD', ticker):
            url = f'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/{ticker[:-4].lower()}.png'
        elif asset.kind in ('us-stock', 'us-etf') and re.fullmatch(r'[A-Z]{1,8}(?:-[A-Z])?', ticker):
            url = f'https://images.financialmodelingprep.com/symbol/{ticker}.png'
        elif re.fullmatch(r'[A-Z]{4}\d{1,2}', ticker) and asset.currency != 'USD':
            url = f'https://icons.brapi.dev/icons/{ticker}.svg'
        else:
            return None
        path = self.directory / (ticker + '.png')
        try:
            if path.exists():
                with Image.open(path) as image:
                    return image.convert('RGBA').copy()
            with self.lock:
                if ticker in self.failed or self.stop.is_set():
                    return None
            request = Request(url, headers={'User-Agent': 'BolsaBrasil/1.0'})
            with urlopen(request, timeout=6) as response:
                content = response.read(512001)
            if len(content) > 512000:
                raise ValueError('Logo muito grande')
            from cairosvg.surface import PNGSurface
            def deny_external(*_args, **_kwargs):
                raise ValueError('Recursos externos em SVG não são permitidos')
            png = PNGSurface.convert(bytestring=content, output_width=64, output_height=64,
                                     url_fetcher=deny_external) if url.endswith('.svg') else content
            with Image.open(BytesIO(png)) as image:
                if image.width > 2048 or image.height > 2048:
                    raise ValueError('Dimensões excessivas')
                image = image.convert('RGBA').copy()
                image.thumbnail((64, 64), Image.Resampling.LANCZOS)
            self.directory.mkdir(parents=True, exist_ok=True)
            with self.lock:
                temporary = path.with_suffix('.tmp')
                image.save(temporary, format='PNG')
                temporary.replace(path)
            return image
        except Exception:
            with self.lock:
                self.failed.add(ticker)
            return None

    def preload(self, assets):
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = pool.map(self.get, assets)
            return sum(image is not None for image in results)


def badge(parent, app, asset, size=36, background='#111827'):
    from tkinter import Label
    from .design import rounded_image
    tint = ('#19485c', '#3e356b', '#285044', '#623f35')[int(sha256(asset.ticker.encode()).hexdigest()[:2], 16) % 4]
    fallback = ImageTk.PhotoImage(rounded_image(tint, (size, size), 9), master=parent)
    label = Label(parent, image=fallback, text=asset.ticker.replace('^', '')[:2], compound='center',
                  fg='#ffffff', bg=background, font=('Sans', 10, 'bold'), borderwidth=0)
    label._logo = fallback
    def loaded(image, error):
        if not label.winfo_exists() or image is None or error:
            return
        tile = rounded_image('#ffffff', (size, size), 9)
        icon = ImageOps.contain(image, (size-8, size-8), Image.Resampling.LANCZOS)
        tile.alpha_composite(icon, ((size-icon.width)//2, (size-icon.height)//2))
        label._logo = ImageTk.PhotoImage(tile, master=label)
        label.configure(image=label._logo, text='')
    if hasattr(app, 'logos'):
        app.submit(loaded, app.logos.get, asset)
    return label


def tree_badge(tree, app, asset, iid):
    """Apenas cache nas listas: não dispara milhares de downloads numa busca."""
    from .design import rounded_image
    if not hasattr(tree, '_brand_images'):
        tree._brand_images = {}
        tree.configure(show='tree headings')
        tree.column('#0', width=38, minwidth=38, stretch=False)
        tree.heading('#0', text='')
    if asset.ticker not in tree._brand_images:
        tile = rounded_image('#285044', (26, 26), 7)
        path = app.logos.directory / (asset.ticker.removesuffix('.SA') + '.png')
        if re.fullmatch(r'[A-Z0-9-]{1,20}', asset.ticker.removesuffix('.SA')) and path.exists():
            try:
                with Image.open(path) as image:
                    icon = ImageOps.contain(image.convert('RGBA'), (22, 22))
                tile = rounded_image('#ffffff', (26, 26), 7)
                tile.alpha_composite(icon, ((26-icon.width)//2, (26-icon.height)//2))
            except (OSError, ValueError):
                pass
        tree._brand_images[asset.ticker] = ImageTk.PhotoImage(tile, master=tree)
    tree.item(iid, image=tree._brand_images[asset.ticker])
