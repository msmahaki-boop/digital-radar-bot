import unittest
from unittest.mock import patch,Mock
import acolad_v4_daily_autopublish as copy
import acolad_v4_hourly_publish as live

class FooterRules(unittest.TestCase):
 def test_telegram_footer_has_telegram_not_bale(self):
  f=copy.footer_for("telegram")
  self.assertIn("@acoladagency",f)
  self.assertIn("کانال تلگرام",f)
  self.assertNotIn("کانال بله",f)
  self.assertNotIn("[",f)
  self.assertNotIn("](",f)
 def test_bale_footer_has_bale_not_telegram(self):
  f=copy.footer_for("bale")
  self.assertIn("@acoladagency",f)
  self.assertIn("کانال بله",f)
  self.assertNotIn("کانال تلگرام",f)
  self.assertNotIn("t.me",f)
  self.assertNotIn("](",f)
 def test_existing_markdown_links_cannot_escape_into_new_public_copy(self):
  old="🌐 [acolad.ir](https://acolad.ir/)\n📢 [@acoladagency](https://t.me/acoladagency)"
  cleaned=copy.clean_old_markup(old)
  self.assertIn("acolad.ir",cleaned)
  self.assertIn("@acoladagency",cleaned)
  self.assertNotIn("](",cleaned)
 def test_hourly_ready_verifies_each_network_footer(self):
  import inspect
  source=inspect.getsource(live.existing_bundle)
  self.assertIn("footer_for",source)
  self.assertNotIn("endswith(engine.FOOTER)",source)
 def test_send_now_removes_legacy_md_before_novinhub(self):
  def fakepost(*args,**kwargs):
   self.assertNotIn("](",kwargs["json"]["caption"])
   return Mock(status_code=201,json=lambda:{"data":{"id":52}})
  with patch.object(live.requests,"post",side_effect=fakepost):
   ident=live.send_now("dummy","bale",
     "قبول شد\n🌐 [acolad.ir](https://acolad.ir/)",[])
  self.assertEqual(ident,52)
 def test_bale_image_post_attaches_one_verified_media_id(self):
  def fakepost(*args,**kwargs):
   payload=kwargs["json"]
   self.assertEqual(payload["type"],"image")
   self.assertEqual(payload["media_ids"],[774])
   self.assertEqual(payload["account_ids"],[live.ACCOUNT["bale"]])
   return Mock(status_code=201,json=lambda:{"data":{"id":54}})
  with patch.object(live.requests,"post",side_effect=fakepost), \
       patch.dict(live.os.environ,{"ACOLAD_REQUIRE_REAL_GPT25_ART":"1"}):
   self.assertEqual(live.send_now("dummy","bale","متن کامل", [774]),54)
 def test_strict_telegram_image_missing_blocks_before_api_post(self):
  with patch.dict(live.os.environ,{"ACOLAD_REQUIRE_REAL_GPT25_ART":"1"}), \
       patch.object(live.requests,"post") as network:
   with self.assertRaisesRegex(ValueError,"cover image required"):
    live.send_now("dummy","telegram","متن کامل",[])
   network.assert_not_called()
 def test_strict_provenance_rejects_pillow_drawings(self):
  import json
  from tempfile import TemporaryDirectory
  from pathlib import Path
  with TemporaryDirectory() as d:
   Path(d,"image_provenance.json").write_text(json.dumps([
    {"scene":1,"original_procedural":True}]),encoding="utf8")
   with patch.object(live,"OUT",Path(d)):
    with self.assertRaisesRegex(RuntimeError,"NOT_MODEL_GENERATED"):
     live.verify_real_gpt25_art()
if __name__=="__main__":unittest.main()
