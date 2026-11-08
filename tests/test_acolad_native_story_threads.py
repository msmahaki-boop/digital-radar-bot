import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock,patch

from PIL import Image
import acolad_native_story_threads as t


class NativeThreadQA(unittest.TestCase):
 def story(self):
  return {"slides":[{"n":i,"scene_id":i,"text":"این بخش از یک روایت تاییدشده درباره تجربه مشتری و فروشگاه آنلاین است."} for i in range(1,8)]}
 def test_three_parts_and_network_specific_footer(self):
  a=t.segments(self.story(),"telegram")
  b=t.segments(self.story(),"bale")
  self.assertEqual(len(a),3)
  self.assertEqual(len(b),3)
  self.assertIn("کانال تلگرام: @acoladagency",a[-1])
  self.assertIn("کانال بله: @acoladagency",b[-1])
  self.assertNotIn("t.me",b[-1])
  self.assertNotIn("](",a[-1])
  self.assertNotIn("](",b[-1])
 def test_no_bale_token_never_sends(self):
  with patch.dict(t.os.environ,{"BALE_BOT_TOKEN":"","BALE_CHANNEL_ID":"@acoladagency"}):
   with self.assertRaisesRegex(RuntimeError,"SECRET_OR_CHANNEL_MISSING"):
    t.credentials("bale")
 def test_three_messages_reply_to_first_and_receipts(self):
  with TemporaryDirectory() as temp:
   cover=Path(temp)/"story_01.png"
   Image.new("RGB",(1080,1920),"white").save(cover,"PNG")
   results=[{"id":77},{"id":-100,"type":"channel"},{"status":"administrator","can_post_messages":True},
            {"message_id":345},{"message_id":346},{"message_id":347}]
   call_args=[]
   def fake_call(net,bot,method,*,data,media=None,session=None):
    call_args.append({"method":method,"data":dict(data),"media":media})
    return results.pop(0)
   with patch.object(t,"_call",side_effect=fake_call),patch.object(t,"credentials",return_value=("fake","@acoladagency")),patch.dict(t.os.environ,{"ACOLAD_TEST_CLOCK":"1"}):
    result=t.publish_thread("telegram",self.story(),cover,date(2026,11,8),state_dir=Path(temp))
    self.assertEqual(result["state"],"PUBLISHED")
    self.assertEqual(result["message_ids"],[345,346,347])
    self.assertTrue(result["publication_verified"])
    self.assertEqual([x["method"] for x in call_args[3:]],["sendPhoto","sendMessage","sendMessage"])
    self.assertEqual(call_args[4]["data"]["reply_to_message_id"],345)
    self.assertEqual(call_args[5]["data"]["reply_to_message_id"],345)
    with self.assertRaisesRegex(RuntimeError,"ALREADY_ATTEMPTED"):
     t.publish_thread("telegram",self.story(),cover,date(2026,11,8),state_dir=Path(temp))
 def test_partial_thread_blocks_blind_replay(self):
  with TemporaryDirectory() as temp:
   cover=Path(temp)/"story_01.png"
   Image.new("RGB",(1080,1920),"white").save(cover,"PNG")
   def fail_after_first(*args,**kw):
    if args[2]=="sendPhoto":return {"message_id":50}
    raise RuntimeError("NATIVE_REMOTE_TIMEOUT")
   with patch.object(t,"access_preflight",return_value=True),patch.object(t,"_call",side_effect=fail_after_first),patch.object(t,"credentials",return_value=("fake","@acoladagency")),patch.dict(t.os.environ,{"ACOLAD_TEST_CLOCK":"1"}):
    with self.assertRaisesRegex(RuntimeError,"NATIVE_REMOTE_TIMEOUT"):
     t.publish_thread("telegram",self.story(),cover,date(2026,11,8),state_dir=Path(temp))
    status=json.loads((Path(temp)/"native_telegram_receipt.json").read_text())
    self.assertEqual(status["message_ids"],[50])
    self.assertFalse(status["publication_verified"])
    with self.assertRaisesRegex(RuntimeError,"ALREADY_ATTEMPTED"):
     t.publish_thread("telegram",self.story(),cover,date(2026,11,8),state_dir=Path(temp))
 def test_not_admin_blocks_before_photo(self):
  returns=[{"id":1},{"type":"channel"},{"status":"member"}]
  with patch.object(t,"_call",side_effect=lambda *a,**k:returns.pop(0)):
   with self.assertRaisesRegex(RuntimeError,"NOT_CHANNEL_ADMIN"):
    t.access_preflight("bale","mock","@acoladagency")
if __name__=="__main__":unittest.main()
