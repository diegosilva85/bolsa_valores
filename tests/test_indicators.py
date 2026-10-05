import unittest
from bolsa_app.indicators import rows_from_info, formatted


class IndicatorsTests(unittest.TestCase):
    def test_ratios_units_and_missing(self):
        rows = rows_from_info({'currency':'BRL', 'trailingPE':8, 'totalDebt':100, 'totalCash':40,
                              'ebitda':20, 'debtToEquity':70, 'returnOnEquity':.15}, 'stock')
        values = {r[1]:r for r in rows}
        self.assertEqual(values['Dívida líquida / EBITDA'][2],3)
        self.assertEqual(formatted(values['Dívida total / patrimônio'][2],'percent_points'),'70,00%')
        self.assertEqual(formatted(values['ROE'][2],'percent'),'15,00%')
        self.assertIsNone(values['P/VP'][2])
        self.assertEqual(formatted(None,'multiple'),'—')
        rows = rows_from_info({'totalDebt':100,'ebitda':20},'stock')
        self.assertIsNone(next(r[2] for r in rows if r[1]=='Dívida líquida / EBITDA'))

    def test_asset_applicability(self):
        for kind in ['crypto','forex','Índice']:
            self.assertEqual(rows_from_info({},kind),[])
        self.assertTrue(all(r[0]=='Valuation' for r in rows_from_info({},'fii')))
