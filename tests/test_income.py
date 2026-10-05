from dataclasses import replace
from datetime import date
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bolsa_app.income import BrapiIncomeProvider, generate_income, monthly_totals, history_key
from bolsa_app.portfolio import CorporateEvent, ExcelPortfolio, Trade


class FakeProvider:
    def __init__(self, rows=None, failure=False):
        self.rows = rows or []
        self.failure = failure
        self.calls = []

    def fetch(self, ticker, kind, year):
        self.calls.append((ticker, kind, year))
        if self.failure:
            raise ValueError('offline')
        return self.rows


def event(**kwargs):
    return dict(paymentDate='2020-02-15', lastDatePrior='2020-01-10', rawRate='1.25', rate='1.25',
                label='DIVIDENDO', verified=True, **kwargs)


class IncomeTests(unittest.TestCase):
    def buy(self, day='01/01/2020', ticker='ABCD3', qty=10, kind='Ações'):
        return Trade.make(day, ticker, 'Teste', kind, 'Compra', qty, 20)

    def generate(self, trades=None, events=(), rows=None, year=2020):
        return generate_income(trades or [self.buy()], events, year, FakeProvider(rows or [event()]), today=date(max(2020, year), 12, 31))

    def test_record_date_not_current_or_payment_position(self):
        sell = Trade.make('20/01/2020', 'ABCD3', 'Teste', 'Ações', 'Venda', 10, 30)
        rows, meta, _ = self.generate([self.buy(), sell])
        self.assertEqual(rows[0].quantity, 10)
        self.assertEqual(rows[0].gross, Decimal('12.50'))
        self.assertEqual(monthly_totals(rows, 2020)[2]['Dividendos'], Decimal('12.50'))
        self.assertEqual(meta['status'], 'Consultado')

    def test_rights_before_selected_year_and_same_day_purchase(self):
        row = {**event(), 'lastDatePrior': '2019-12-31'}
        rows, _, _ = self.generate([self.buy('31/12/2019')], rows=[row])
        self.assertEqual(rows[0].quantity, 10)
        rows, _, _ = self.generate([self.buy('01/01/2020')], rows=[row])
        self.assertEqual(rows, [])

    def test_split_and_renamed_asset_history(self):
        split = CorporateEvent.make('05/01/2020', 'Desdobramento', 'ABCD3', 'Ações', factor=8)
        rename = CorporateEvent.make('20/01/2020', 'Troca de ticker/nome', 'ABCD3', 'Ações', target='EFGH3')
        rows, _, _ = self.generate(events=[split, rename])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ticker, 'ABCD3')
        self.assertEqual(rows[0].quantity, 80)

    def test_jcp_fii_amortization_and_pending(self):
        rows = [{**event(), 'label': label, 'relatedTo': label} for label in ('JCP', 'RENDIMENTO', 'AMORTIZACAO')]
        result, _, _ = self.generate([self.buy(ticker='ABCD11', kind='FIIs')], rows=rows)
        self.assertEqual({r.type for r in result}, {'JCP', 'Rendimentos FII', 'Amortizações'})
        self.assertEqual(sum(monthly_totals(result, 2020)[2].values()), Decimal('37.50'))
        self.assertEqual(sum(monthly_totals(result, 2020, today=date(2020, 1, 31))[2].values()), 0)

    def test_missing_unverified_conflicting_and_duplicate_data(self):
        normal = event()
        result, meta, _ = self.generate(rows=[normal, normal])
        self.assertEqual(len(result), 1)
        self.assertEqual(meta['status'], 'Consultado')
        result, meta, _ = self.generate(rows=[normal, {**normal, 'rawRate': '2'}])
        self.assertTrue(result[0].review)
        self.assertEqual(sum(monthly_totals(result, 2020)[2].values()), 0)
        self.assertEqual(meta['status'], 'Parcial')
        for changes in ({'rawRate': None}, {'paymentDate': None}, {'lastDatePrior': None}, {'rawRate':'nan'}):
            result, meta, _ = self.generate(rows=[{**normal, **changes}])
            self.assertEqual(result, [])
            self.assertTrue(meta['warnings'])
        for changes in ({'verified': False}, {'paymentDateIsDeadline': True}):
            result, _, _ = self.generate(rows=[{**normal, **changes}])
            self.assertTrue(result[0].review)

    def test_excel_roundtrip_refresh_and_other_years(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ExcelPortfolio(Path(folder) / 'test.xlsx')
            store.write([self.buy()])
            result = self.generate(store.trades)
            store.save_income_year(result)
            loaded = ExcelPortfolio(store.path).load()
            self.assertEqual(loaded.income, result[0])
            self.assertIn(2020, loaded.income_periods)
            changed = self.generate(store.trades, rows=[{**event(), 'rawRate': '2'}])
            loaded.save_income_year(changed)
            self.assertEqual(len(loaded.income), 1)
            self.assertEqual(loaded.income[0].gross, 20)
            future = self.generate(store.trades, rows=[{**event(), 'paymentDate':'2021-01-02'}], year=2021)
            loaded.save_income_year(future)
            self.assertEqual(len(loaded.income), 2)
            loaded.add(self.buy('01/03/2020', qty=1))
            self.assertEqual(len(ExcelPortfolio(loaded.path).load().income), 2)
            self.assertNotEqual(loaded.income_periods[2020]['history'], history_key(loaded.trades, loaded.events))

    def test_failure_preserves_file_and_external_conflict(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ExcelPortfolio(Path(folder) / 'test.xlsx')
            store.write([self.buy()])
            store.save_income_year(self.generate(store.trades))
            before = store.path.read_bytes()
            failed = generate_income(store.trades, [], 2020, FakeProvider(failure=True))
            with self.assertRaises(ValueError):
                store.save_income_year(failed)
            self.assertEqual(store.path.read_bytes(), before)
            with patch.object(store, 'digest', return_value='external change'):
                with self.assertRaises(ValueError):
                    store.save_income_year(self.generate(store.trades))
            self.assertEqual(store.path.read_bytes(), before)

    def test_empty_year_is_cached(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ExcelPortfolio(Path(folder) / 'test.xlsx')
            store.write([self.buy()])
            result = generate_income(store.trades, [], 2020, FakeProvider())
            store.save_income_year(result)
            loaded = ExcelPortfolio(store.path).load()
            self.assertEqual(loaded.income, [])
            self.assertIn(2020, loaded.income_periods)

    def test_provider_envelopes_and_token_not_in_url(self):
        data = {'results': [{'symbol':'ABCD3', 'requestedSymbol':'ABCD3', 'changed':False, 'data':{'cashDividends':[event()]}}]}
        with patch('bolsa_app.income.urlopen', return_value=BytesIO(json.dumps(data).encode())) as call:
            self.assertEqual(len(BrapiIncomeProvider('SECRET').fetch('ABCD3', 'Ações', 2020)), 1)
            request = call.call_args.args[0]
            self.assertNotIn('SECRET', request.full_url)
            self.assertEqual(request.get_header('Authorization'), 'Bearer SECRET')
            self.assertIn('includeRaw=true', request.full_url)
        data = {'dividends': [{**event(), 'symbol':'ABCD11'}]}
        with patch('bolsa_app.income.urlopen', return_value=BytesIO(json.dumps(data).encode())):
            self.assertEqual(len(BrapiIncomeProvider('').fetch('ABCD11', 'FIIs', 2020)), 1)

    def test_partial_failure_keeps_old_records_as_review(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ExcelPortfolio(Path(folder) / 'test.xlsx')
            store.write([self.buy(), self.buy(ticker='EFGH3')])
            result = self.generate(store.trades)
            store.save_income_year(result)
            rows, meta, _ = result
            meta = {**meta, 'status':'Parcial', 'warnings':'EFGH3 offline'}
            store.save_income_year(([r for r in rows if r.ticker == 'ABCD3'], meta, ['ABCD3']))
            self.assertEqual(len(store.income), 2)
            self.assertTrue(next(r for r in store.income if r.ticker == 'EFGH3').review)


if __name__ == '__main__':
    unittest.main()
