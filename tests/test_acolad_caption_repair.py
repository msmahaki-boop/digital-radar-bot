import unittest
from unittest.mock import patch
import acolad_v4_daily_autopublish as p

class CaptionRetry(unittest.TestCase):
 def test_bad_instagram_caption_is_rewritten_only_for_that_channel(self):
  tg="داستان واقعی و قابل فهم درباره خرید آنلاین و یک مشکل روشن. "*9
  bale="مشتری رفت تو سایت و متوجه شد مسیر خرید سخت شده. "*7
  bad="📌 کپشن مشکل دار"
  good="😕 مشتری فقط می‌خواست خریدش رو تموم کنه، اما سایت جلوش یه مانع اضافی گذاشته بود! می‌شه این مسیر رو با چند نفر امتحان کرد."
  self.assertFalse(p.channel_copy_issues("instagram",good,60,500))
  outputs=[{"telegram":tg,"bale":bale,"instagram":bad},{"instagram":good}]
  with patch.object(p,"model_json",side_effect=outputs) as model:
   res=p.make_channel_copies({"slides":[{"text":"یک روایت اصلی"}]},[{"title":"Original","excerpt":"Evidence"}])
  self.assertEqual(model.call_count,2)
  self.assertTrue(res["telegram"].endswith(p.FOOTER))
  self.assertTrue(res["bale"].endswith(p.footer_for("bale")))
  self.assertEqual(res["instagram"],good)
 def test_two_bad_rewrites_remain_blocked(self):
  tg="این یک متن با شواهد معتبر است و درباره تجربه خرید مشتری صحبت می‌کنه. "*9
  bale="این یه روایت معتبر و قابل فهم درباره تجربه خرید مشتریه. "*8
  with patch.object(p,"model_json",side_effect=[
   {"telegram":tg,"bale":bale,"instagram":"📌 بد"},
   {"instagram":"📌 بد"},
   {"instagram":"📌 بد"}]):
   with self.assertRaisesRegex(RuntimeError,"LOW_QUALITY_OR_INVALID_COPY_instagram"):
    p.make_channel_copies({"slides":[]},[])
 def test_external_sources_cannot_be_in_public_caption(self):
  self.assertIn("SOURCE_LEAK",p.channel_copy_issues("instagram","https://example.com",60,500))
 def test_formal_or_pinned_tone_is_rejected(self):
  self.assertIn("FORMAL_OR_UNSAFE_TONE",p.channel_copy_issues("instagram",
   "📌 این روایت بد است اما چیزی باقی می‌ماند و منتظر می‌شود"*3,60,500))

if __name__=="__main__":unittest.main()
