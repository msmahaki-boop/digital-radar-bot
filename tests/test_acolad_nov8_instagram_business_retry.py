import json,unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import acolad_nov8_instagram_business_retry as retry

class InstagramOnlyRecoveryQA(unittest.TestCase):
 def setup_files(self,root):
  for i in range(1,9):
   (root/"frames").mkdir(exist_ok=True)
   (root/"frames"/f"story_{i:02d}.png").write_bytes(b"fake-offline-media")
  (root/"hourly_ready.json").write_text(json.dumps({
   "nframes":8,"captions":{"instagram":"Source-reviewed Persian IG description with all required factual guards."}}),encoding="utf8")
 def context(self,root):
  return [patch.object(retry,"datetime"),patch.object(retry,"ROOT",root),
   patch.object(retry,"INTENT",root/"intent.json"),
   patch.object(retry,"STATUS",root/"status.json"),
   patch.object(retry,"verify_owner_release_artifact",return_value={}),
   patch.object(retry,"token",return_value="mock-token")]

 def test_explicit_creator_400_safe_no_published_claim(self):
  from contextlib import ExitStack
  with TemporaryDirectory() as d:
   root=Path(d);self.setup_files(root)
   with ExitStack() as st:
    contexts=self.context(root)
    for c in contexts:st.enter_context(c)
    retry.datetime.now.return_value.date.return_value=date(2026,11,8)
    st.enter_context(patch.object(retry,"provider_list",return_value=[]))
    st.enter_context(patch.object(retry,"assess",return_value={"state":"ABSENT"}))
    with patch.object(retry,"upload_file",side_effect=list(range(1,9))) as upload,\
         patch.object(retry,"send_now",side_effect=retry.ProviderValidationRejected("400")) as send:
     result=retry.run()
    self.assertEqual(result["status"],"CREATOR_ACCOUNT_REJECTED_CONNECT_INSTAGRAM_BUSINESS")
    self.assertFalse(result["publication_verified"])
    self.assertEqual(upload.call_count,8)
    send.assert_called_once()
    self.assertEqual(send.call_args.args[1],"instagram")
    self.assertEqual(json.loads((root/"intent.json").read_text())["state"],"REJECTED_VALIDATION_400")

 def test_existing_accepted_intent_never_resends(self):
  from contextlib import ExitStack
  with TemporaryDirectory() as d:
   root=Path(d);self.setup_files(root)
   (root/"intent.json").write_text(json.dumps({"day":"2026-11-08","state":"ACCEPTED"}))
   with ExitStack() as st:
    for c in self.context(root):st.enter_context(c)
    retry.datetime.now.return_value.date.return_value=date(2026,11,8)
    st.enter_context(patch.object(retry,"provider_list",return_value=[]))
    st.enter_context(patch.object(retry,"assess",return_value={"state":"ABSENT"}))
    with patch.object(retry,"upload_file") as upload,patch.object(retry,"send_now") as send:
     outcome=retry.run()
    self.assertIn("NO_BLIND_RETRY",outcome["status"])
    upload.assert_not_called();send.assert_not_called()

 def test_existing_published_remote_is_success_without_post(self):
  from contextlib import ExitStack
  with TemporaryDirectory() as d:
   root=Path(d)
   with ExitStack() as st:
    for c in self.context(root):st.enter_context(c)
    retry.datetime.now.return_value.date.return_value=date(2026,11,8)
    st.enter_context(patch.object(retry,"provider_list",return_value=[{"id":52}]))
    st.enter_context(patch.object(retry,"assess",return_value={"state":"PUBLISHED","ids":[52]}))
    with patch.object(retry,"upload_file") as upload,patch.object(retry,"send_now") as send:
     result=retry.run()
    self.assertTrue(result["publication_verified"])
    upload.assert_not_called();send.assert_not_called()

 def test_expired_date_never_calls_any_external_api(self):
  from contextlib import ExitStack
  with TemporaryDirectory() as d:
   with ExitStack() as st:
    for c in self.context(Path(d)):st.enter_context(c)
    retry.datetime.now.return_value.date.return_value=date(2026,11,9)
    with patch.object(retry,"provider_list") as get,patch.object(retry,"send_now") as post:
     result=retry.run()
    self.assertEqual(result["status"],"DATE_EXPIRED_NO_REQUEST")
    get.assert_not_called();post.assert_not_called()

if __name__=="__main__":
 unittest.main()
