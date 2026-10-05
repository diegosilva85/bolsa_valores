import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from bolsa_app.portfolio import ExcelPortfolio, Trade, positions


def trade(side='Compra', qty='10', price='20,50', day='01/01/2020', **kwargs):
    return Trade.make(day, 'PETR4', 'Petrobras', 'Ações', side, qty, price, **kwargs)


class PortfolioTests(unittest.TestCase):
    def test_partial_sale_and_average_cost(self):
        p = positions([trade(), trade(qty='10', price='30,50'), trade('Venda', '5', '40')])['PETR4']
        self.assertEqual(p.quantity, Decimal(15))
        self.assertEqual(p.cost, Decimal('382.50'))

    def test_oversell_backdate_and_duplicates(self):
        with self.assertRaises(ValueError):
            positions([trade(), trade('Venda', '11')])
        with self.assertRaises(ValueError):
            positions([trade(day='02/01/2020'), trade('Venda', '1')])
        t = trade()
        with self.assertRaises(ValueError):
            positions([t, t])
        self.assertEqual(positions([trade(), trade('Venda')]), {})

    def test_invalid_inputs(self):
        for qty in ('-1', '0', 'NaN', 'Infinity', 'abc'):
            with self.assertRaises(ValueError):
                trade(qty=qty)
        with self.assertRaises(ValueError):
            trade(day='32/01/2020')

    def test_excel_roundtrip_backup_and_external_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'carteira.xlsx'
            store = ExcelPortfolio(path)
            store.write([])
            first = trade()
            store.add(first)
            store.add(trade('Venda', '2'))
            reopened = ExcelPortfolio(path).load()
            self.assertEqual(reopened.trades, store.trades)
            self.assertEqual(positions(reopened.trades)['PETR4'].quantity, Decimal(8))
            backup = ExcelPortfolio(path.with_suffix('.backup.xlsx')).load()
            self.assertEqual(backup.trades, [first])
            reopened.add(trade(qty='1'))
            with self.assertRaises(ValueError):
                store.add(trade(qty='1'))
            # Invalid sales must not mutate the file or in-memory trades.
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                reopened.add(trade('Venda', '100'))
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
