import json
import unittest
from pathlib import Path
import acolad_daily_ai_ink_stories_v1 as art

class SceneSpecificAIImageTests(unittest.TestCase):
    def test_scene_metaphor_beats_general_news_title(self):
        topic="خرید اینترنتی با حساب کاربری قفل‌شده"
        self.assertIn("magnifying glass",
            art.editorial_english_motif("دو نسخه مقایسه A/B برای نرخ تکمیل",topic))
        self.assertIn("key",
            art.editorial_english_motif("کلید پنهان پشت پرده",topic))
    def test_daily_episode_has_distinct_image_intents(self):
        story=json.loads(Path("examples/acolad_new_daily_episode_guest_checkout_20261103.json").read_text(encoding="utf8"))
        from acolad_concept_art_pipeline_v2 import image_scenes,image_metaphor
        scenes=image_scenes(story)
        motifs=[art.editorial_english_motif(image_metaphor(story,i),story.get("topic","")) for i in scenes]
        self.assertGreaterEqual(len(set(motifs)),2)
    def test_image_budget_and_no_publish(self):
        self.assertEqual(art.CAP_SCENES,4)
        self.assertEqual(art.LICENSE,"creativeml-openrail-m")

if __name__=="__main__":
    unittest.main()
