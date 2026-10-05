import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from bolsa_app.portfolio import CorporateEvent, ExcelPortfolio, Trade, positions


class EventsTests(unittest.TestCase):
    def test_liquidation_distinct_cost_cash_fraction_and_sale(self):
        event = self.event('Liquidação com entrega de cotas', target='EFGH3', factor='.83',
                           received_quantity=8, received_price=12, cash='5.61')
        ledger = []
        existing = Trade.make('01/01/2020', 'EFGH3', '', 'Ações', 'Compra', 2, 10)
        sell = Trade.make('03/01/2020', 'EFGH3', '', 'Ações', 'Venda', 5, 15)
        result = positions([self.buy(), existing, sell], [event], ledger)
        self.assertNotIn('ABCD3', result)
        self.assertEqual((result['EFGH3'].quantity, result['EFGH3'].cost), (5, 58))
        self.assertEqual(ledger[0]['fraction'], Decimal('.3'))
        self.assertEqual(ledger[0]['cash'], Decimal('5.61'))
        self.assertEqual(ledger[0]['old_cost'], 200)
        with tempfile.TemporaryDirectory() as folder:
            store = ExcelPortfolio(Path(folder) / 'liquidation.xlsx')
            store.write([self.buy()], [event])
            self.assertEqual(ExcelPortfolio(store.path).load().events, [event])

    def test_liquidation_validation(self):
        with self.assertRaises(ValueError):
            self.event('Liquidação com entrega de cotas', target='EFGH3')
        for qty in (7, 9):
            event = self.event('Liquidação com entrega de cotas', target='EFGH3', factor='.83', received_quantity=qty, received_price=12)
            with self.assertRaises(ValueError):
                positions([self.buy()], [event])

    def test_legacy_event_sheet(self):
        from openpyxl import load_workbook
        with tempfile.TemporaryDirectory() as folder:
            store = ExcelPortfolio(Path(folder) / 'legacy.xlsx')
            event = self.event('Desdobramento', factor=8)
            store.write([self.buy()], [event])
            workbook = load_workbook(store.path)
            workbook['Eventos'].delete_cols(13, 3)
            workbook.save(store.path)
            workbook.close()
            loaded = ExcelPortfolio(store.path).load()
            self.assertEqual(loaded.events, [event])
            loaded.write(loaded.trades)
            self.assertEqual(ExcelPortfolio(store.path).load().events, [event])

    def buy(self):
        return Trade.make('01/01/2020', 'ABCD3', 'Original', 'Ações', 'Compra', 10, 20)

    def event(self, type, **kwargs):
        return CorporateEvent.make('02/01/2020', type, 'ABCD3', 'Ações', **kwargs)

    def test_split_and_sale(self):
        event = self.event('Desdobramento', factor=2)
        sell = Trade.make('03/01/2020', 'ABCD3', '', 'Ações', 'Venda', 15, 12)
        p = positions([self.buy(), sell], [event])['ABCD3']
        self.assertEqual((p.quantity, p.cost), (5, 50))
        with self.assertRaises(ValueError):
            positions([self.buy(), sell])

    def test_reverse_fraction(self):
        p = positions([self.buy()], [self.event('Grupamento', factor='0.03')])['ABCD3']
        self.assertEqual((p.quantity, p.cost), (Decimal('.30'), 200))

    def test_merger_and_spinoff(self):
        for type, expected in [('Incorporação', 200), ('Cisão', 50)]:
            result = positions([self.buy()], [self.event(type, target='EFGH3', factor=2, cost_percent=25)])
            self.assertEqual(result['EFGH3'].quantity, 20)
            self.assertEqual(result['EFGH3'].cost, expected)
            self.assertEqual(sum(p.cost for p in result.values()), 200)

    def test_rename_bonus_amortization(self):
        result = positions([self.buy()], [self.event('Troca de ticker/nome', target='EFGH3', name='Novo')])
        self.assertNotIn('ABCD3', result)
        self.assertEqual(result['EFGH3'].name, 'Novo')
        p = positions([self.buy()], [self.event('Bonificação', factor='.1', amount=5)])['ABCD3']
        self.assertEqual((p.quantity, p.cost), (11, 205))
        p = positions([self.buy()], [self.event('Amortização', amount=2)])['ABCD3']
        self.assertEqual(p.cost, 180)

    def test_validation_and_same_day(self):
        event = self.event('Desdobramento', factor=2)
        with self.assertRaises(ValueError):
            positions([self.buy()], [event, self.event('Desdobramento', factor=2)])
        with self.assertRaises(ValueError):
            positions([self.buy()], [self.event('Amortização', amount=21)])
        with self.assertRaises(ValueError):
            positions([], [event])
        event = CorporateEvent.make('01/01/2020', 'Desdobramento', 'ABCD3', 'Ações', factor=2, timing='Depois')
        self.assertEqual(positions([self.buy()], [event])['ABCD3'].quantity, 20)

    def test_excel_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ExcelPortfolio(Path(folder) / 'portfolio.xlsx')
            event = self.event('Troca de ticker/nome', target='EFGH3', name='Novo')
            store.write([self.buy()], [event])
            loaded = ExcelPortfolio(store.path).load()
            self.assertEqual(loaded.events, [event])
            self.assertEqual(loaded.trades, store.trades)
            before = store.path.read_bytes()
            with self.assertRaises(ValueError):
                store.write([], [event])
            self.assertEqual(store.path.read_bytes(), before)
            store.write(store.trades)
            self.assertEqual(ExcelPortfolio(store.path).load().events, [event])
