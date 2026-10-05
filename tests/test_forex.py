import unittest
from bolsa_app.catalog import Asset, Catalog, FX_ASSETS
from bolsa_app.portfolio import Trade, positions, symbol_for
from decimal import Decimal


class ForexTests(unittest.TestCase):
    def test_names_codes_and_symbols(self):
        catalog = Catalog()
        for query, expected in [('dolar','USD/BRL'), ('euro','EUR/BRL'), ('iene','JPY/BRL'),
                                ('yuan','CNY/BRL'), ('libra','GBP/BRL'), ('CHF','CHF/BRL')]:
            self.assertIn(expected, [a.ticker for a in catalog.search(query)])
        for asset in FX_ASSETS:
            self.assertEqual(asset.currency,'BRL')
            self.assertTrue(asset.symbol.endswith('=X'))
            self.assertEqual(symbol_for(asset.ticker,'Moedas'), asset.symbol)
        self.assertEqual(Asset('USD/BRL','Dólar','forex').symbol, 'BRL=X')

    def test_foreign_currency_position_is_valued_in_reais(self):
        buy = Trade.make('01/01/2020','USD','Dólar','Moedas','Compra','100','5')
        sell = Trade.make('02/01/2020','USD/BRL','Dólar','Moedas','Venda','25','6')
        self.assertEqual(buy.currency, 'BRL')
        position = positions([buy,sell])['USD/BRL']
        self.assertEqual(position.quantity, Decimal('75'))
        self.assertEqual(position.cost, Decimal('375'))
        with self.assertRaises(ValueError):
            Trade.make('01/01/2020','INVALID','Inválido','Moedas','Compra','10','1')
