import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
import acolad_story_image_ladder as m

class Story:
    def __init__(self,topic):
        self.topic=topic;self.title_fa="آزمایش مسیر خرید در فروشگاه اینترنتی"
        self.original_title="How ecommerce checkout visibility affects shopping carts"
        self.summary_fa="فرض کن مشتری گزینه پرداخت را پیدا نمی‌کند و خرید ناقص می‌ماند"
        self.image=None;self.image_status=""

class TestVisual(unittest.TestCase):
    def test_first_provider_is_gpt_image_2(self):
        self.assertEqual(m.MODELS[0],"gpt-image-2")
    def test_fallback_order(self):
        self.assertEqual(m.MODELS,("gpt-image-2","gemini-2.5-flash-image","gapgpt/qwen-image-2.1"))
    def test_only_two_images_in_five_slides(self):
        rows=[Story(str(i)) for i in range(4)]
        class Image: pass
        with TemporaryDirectory() as d,patch.object(m,"OUTPUT",Path(d)),patch.object(m,"attempt",return_value=(Image(),{"status":"VALID_IMAGE","model":"gpt-image-2"})) as call:
            m.enrich_images(rows)
        self.assertEqual(call.call_count,2)
        self.assertEqual([i for i,s in enumerate(rows) if s.image is not None],[0,2])
    def test_all_models_fail_then_text(self):
        rows=[Story(str(i)) for i in range(4)]
        with TemporaryDirectory() as d,patch.object(m,"OUTPUT",Path(d)),patch.object(m,"attempt",return_value=(None,{"status":"API_HTTP_ERROR","http_status":503})),patch.object(m,"safe_stock",return_value=(None,{"status":"NO_MATCH"})),patch.object(m,"commons_stock",return_value=(None,{"status":"COMMONS_NO_MATCH"})):
            result=m.enrich_images(rows)
        self.assertEqual(result["images_used"],0)
        self.assertEqual(rows[0].image_status,"TEXT_ONLY_NO_RELEVANT_IMAGE")
    def test_stock_after_three_failed_models(self):
        rows=[Story(str(i)) for i in range(4)]
        class Image:pass
        with TemporaryDirectory() as d,patch.object(m,"OUTPUT",Path(d)),patch.object(m,"attempt",return_value=(None,{"status":"API_HTTP_ERROR"})) as calls,patch.object(m,"safe_stock",return_value=(Image(),{"status":"LICENSED_STOCK_CANDIDATE"})):
            result=m.enrich_images(rows)
        self.assertEqual(calls.call_count,6)
        self.assertEqual(result["images_used"],2)
        self.assertEqual(rows[0].image_status,"LICENSED_STOCK")
if __name__=="__main__":unittest.main()
