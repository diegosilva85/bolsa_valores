import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO
from bolsa_app.catalog import Asset
from bolsa_app.logos import LogoCache


class LogosTests(unittest.TestCase):
    def test_download_then_offline_cache(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="orange"/></svg>'
        with tempfile.TemporaryDirectory() as directory:
            cache = LogoCache(directory)
            with patch('bolsa_app.logos.urlopen', return_value=BytesIO(svg)) as request:
                self.assertEqual(cache.get(Asset('ITUB4', 'Itau', 'stock')).size, (64, 64))
                self.assertIsNotNone(cache.get(Asset('ITUB4', 'Itau', 'stock')))
                self.assertEqual(request.call_count, 1)

    def test_invalid_and_missing_logos(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = LogoCache(directory)
            with patch('bolsa_app.logos.urlopen', side_effect=OSError('offline')) as request:
                self.assertIsNone(cache.get(Asset('../escape', '', 'stock')))
                self.assertIsNone(cache.get(Asset('PETR4', '', 'stock')))
                self.assertIsNone(cache.get(Asset('PETR4', '', 'stock')))
                self.assertEqual(request.call_count, 1)

    def test_svg_external_resources_blocked(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><image xlink:href="file:///etc/passwd" width="64" height="64"/></svg>'
        with tempfile.TemporaryDirectory() as directory:
            with patch('bolsa_app.logos.urlopen', return_value=BytesIO(svg)):
                self.assertIsNone(LogoCache(directory).get(Asset('ITUB4', '', 'stock')))
