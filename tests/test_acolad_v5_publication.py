import json,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import acolad_v5_publication as p

DOC=Path("examples/acolad_human_story_v5_returns_example.json")

class V5PublicationSafetyQA(unittest.TestCase):
 def setUp(self):
  self.story=json.loads(DOC.read_text(encoding="utf8"))
 def mock_paths(self,d):
  self.root=Path(d)
  return [patch.object(p,"ROOT",self.root),
          patch.object(p,"INTENTS",self.root/"intents.json"),
          patch.object(p,"RECEIPTS",self.root/"receipts.json")]
 def test_genuine_native_three_messages_reply_to_one_independent_photo(self):
  with TemporaryDirectory() as d:
   from contextlib import ExitStack
   out=Path(d)/"social_cover_square.png"
   out.write_bytes(b"only-a-mocked-upload-path")
   observed=[]
   nextids=iter((601,602,603))
   def fake_call(net,bot,method,*,data,media=None):
    observed.append((net,method,dict(data),media))
    return {"message_id":next(nextids),
            "reply_to_message":{"message_id":601}}
   with ExitStack() as st:
    for cm in self.mock_paths(d):st.enter_context(cm)
    st.enter_context(patch.dict(p.os.environ,{"BOT_TOKEN":"mock-secret"}))
    st.enter_context(patch.object(p,"credentials",return_value=("mock","@acoladagency")))
    st.enter_context(patch.object(p,"access_preflight",return_value=True))
    st.enter_context(patch.object(p,"_call",side_effect=fake_call))
    p._native_three_parts("telegram",self.story,out)
   self.assertEqual([x[1] for x in observed],["sendPhoto","sendMessage","sendMessage"])
   self.assertEqual(observed[0][3],out)
   self.assertEqual([x[2]["reply_to_message_id"] for x in observed[1:]],[601,601])
   self.assertNotIn("روایت آکولاد |",observed[0][2]["caption"])
   receipts=json.loads((Path(d)/"receipts.json").read_text())
   self.assertEqual(receipts["network"]["telegram"]["status"],"PUBLISHED")
   self.assertEqual(receipts["network"]["telegram"]["message_ids"],[601,602,603])
   self.assertTrue(receipts["network"]["telegram"]["publication_verified"])

 def test_partial_remote_timeout_persists_id_and_prevents_blind_replay(self):
  with TemporaryDirectory() as d:
   from contextlib import ExitStack
   cover=Path(d)/"cover.png";cover.touch()
   called=[]
   def fake_call(*args,**kwargs):
    called.append(args[2])
    if len(called)==1:return {"message_id":701}
    raise RuntimeError("NATIVE_REMOTE_TIMEOUT")
   with ExitStack() as st:
    for cm in self.mock_paths(d):st.enter_context(cm)
    st.enter_context(patch.dict(p.os.environ,{"BOT_TOKEN":"mock-secret"}))
    st.enter_context(patch.object(p,"credentials",return_value=("mock","@acoladagency")))
    st.enter_context(patch.object(p,"access_preflight",return_value=True))
    st.enter_context(patch.object(p,"_call",side_effect=fake_call))
    with self.assertRaisesRegex(RuntimeError,"NATIVE_REMOTE_TIMEOUT"):
     p._native_three_parts("telegram",self.story,cover)
    self.assertTrue(p._attempted("telegram"))
   receipt=json.loads((Path(d)/"receipts.json").read_text())
   self.assertEqual(receipt["network"]["telegram"]["message_ids"],[701])
   self.assertFalse(receipt["network"]["telegram"]["publication_verified"] if
       "publication_verified" in receipt["network"]["telegram"] else False)

 def test_provider_bale_is_three_chapters_but_never_claims_native_reply(self):
  with TemporaryDirectory() as d:
   from contextlib import ExitStack
   with ExitStack() as st:
    for cm in self.mock_paths(d):st.enter_context(cm)
    st.enter_context(patch.object(p,"upload_file",return_value=800))
    st.enter_context(patch.object(p,"send_now",side_effect=[991,992,993])) as send:
     st.enter_context(patch.object(p.time,"sleep",return_value=None))
     p._bale_via_novinhub("mock",self.story,Path(d)/"cover.png")
     self.assertEqual(send.call_count,3)
     self.assertEqual([a.args[1] for a in send.call_args_list],["bale"]*3)
     self.assertEqual(send.call_args_list[0].args[3],[800])
     self.assertEqual(send.call_args_list[1].args[3],[])
     self.assertEqual(send.call_args_list[2].args[3],[])
   data=json.loads((Path(d)/"receipts.json").read_text())["network"]["bale"]
   self.assertEqual(data["status"],"SUBMITTED_NOT_PROVEN_PUBLISHED")
   self.assertFalse(data["native_reply_to_first"])
   self.assertFalse(data["publication_verified"])

 def test_duplicate_story_in_novinhub_readonly_check_blocks_post(self):
  with patch.object(p,"provider_list",return_value=[
       {"id":1,"post":[{"caption":"محمد مرجوعی بایمرد پژوهش"}]}]):
   self.assertTrue(p._provider_seen_story("mock","bale"))
  with patch.object(p,"provider_list",return_value=[
       {"id":1,"post":[{"caption":"تحلیل سرعت سایت آکولاد متفاوت"}]}]):
   self.assertFalse(p._provider_seen_story("b","bale"))

 def test_instagram_creator_validation_never_claims_publication(self):
  with TemporaryDirectory() as d:
   from contextlib import ExitStack
   from acolad_v4_hourly_publish import ProviderValidationRejected
   with ExitStack() as st:
    for cm in self.mock_paths(d):st.enter_context(cm)
    st.enter_context(patch.object(p,"_provider_seen_story",return_value=False))
    st.enter_context(patch.object(p,"upload_file",return_value=99))
    st.enter_context(patch.object(p,"send_now",
            side_effect=ProviderValidationRejected("HTTP 400"))) as send:
     p._instagram("mock",self.story,[Path(d)/f"story{i}.png" for i in range(9)])
     send.assert_called_once()
   receipt=json.loads((Path(d)/"receipts.json").read_text())["network"]["instagram"]
   self.assertEqual(receipt["status"],"HTTP_400_NOT_PUBLISHED")
   self.assertFalse(receipt["publication_verified"])

if __name__=="__main__":unittest.main()
