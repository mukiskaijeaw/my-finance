import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'tests'))
from PIL import Image
from test_decision_policy import fixture
from decision_policy import evaluate_decision
from decision_renderer import render_decision_card
from shopping import today


class DecisionVisualTests(unittest.TestCase):
    def test_engine_to_policy_to_png_two_themes(self):
        p,d=fixture();r=evaluate_decision(p,d,today());before=copy.deepcopy(r)
        with tempfile.TemporaryDirectory() as tmp:
            for theme in ('light','dark'):
                path=render_decision_card(r,Path(tmp)/(theme+'.png'),theme,demo=True)
                with Image.open(path) as im:
                    self.assertEqual((im.format,im.width),('PNG',1200))
                    self.assertTrue(1450<=im.height<=1700)
        self.assertEqual(r,before)

    def test_mismatched_policy_fit_rejected(self):
        p,d=fixture();r=evaluate_decision(p,d,today())
        r['decision']['financial_fit']='AFFORDABLE'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError): render_decision_card(r,Path(tmp)/'bad.png')

    def test_missing_data_still_renders(self):
        _,d=fixture();r=evaluate_decision({},d,today())
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(render_decision_card(r,Path(tmp)/'missing.png',demo=True).exists())


if __name__=='__main__': unittest.main()
