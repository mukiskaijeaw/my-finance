import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mcp_ui_poc as m


class MCPProtocolTests(unittest.TestCase):
    def test_resource_metadata_and_one_button(self):
        tools=m.dispatch('tools/list',{})['tools']
        self.assertEqual(tools[0]['_meta']['ui']['resourceUri'],m.BUTTON)
        text=m.dispatch('resources/read',{'uri':m.BUTTON})['contents'][0]
        self.assertEqual(text['mimeType'],m.MIME)
        self.assertEqual(text['text'].count('<button '),1)

    def test_synthetic_context_across_tool_calls(self):
        m.clicks=0
        a=m.dispatch('tools/call',{'name':'shopping_demo_click','arguments':{}})['structuredContent']
        b=m.dispatch('tools/call',{'name':'shopping_demo_click','arguments':{}})['structuredContent']
        self.assertEqual((a['clicks'],b['clicks']),(1,2))
        self.assertEqual(a['context'],b['context'])

    def test_no_arbitrary_file_reads_or_financial_args(self):
        with self.assertRaises(ValueError):m.dispatch('resources/read',{'uri':'file:///database.csv'})
        with self.assertRaises(ValueError):m.dispatch('tools/call',{'name':'shopping_demo_click','arguments':{'income':30000}})

    def test_stdio_protocol_end_to_end(self):
        script=Path(m.__file__)
        messages=[dict(jsonrpc='2.0',id=1,method='initialize',params={'protocolVersion':'2025-06-18'}),
                  dict(jsonrpc='2.0',id=2,method='tools/list'),
                  dict(jsonrpc='2.0',id=3,method='resources/read',params={'uri':m.BUTTON}),
                  dict(jsonrpc='2.0',id=4,method='tools/call',params={'name':'shopping_demo_click','arguments':{}})]
        r=subprocess.run([sys.executable,'-B',str(script)],input='\n'.join(json.dumps(x) for x in messages)+'\n',
                         text=True,encoding='utf-8',capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        replies=[json.loads(line) for line in r.stdout.splitlines()]
        self.assertEqual([x['id'] for x in replies],[1,2,3,4])
        self.assertEqual(replies[3]['result']['structuredContent']['clicks'],1)

    def test_no_network_for_demo_resource(self):
        with patch('socket.socket',side_effect=AssertionError('network')):
            content=m.dispatch('resources/read',{'uri':m.SIMULATOR})['contents'][0]
        self.assertIn('ทดลองเปลี่ยนราคาสินค้า',content['text'])


if __name__=='__main__':unittest.main()
