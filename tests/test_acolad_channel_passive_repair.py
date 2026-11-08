import unittest

from acolad_v4_daily_autopublish import colloquialize_safe_inflections, channel_copy_issues

class ChannelPassiveQA(unittest.TestCase):
    def test_only_register_changed_and_source_numerals_preserved(self):
        source="در گزارش ۲۰۲۶ نتیجه بررسی شد و در آزمایش، داده‌ها ارائه شده اما قطعیت نداره."
        fixed=colloquialize_safe_inflections(source)
        self.assertIn("۲۰۲۶",fixed)
        self.assertIn("قطعیت نداره",fixed)
        self.assertNotIn("بررسی شد",fixed)
        self.assertNotIn("ارائه شده",fixed)
        self.assertEqual(channel_copy_issues("telegram",fixed,5,500),[])

    def test_claim_not_rewritten(self):
        source="مشتری حس کرد سرش کلاه رفته"
        fixed=colloquialize_safe_inflections(source)
        self.assertEqual(source,fixed)
        self.assertIn("FORMAL_OR_UNSAFE_TONE",channel_copy_issues("bale",fixed,3,250))

if __name__=="__main__":
    unittest.main()
