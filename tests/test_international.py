import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
from openpyxl import Workbook

from bolsa_app.catalog import Asset, Catalog, search_global
from bolsa_app.market_data import MarketSnapshot, YahooFinanceProvider
from bolsa_app.portfolio import Trade, ExcelPortfolio, LEGACY_HEADERS, symbol_for
from bolsa_app.portfolio_ui import PortfolioWindow


class InternationalTests(unittest.TestCase):
    def test_symbols_and_currencies(self):
        for ticker, kind, symbol, currency in [('BTC','crypto','BTC-USD','USD'), ('ETH-USD','crypto','ETH-USD','USD'),
                ('AAPL','us-stock','AAPL','USD'), ('SPY','us-etf','SPY','USD'), ('PETR4','stock','PETR4.SA','BRL')]:
            asset = Asset(ticker,ticker,kind)
            self.assertEqual((asset.symbol, asset.currency), (symbol, currency))
        self.assertTrue(Catalog().search('BTC'))

    def test_mixed_excel_and_legacy(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'wallet.xlsx'
            wb = Workbook()
            wb.active.title = 'Operações'
            wb.active.append(LEGACY_HEADERS)
            wb.active.append(['old','01/01/2020','PETR4','Petrobras','Ações','Compra',10,20])
            wb.save(path)
            wallet = ExcelPortfolio(path).load()
            crypto = Trade.make('02/01/2020','BTC','Bitcoin','Criptomoedas','Compra','0,0025','60000')
            wallet.add(crypto)
            wallet.add(Trade.make('02/01/2020','AAPL','Apple','Ações EUA','Compra','0,5','200'))
            recovered = ExcelPortfolio(path).load()
            self.assertEqual(recovered.trades[0].currency, 'BRL')
            self.assertEqual(recovered.trades[1], crypto)
            self.assertEqual(crypto.currency, 'USD')
            self.assertEqual(crypto.quantity, Decimal('0.0025'))
            self.assertEqual(symbol_for(crypto.ticker,crypto.kind),'BTC-USD')

    def test_search_filter(self):
        with patch('yfinance.Search') as search:
            search.return_value.quotes = [dict(symbol='AAPL',quoteType='EQUITY',exchange='NMS'),
                dict(symbol='BTC-USD',quoteType='CRYPTOCURRENCY'), dict(symbol='BTC-EUR',quoteType='CRYPTOCURRENCY'),
                dict(symbol='SHOP.TO',quoteType='EQUITY',exchange='TOR')]
            self.assertEqual([a.ticker for a in search_global('abc')], ['AAPL','BTC-USD'])

    def test_conversion(self):
        window = object.__new__(PortfolioWindow)
        window.fx = (Decimal('5'),datetime.now())
        self.assertEqual(window.convert(Decimal('100'),'USD','BRL'),Decimal('500'))
        self.assertEqual(window.convert(Decimal('500'),'BRL','USD'),Decimal('100'))
        window.fx = None
        self.assertIsNone(window.convert(Decimal('100'),'USD','BRL'))
        snapshot = MarketSnapshot('AAPL','Apple',[datetime.now()],[100],100,10,10)
        converted = YahooFinanceProvider.converted(snapshot,5)
        self.assertEqual(converted.last_price,500)
        self.assertEqual(snapshot.last_price,100)


if __name__ == '__main__':
    unittest.main()
