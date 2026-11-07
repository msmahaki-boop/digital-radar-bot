import unittest
from unittest.mock import patch
import acolad_luna_research_preview as m

class PlanJSONFailure(unittest.TestCase):
 def test_only_invalid_model_json_enables_verified_fallback(self):
  logs=[]
  with patch.object(m,"api_call",side_effect=RuntimeError("GapGPT invalid JSON/shape: JSONDecodeError")):
   self.assertEqual(m.select_plan_or_verified_source_fallback("key","prompt",{},logs),
                    {"source_ids":[]})
  self.assertTrue(any("ORIGINAL source" in x for x in logs))
 def test_authentication_errors_never_masquerade_as_source_failure(self):
  with patch.object(m,"api_call",side_effect=RuntimeError("HTTP 401")):
   with self.assertRaisesRegex(RuntimeError,"HTTP 401"):
    m.select_plan_or_verified_source_fallback("key","prompt",{},[])
 def test_valid_plan_unchanged(self):
  plan={"source_ids":["S03"],"angle":"real"}
  with patch.object(m,"api_call",return_value=plan):
   self.assertEqual(m.select_plan_or_verified_source_fallback("key","prompt",{},[]),plan)

if __name__=="__main__":unittest.main()
