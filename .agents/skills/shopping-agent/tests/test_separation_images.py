import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from shopping import load_finance,run_request,render,product_image
from test_engine import listing,TODAY

class SeparationImageTests(unittest.TestCase):
    def test_unconfigured_source_reads_no_financial_files(self):
        with patch('shopping.read_ledger',side_effect=AssertionError('must not read')):
            result=load_finance(None,TODAY)
        self.assertFalse(result['connected'])
        self.assertEqual(result['profile'],{})
        self.assertIn('finance_source_not_configured',result['issues'])

    def test_unconfigured_assessment_is_explicitly_incomplete(self):
        with patch('shopping.read_ledger',side_effect=AssertionError('must not read')):
            _,result=run_request({'include_financial':True,'listings':[listing()]},TODAY)
        self.assertEqual(result['results'][0]['financial']['status'],'INSUFFICIENT_DATA')
        self.assertIn('finance_source_not_configured',result['data_quality']['profile'])

    def test_search_never_reads_even_configured_source(self):
        with patch('shopping.load_finance',side_effect=AssertionError('must not load')):
            _,result=run_request({'listings':[listing()]},TODAY,'/some/private/workspace')
        self.assertEqual(result['results'][0]['price']['effective'],'950')

    def test_verified_image_and_provenance_render(self):
        item=listing()
        item.update(image_url='https://example.org/photo.jpg',image_source='https://example.org/product',
                    image_verified=True,image_matches_variant=True)
        request,result=run_request({'listings':[item]},TODAY)
        output=render(request,result)
        self.assertIn('![Synthetic product](https://example.org/photo.jpg)',output)
        self.assertIn('แหล่งภาพ:',output)

    def test_unknown_or_wrong_variant_image_not_embedded(self):
        for flag in ('image_verified','image_matches_variant'):
            item=listing();item.update(image_url='https://example.org/photo.jpg',image_source='https://example.org/product',image_verified=True,image_matches_variant=True)
            item[flag]=False
            self.assertNotIn('![',product_image(item))

    def test_unsafe_image_or_source_rejected(self):
        for value in ('javascript:alert(1)','http://example.org/image','https://user:pass@example.org/image'):
            for key in ('image_url','image_source'):
                item=listing();item.update(image_url='https://example.org/photo.jpg',image_source='https://example.org/product',image_verified=True,image_matches_variant=True)
                item[key]=value
                self.assertNotIn('![',product_image(item))

if __name__=='__main__':unittest.main()
