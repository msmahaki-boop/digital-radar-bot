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
if __name__=="__main__":unittest.main()
