import json,unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import acolad_telegram_continue_existing_48 as t

class ExistingPhotoReplyQA(unittest.TestCase):
    def story(self):
        return {"slides":[{"n":i,"scene_id":1+(i-1)//2,"text":
                "روایت تاییدشده درباره تجربه مشتری و وب‌سایت؛ داده‌ها به منبع واقعی نسبت داده می‌شن."} for i in range(1,9)]}

    def test_root_must_be_real_remote_telegram_message_48(self):
        good={"id":3699384,"post":[{"account_id":233472,"status":"published",
          "accountPost":{"post_id":"48","permalink":"https://t.me/acoladagency/48"}}]}
        with patch.object(t,"provider_list",return_value=[good]):
            self.assertTrue(t.verify_root_from_provider("mock",date(2026,11,8)))
        good["post"][0]["accountPost"]["post_id"]="47"
        with patch.object(t,"provider_list",return_value=[good]):
            with self.assertRaisesRegex(RuntimeError,"NOT_PROVIDER_VERIFIED"):
                t.verify_root_from_provider("mock",date(2026,11,8))

    def test_two_replies_to_verified_root_no_new_photo_and_dedupe(self):
        with TemporaryDirectory() as folder:
            out=Path(folder);(out/"story.json").write_text(
               json.dumps(self.story(),ensure_ascii=False),encoding="utf8")
            results=iter([{"message_id":49,"reply_to_message":{"message_id":48}},
                          {"message_id":50,"reply_to_message":{"message_id":48}}])
            seen=[]
            def fake_call(net,bot,method,*,data):
                seen.append((net,method,dict(data)))
                return next(results)
            with patch.object(t,"datetime") as clock,\
                 patch.object(t,"OUT",out),patch.object(t,"RECEIPT",out/"receipt.json"),\
                 patch.object(t,"verify_owner_release_artifact",return_value={}),\
                 patch.object(t,"verify_root_from_provider",return_value=True),\
                 patch.object(t,"token",return_value="mock"),\
                 patch.object(t,"credentials",return_value=("mock","@acoladagency")),\
                 patch.object(t,"access_preflight",return_value=True),\
                 patch.object(t,"_call",side_effect=fake_call),\
                 patch.object(t.time,"sleep",return_value=None):
                clock.now.return_value.date.return_value=date(2026,11,8)
                receipt=t.continue_verified_telegram()
                self.assertEqual(receipt["message_ids"],[49,50])
                self.assertEqual(receipt["state"],"PUBLISHED")
                self.assertTrue(receipt["published"])
                self.assertEqual([method for _,method,_ in seen],["sendMessage","sendMessage"])
                self.assertEqual([args["reply_to_message_id"] for _,_,args in seen],[48,48])
                with self.assertRaisesRegex(RuntimeError,"NEVER_BLIND_RETRY"):
                    t.continue_verified_telegram()

    def test_wrong_remote_parent_fails_closed(self):
        with TemporaryDirectory() as folder:
            out=Path(folder);(out/"story.json").write_text(
               json.dumps(self.story(),ensure_ascii=False),encoding="utf8")
            with patch.object(t,"datetime") as clock,\
                 patch.object(t,"OUT",out),patch.object(t,"RECEIPT",out/"receipt.json"),\
                 patch.object(t,"verify_owner_release_artifact",return_value={}),\
                 patch.object(t,"verify_root_from_provider",return_value=True),\
                 patch.object(t,"token",return_value="mock"),\
                 patch.object(t,"credentials",return_value=("mock","@acoladagency")),\
                 patch.object(t,"access_preflight",return_value=True),\
                 patch.object(t,"_call",return_value={"message_id":49,
                      "reply_to_message":{"message_id":47}}):
                clock.now.return_value.date.return_value=date(2026,11,8)
                with self.assertRaisesRegex(RuntimeError,"WRONG_ROOT"):
                    t.continue_verified_telegram()
                state=json.loads((out/"receipt.json").read_text())
                self.assertFalse(state["published"])

if __name__=="__main__":
    unittest.main()
