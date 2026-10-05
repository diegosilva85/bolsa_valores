from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from bolsa_app.official_income import OfficialIncomeProvider, ITAU_HISTORY, parse_itau
from bolsa_app.income import generate_income
from bolsa_app.portfolio import Trade


class OfficialIncomeTests(unittest.TestCase):
    def parse(self, rows, year=2025):
        sheet = MagicMock()
        sheet.values = rows
        workbook = MagicMock()
        workbook.__iter__.return_value = iter([sheet])
        with patch('bolsa_app.official_income.ZipFile'), patch(
                'bolsa_app.official_income.load_workbook', return_value=workbook):
            return parse_itau(b'fixture', year)

    def rows(self):
        return [('Histórico',),
                ('Ano', 'Competência do Exercício', 'Posição Acionária',
                 'Data do Pagamento', 'Tipo de evento', 'PAGAMENTO'),
                (None, None, None, None, None, 'Bruto'),
                (2024, 'Dezembro', '09.12.2024', '07.03.2025', 'JCP Complementar', .31056),
                (None, None, None, None, None, None)]

    def test_payment_year_and_original_gross(self):
        rows = self.parse(self.rows())
        self.assertEqual(rows[0]['rawRate'], Decimal('.31056'))
        self.assertEqual(rows[0]['lastDatePrior'], date(2024, 12, 9))
        self.assertEqual(rows[0]['label'], 'JCP')
        self.assertEqual(rows[0]['source'], ITAU_HISTORY)

    def test_missing_year_is_not_zero(self):
        with self.assertRaisesRegex(ValueError, 'Sem cobertura'):
            self.parse(self.rows(), 2020)

    def test_changed_header_and_invalid_date_fail(self):
        rows = self.rows()
        rows[2] = (None,) * 6
        with self.assertRaises(ValueError):
            self.parse(rows)
        rows = self.rows()
        rows[3] = (2024, 'Dezembro', 'data ausente', '07.03.2025', 'JCP', .31)
        with self.assertRaises(ValueError):
            self.parse(rows)

    def test_unsupported_does_not_fetch(self):
        with patch('bolsa_app.official_income.urlopen') as request:
            with self.assertRaisesRegex(ValueError, 'sem cobertura'):
                OfficialIncomeProvider().fetch('BCFF11', 'FIIs', 2024)
            request.assert_not_called()

    def test_shared_download_and_persistable_source(self):
        provider = OfficialIncomeProvider()
        rows = self.parse(self.rows())
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'fixture'
        with patch('bolsa_app.official_income.urlopen', return_value=response) as request, patch(
                'bolsa_app.official_income.parse_itau', return_value=rows):
            trades = [Trade.make('01/01/2024', t, 'Itaú', 'Ações', 'Compra', 100, 30)
                      for t in ('ITUB3', 'ITUB4')]
            result, period, successful = generate_income(trades, [], 2025, provider, date(2025, 12, 31))
            self.assertEqual(request.call_count, 1)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].source, ITAU_HISTORY)
            self.assertEqual(result[0].gross, Decimal('31.06'))
            self.assertEqual(period['status'], 'Consultado')


if __name__ == '__main__':
    unittest.main()
