import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = pathlib.Path(__file__).parents[1]/'acolad_premium_editorial_compare.py'
spec = importlib.util.spec_from_file_location('bench', SCRIPT)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

class Tests(unittest.TestCase):
    def test_models_priced(self):
        self.assertEqual(set(b.CORE).union(b.ALL),set(b.PRICES))
    def test_no_temperature_for_sol(self):
        x=b.build_payload('gpt-6.1-sol')
        self.assertEqual(x['reasoning_effort'],'low')
        self.assertNotIn('temperature',x)
    def test_luna_past_successful_setting(self):
        x=b.build_payload('gpt-6-luna')
        self.assertEqual(x['reasoning_effort'],'none')
    def test_output_cap(self):
        self.assertEqual(b.build_payload('gpt-6.1-sol')['max_tokens'],2500)
    def test_price(self):
        self.assertAlmostEqual(b.money('gpt-6.1-sol',2000,1800),0.022)
    def test_upper_bounds(self):
        self.assertLess(sum(b.quote_max(m) for m in b.CORE),0.12)
        self.assertLess(sum(b.quote_max(m) for m in b.ALL),0.19)
    def test_content_array(self):
        response={'choices':[{'message':{'content':[{'text':'متن فارسی'}]},'finish_reason':'stop'}],'usage':{'prompt_tokens':20,'completion_tokens':30}}
        text,usage,finish=b.extract_response(response)
        self.assertEqual((text,finish),('متن فارسی','stop'))
        self.assertEqual(usage['prompt_tokens'],20)
    def test_block_without_auth(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(b,'OUT',pathlib.Path(d)), patch.dict('os.environ',{'GAPGPT_API_KEY':'fake'},clear=True):
                self.assertEqual(b.main(['--mode','compare']),2)
    def test_offline_has_no_http(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(b,'OUT',pathlib.Path(d)),patch.object(b,'fetch_json',side_effect=AssertionError('network called')):
                self.assertEqual(b.main(['--mode','offline']),0)
                import json
                data=json.loads((pathlib.Path(d)/'status.json').read_text())
                self.assertEqual(data['requests_sent'],0)
                self.assertEqual(data['publication'],'NEVER')

if __name__ == '__main__':unittest.main()
