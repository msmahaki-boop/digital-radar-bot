import unittest
from unittest.mock import patch
import acolad_luna_research_preview as research
import acolad_v4_daily_autopublish as social

class SharedGateway(unittest.TestCase):
 def test_social_writer_uses_verified_luna_client(self):
  with patch.dict(social.os.environ,{"GAPGPT_API_KEY":"fake_not_real"}):
   with patch.object(research,"api_call",return_value={"instagram":"متن نمونه"}) as call:
    result=social.model_json("style",{"evidence":[{"title":"Original research"}]})
  self.assertEqual(result,{"instagram":"متن نمونه"})
  self.assertEqual(call.call_args.args[1],"style")
  self.assertIn("Original research",call.call_args.args[2])
  self.assertEqual(call.call_args.args[3],2500)
  self.assertEqual(call.call_args.args[4]["budget_usd"],0.018)
 def test_auth_and_billing_errors_propagate(self):
  with patch.dict(social.os.environ,{"GAPGPT_API_KEY":"fake_not_real"}):
   with patch.object(research,"api_call",side_effect=RuntimeError("GapGPT HTTP 403")):
    with self.assertRaisesRegex(RuntimeError,"403"):
     social.model_json("style",{"one":"item"})
 def test_missing_secret_never_makes_paid_request(self):
  with patch.dict(social.os.environ,{"GAPGPT_API_KEY":""}):
   with patch.object(research,"api_call") as call:
    with self.assertRaisesRegex(RuntimeError,"KEY_MISSING"):
     social.model_json("style",{"one":"item"})
   call.assert_not_called()

if __name__=="__main__":unittest.main()
