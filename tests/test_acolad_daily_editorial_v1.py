import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import acolad_daily_editorial_v1 as daily
import acolad_concept_art_pipeline_v2 as art

STORY=Path("examples/acolad_new_daily_episode_guest_checkout_20261103.json")

class DailyEditorialTests(unittest.TestCase):
    def setUp(self):
        self.story=json.loads(STORY.read_text(encoding="utf-8"))
    def test_seven_editorial_pillars_really_present(self):
        self.assertEqual(len(daily.TOPICS),7)
        self.assertIn("iran_economy",daily.TOPICS)
        self.assertIn("social",daily.TOPICS)
    def test_hook_rotates_with_dates(self):
        today=dt.date(2026,11,3)
        hooks=[daily.selected_style(today+dt.timedelta(days=i))[0] for i in range(7)]
        self.assertEqual(len(set(hooks)),7)
        self.assertIn("morning",hooks)
    def test_no_fixed_mehdi_in_dynamic_template(self):
        self.assertIn("نام «مهدی»",daily.narrative_prompts(dt.date(2026,11,3)))
        self.assertTrue(daily.story_is_distinct(self.story))
    def test_factual_sources_exposed_for_human_review(self):
        self.assertGreaterEqual(len(self.story["sources"]),2)
        self.assertTrue(all(s.get("url","").startswith("https://baymard.com/")
                            for s in self.story["sources"]))
        self.assertTrue(all(s.get("verification") for s in self.story["sources"]))
    def test_image_slots_meaningful(self):
        scenes=art.image_scenes(self.story)
        self.assertTrue(scenes)
        self.assertLessEqual(len(scenes),4)
        self.assertTrue(set(scenes).issubset({x["scene_id"] for x in self.story["slides"]}))
        self.assertLess(len(scenes),len(self.story["slides"]))
    def test_original_transparent_illustration_when_api_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"scene_02.png"
            report=art.ink_sketch(2,"در قفل و خرید مهمان",path)
            self.assertTrue(path.exists())
            from PIL import Image
            with Image.open(path) as image:
                self.assertEqual(image.size,(1024,1024))
                self.assertEqual(image.getextrema()[3][0],0)
            self.assertEqual(report["status"],"ORIGINAL_PROCEDURAL_PNG")
    def test_paid_requests_never_exceed_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ",{"GEMINI_API_KEY":""}):
                result=art.create_art(self.story,Path(tmp),allow_paid=True)
            self.assertEqual(result["image_api_calls"],0)
            self.assertTrue(all(Path(v["path"]).exists()
                         for v in result["providers"]
                         if v["status"]=="ORIGINAL_PROCEDURAL_PNG"))
    def test_image_budget_and_no_automatic_publish(self):
        self.assertEqual(art.MAX_IMAGE_REQUESTS,1)
        self.assertEqual(art.MAX_TOMAN,20000)
        self.assertFalse("novinhub" in art.HOST.lower())
        self.assertEqual(self.story["publication_permission"],"PREVIEW_ONLY")
    def test_account_creation_stat_scope_not_iran(self):
        first=self.story["sources"][0]["claim"].lower()
        self.assertIn("us",first)
        self.assertNotIn("iran",first)
    def test_daily_intake_no_paid_model_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(daily.news,"collect_sources",return_value=[
                {"id":"S01","title":"تجربه مشتری در سایت","publisher":"نمونه",
                 "date":"2026-11-03","url":"https://example.org/a",
                 "evidence_depth":"summary_only","source_type":"rss_summary",
                 "rank":10}]):
                with patch.object(daily.news,"suggested_evidence_pairs",return_value=[]):
                    report=daily.write_intake(dt.date(2026,11,3),Path(tmp))
                    self.assertEqual(report["model_calls"],0)
                    self.assertEqual(report["drafts"],0)
                    self.assertEqual(len(report["categories"]),7)
                    self.assertTrue((Path(tmp)/"DAILY_BRIEF_FA.md").exists())

if __name__=="__main__":unittest.main()
