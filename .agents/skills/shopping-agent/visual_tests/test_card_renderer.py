import copy
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from engine import financial_fit
from card_renderer import render_financial_fit


def result(price='4500', allocated='0'):
    p = dict(income='30000', essential='20000', debt='2000', saving='5000', cash='10000',
             emergency='10000', reserved='0', earmarked=allocated, as_of=date.today().isoformat(),
             complete=True, future_complete=True, future_extra=[], income_kind='stable')
    return financial_fit(p, price, date.today())


class RenderTests(unittest.TestCase):
    def test_requested_poc_uses_engine(self):
        r = result()
        self.assertEqual((r['status'], r['monthly_surplus'], r['months']), ('SAVE_FIRST', '3000', 2))
        self.assertEqual((r['savings_progress']['goal'], r['savings_progress']['allocated']), ('4500', '0'))

    def test_light_and_dark_valid_png(self):
        with tempfile.TemporaryDirectory() as d:
            for theme in ('light', 'dark'):
                path = render_financial_fit(result(), Path(d) / (theme + '.png'), theme, demo=True)
                with Image.open(path) as image:
                    self.assertEqual((image.format, image.size), ('PNG', (1200, 1400)))

    def test_input_unchanged_and_no_network(self):
        r = result(); before = copy.deepcopy(r)
        with tempfile.TemporaryDirectory() as d, patch('socket.socket', side_effect=AssertionError('network forbidden')):
            render_financial_fit(r, Path(d) / 'card.png', demo=True)
        self.assertEqual(r, before)

    def test_changed_engine_values_change_image(self):
        with tempfile.TemporaryDirectory() as d:
            a = render_financial_fit(result('4500'), Path(d) / 'a.png', demo=True)
            b = render_financial_fit(result('9000'), Path(d) / 'b.png', demo=True)
            self.assertNotEqual(a.read_bytes(), b.read_bytes())

    def test_missing_data_not_fake_zero_progress(self):
        r = financial_fit({}, '4500', date.today())
        self.assertNotIn('savings_progress', r)
        with tempfile.TemporaryDirectory() as d:
            render_financial_fit(r, Path(d) / 'missing.png', demo=True)

    def test_never_overwrites_existing_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'card.png'
            p.write_bytes(b'original')
            with self.assertRaises(FileExistsError):
                render_financial_fit(result(), p, demo=True)
            self.assertEqual(p.read_bytes(), b'original')


if __name__ == '__main__':
    unittest.main()
