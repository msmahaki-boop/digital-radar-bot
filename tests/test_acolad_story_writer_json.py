import unittest
from unittest.mock import patch
import acolad_luna_research_preview as module

class WriterJSONSafety(unittest.TestCase):
 def test_only_malformed_json_one_evidence_locked_retry(self):
  log=[]
  answer={"slides":[{"n":1,"text":"داستان نمونه"}]}
  with patch.object(module,"api_call",side_effect=[
    RuntimeError("GapGPT invalid JSON/shape: JSONDecodeError"),answer
  ]) as call:
   result=module.write_story_with_json_retry("key","VERIFIED_EVIDENCE=S01",{"requests_sent":0},log)
  self.assertEqual(result,answer)
  self.assertEqual(call.call_count,2)
  self.assertIn("VERIFIED_EVIDENCE=S01",call.call_args.args[2])
  self.assertEqual(len(log),1)
 def test_auth_401_must_not_retry(self):
  with patch.object(module,"api_call",side_effect=RuntimeError("GapGPT HTTP 401")) as call:
   with self.assertRaisesRegex(RuntimeError,"401"):
    module.write_story_with_json_retry("key","EVIDENCE",{},[])
  self.assertEqual(call.call_count,1)
 def test_two_malformed_results_still_veto(self):
  with patch.object(module,"api_call",side_effect=RuntimeError("GapGPT invalid JSON/shape: JSONDecodeError")) as call:
   with self.assertRaisesRegex(RuntimeError,"JSON"):
    module.write_story_with_json_retry("key","EVIDENCE",{},[])
  self.assertEqual(call.call_count,2)
 def test_budget_error_never_hidden(self):
  with patch.object(module,"api_call",side_effect=[
      RuntimeError("GapGPT invalid JSON/shape: JSONDecodeError"),
      RuntimeError("Budget planning gate blocked next call")]):
   with self.assertRaisesRegex(RuntimeError,"Budget"):
    module.write_story_with_json_retry("key","EVIDENCE",{},[])

if __name__=="__main__":unittest.main()
