import importlib.util
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]/'telegram_daily_v4.py'
spec = importlib.util.spec_from_file_location('telegram_daily_v4', MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TestV4(unittest.TestCase):
    def test_8_slots_7_topics(self):
        now = datetime(2026, 10, 25, 10, 12, tzinfo=ZoneInfo('Asia/Tehran'))
        self.assertEqual(m.TOPIC_ORDER, ('tech','ai','iran_economy','marketing','small_business_growth','iran_platforms','social','best_of_day'))
        self.assertEqual([m.slot_from_now(now, h)[2] for h in m.HOURS], list(m.TOPIC_ORDER))
    def test_categories_from_config(self):
        data = m.load_new_sources()
        for topic in ('iran_economy','small_business_growth','iran_platforms'):
            self.assertGreater(len(data[topic]), 0)
    def test_filter_commodities_and_small_business(self):
        self.assertFalse(m.relevant('iran_economy', {'title':'قیمت مرغ امروز', 'excerpt':'خبر روز'}))
        self.assertFalse(m.relevant('small_business_growth', {'title':'ترکیب پرسپولیس مقابل فولاد', 'excerpt':''}))
        self.assertTrue(m.relevant('small_business_growth', {'title':'کمپین جدید فروشگاه آنلاین', 'excerpt':'خرید مشتری'}))
        self.assertTrue(m.relevant('iran_platforms', {'title':'کمپین اسنپ شاپ', 'excerpt':'افزایش سفارش'}))
    def test_semantic_duplicate(self):
        self.assertTrue(m.same_story('اسنپ و دیجی‌کالا بالاترین امتیاز تجربه کاربری را کسب کردند', 'دیجی‌کالا و اسنپ بالاترین امتیاز تجربه کاربری کسب کردند'))
        self.assertFalse(m.same_story('افزایش قیمت برنج در بازار', 'اسنپ‌شاپ کمپین بلک فرایدی را آغاز کرد'))

if __name__ == '__main__': unittest.main()
