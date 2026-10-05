"""Catálogo paginado da brapi, com cópia local para consultas offline."""
import json
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import Request, urlopen

DATA_DIR = Path(__file__).resolve().parent.parent / '.bolsa_data'


@dataclass(frozen=True)
class Asset:
    ticker: str
    name: str
    kind: str = ''

    @property
    def currency(self):
        return 'USD' if self.kind in ('crypto', 'us-stock', 'us-etf') else 'BRL'

    @property
    def symbol(self):
        if self.kind == 'forex':
            return FX_SYMBOLS[self.ticker]
        if self.currency == 'USD':
            return self.ticker if self.kind != 'crypto' or self.ticker.endswith('-USD') else self.ticker + '-USD'
        return self.ticker if self.ticker.startswith('^') or self.ticker.endswith('.SA') else self.ticker + '.SA'


IBOV = Asset('^BVSP', 'Ibovespa', 'Índice')
FX_NAMES = {
    'USD': 'Dólar americano', 'EUR': 'Euro', 'JPY': 'Iene japonês',
    'CNY': 'Yuan chinês (renminbi)', 'GBP': 'Libra esterlina', 'CHF': 'Franco suíço',
    'CAD': 'Dólar canadense', 'AUD': 'Dólar australiano', 'NZD': 'Dólar neozelandês',
    'HKD': 'Dólar de Hong Kong', 'SGD': 'Dólar de Singapura', 'MXN': 'Peso mexicano',
    'ARS': 'Peso argentino', 'CLP': 'Peso chileno', 'ZAR': 'Rand sul-africano',
    'INR': 'Rúpia indiana', 'KRW': 'Won sul-coreano', 'SEK': 'Coroa sueca',
    'NOK': 'Coroa norueguesa', 'DKK': 'Coroa dinamarquesa',
}
FX_SYMBOLS = {code + '/BRL': ('BRL=X' if code == 'USD' else code + 'BRL=X') for code in FX_NAMES}
FX_ASSETS = [Asset(code + '/BRL', name + ' · reais por unidade', 'forex') for code, name in FX_NAMES.items()]
GLOBAL_ASSETS = [Asset('BTC-USD', 'Bitcoin', 'crypto'), Asset('ETH-USD', 'Ethereum', 'crypto'),
                 Asset('AAPL', 'Apple', 'us-stock'), Asset('MSFT', 'Microsoft', 'us-stock'),
                 Asset('NVDA', 'NVIDIA', 'us-stock'), Asset('SPY', 'SPDR S&P 500 ETF', 'us-etf')]


def search_global(query):
    import yfinance as yf
    quotes = yf.Search(query, max_results=30, news_count=0, timeout=15).quotes
    result = []
    for row in quotes:
        symbol, kind = row.get('symbol', ''), row.get('quoteType', '')
        if kind == 'CRYPTOCURRENCY' and symbol.endswith('-USD'):
            category = 'crypto'
        elif kind in ('EQUITY', 'ETF') and row.get('exchange') in ('NMS', 'NGM', 'NCM', 'NYQ', 'ASE', 'PCX', 'BTS'):
            category = 'us-etf' if kind == 'ETF' else 'us-stock'
        else:
            continue
        result.append(Asset(symbol, row.get('shortname') or row.get('longname') or symbol, category))
    return result


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.upper()) if not unicodedata.combining(c))


class Catalog:
    def __init__(self):
        self.assets = [IBOV]
        self.path = DATA_DIR / 'catalog.json'
        try:
            self.assets = [Asset(**row) for row in json.loads(self.path.read_text())]
        except (OSError, ValueError, TypeError):
            pass
        self.merge(GLOBAL_ASSETS)
        self.merge(FX_ASSETS)

    def merge(self, assets):
        self.assets = list({a.ticker: a for a in [*self.assets, *assets]}.values())

    def refresh(self):
        assets = {IBOV.ticker: IBOV}
        for page in range(1, 101):
            request = Request(f'https://brapi.dev/api/quote/list?limit=2000&sortBy=name&sortOrder=asc&page={page}',
                              headers={'User-Agent': 'BolsaBrasil/1.0'})
            with urlopen(request, timeout=20) as response:
                data = json.load(response)
            rows = data.get('stocks', [])
            if not rows:
                raise RuntimeError('O catálogo retornou uma página vazia.')
            for row in rows:
                ticker = row['stock']
                assets[ticker] = Asset(ticker, row.get('name') or ticker, row.get('subType') or row.get('type', ''))
            if not data.get('hasNextPage', False):
                if len(assets) - 1 < data.get('totalCount', 0):
                    raise RuntimeError('Catálogo incompleto; mantendo a cópia anterior. Tente novamente.')
                result = sorted(assets.values(), key=lambda a: a.ticker)
                result += [a for a in self.assets if a.currency == 'USD' or a.kind == 'forex']
                save_json(self.path, [asdict(a) for a in result])
                return result
        raise RuntimeError('Catálogo excedeu o limite de páginas; atualização não aplicada.')

    def search(self, query):
        query = normalize(query.strip())
        if len(query) < 3:
            return []
        return sorted((a for a in self.assets if query in normalize(a.ticker + ' ' + a.name)),
                      key=lambda a: (not a.ticker.startswith(query), a.ticker))
