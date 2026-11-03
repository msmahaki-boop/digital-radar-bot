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
    def test_remove_unnecessary_publisher_showmanship_without_claim_changes(self):
        story=json.loads(STORY.read_text(encoding="utf-8"))
        story["slides"][2]["text"]="گزارش دیجیاتو می‌گه اسنپ‌مارکت این عادت رو هدف گرفت"
        before=[frame.get("source_ids") for frame in story["slides"]]
        revised,changed=daily.repair_unnecessary_publisher_mentions(story)
        self.assertTrue(changed)
        self.assertEqual(revised["slides"][2]["text"],
            "در گزارش منتشرشده اومده که اسنپ‌مارکت این عادت رو هدف گرفت")
        self.assertEqual(before,[frame.get("source_ids") for frame in revised["slides"]])

    def test_model_every_frame_new_scene_gets_genuine_frozen_text(self):
        story=json.loads(STORY.read_text(encoding="utf-8"))
        for frame in story["slides"]:
            frame["scene_id"]=frame["n"]
            frame["visual_action"]="new_scene"
        changed,was_patched=daily.repair_all_new_scenes(story)
        self.assertTrue(was_patched)
        self.assertEqual(story["slides"][1]["visual_action"],"new_scene")
        self.assertEqual(changed["slides"][1]["visual_action"],"add_text")
        self.assertEqual(changed["slides"][0]["scene_id"],changed["slides"][1]["scene_id"])
        self.assertEqual(
            [s["text"] for s in changed["slides"]],
            [s["text"] for s in story["slides"]])
        self.assertEqual(
            [s["source_ids"] for s in changed["slides"]],
            [s["source_ids"] for s in story["slides"]])

    def test_recent_story_is_not_chosen_again_for_next_daily_episode(self):
        today=dt.date(2026,11,3)
        sources=[
            {"id":"S01","title":"گزارش الف","source_type":"rss_summary",
             "evidence_depth":"full_article","url":"https://example.com/repeated"},
            {"id":"S02","title":"گزارش ب","source_type":"rss_summary",
             "evidence_depth":"full_article","url":"https://example.com/new"},
            {"id":"S03","title":"Academic evidence","source_type":"academic_doi",
             "evidence_depth":"abstract","url":"https://doi.org/10.1/new"},
        ]
        history=[{"url":"https://example.com/repeated","date":today.isoformat()}]
        result=daily.unseen_recent_articles(sources,history,[])
        self.assertEqual(len(result),2)
        self.assertNotIn("https://example.com/repeated",[s["url"] for s in result])
        self.assertEqual(result[0]["id"],"S01")

    def test_reject_advertorial_and_unsourced_brand_campaign_as_independent_news(self):
        samples=[
            {"title":"کمپین جدید برند الف","url":"https://news.example/a",
             "excerpt":"اجرای کمپین با مشارکت ۱۱ برند"},
            {"title":"راهنمای خرید","url":"https://example.com/promoted/item",
             "excerpt":"محصول و مزایا"},
            {"title":"گزارش تست مستقل فروشگاه","url":"https://example.org/independent",
             "excerpt":"آزمایش مستقل با سنجه واقعی"},
        ]
        self.assertTrue(daily.is_promotional_source(samples[0]))
        self.assertTrue(daily.is_promotional_source(samples[1]))
        self.assertFalse(daily.is_promotional_source(samples[2]))

    def test_missing_conflict_is_repaired_by_relabeling_only(self):
        original={"slides":[
            {"n":1,"beat":"hook","text":"فرض کن صبح از خواب پاشدی"},
            {"n":2,"beat":"evidence","text":"یک گزارش چیز تازه‌ای نشون داده"},
            {"n":3,"beat":"discovery","text":"اما این گزارش نتیجه فروش نهایی رو نشون نمی‌ده"},
            {"n":4,"beat":"action","text":"آمار سفارش رو اندازه بگیر"},
            {"n":5,"beat":"payoff","text":"تصمیم رو با شواهد بگیر"}]}
        repaired,changed=daily.repair_missing_conflict_beat(original)
        self.assertTrue(changed)
        self.assertEqual(repaired["slides"][2]["beat"],"conflict")
        self.assertEqual([x["text"] for x in original["slides"]],
                         [x["text"] for x in repaired["slides"]])
        self.assertEqual(original["slides"][2]["beat"],"discovery")

    def test_corrupt_history_is_safe_and_no_credentials_are_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            original=daily.HISTORY
            daily.HISTORY=Path(tmp)/"history.json"
            try:
                daily.HISTORY.write_text("invalid json",encoding="utf-8")
                self.assertEqual(daily.read_history(dt.date(2026,11,3)),[])
            finally:
                daily.HISTORY=original

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
