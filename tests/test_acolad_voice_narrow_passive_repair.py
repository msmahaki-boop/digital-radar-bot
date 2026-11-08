import unittest

import acolad_daily_editorial_v1 as editorial
from acolad_voice_v4_guard import audience_issues

class FormalPassiveNarrowRepairQA(unittest.TestCase):
    def test_only_voice_passive_changes_and_preserves_source(self):
        story={"story_link":"https://example.org/primary-source",
               "slides":[{"n":1,"text":"نتایج آزمایش سال ۲۰۲۶ بررسی شد اما میزان اثر نامعلومه",
                          "source_ids":["source-1"],"scene_id":1},
                         {"n":2,"text":"این ادعا رو نمی‌شه بدون شاهد قطعی دونست",
                          "source_ids":["source-1"],"scene_id":1}]}
        fixed,changed=editorial.repair_colloquial_passive_without_new_claims(story)
        self.assertTrue(changed)
        self.assertNotIn("FORMAL_1",audience_issues(fixed["slides"][0]["text"]))
        self.assertEqual(fixed["slides"][0]["source_ids"],["source-1"])
        self.assertEqual(fixed["slides"][0]["scene_id"],1)
        self.assertIn("۲۰۲۶",fixed["slides"][0]["text"])
        self.assertEqual(fixed["story_link"],story["story_link"])
        self.assertEqual(story["slides"][0]["text"],"نتایج آزمایش سال ۲۰۲۶ بررسی شد اما میزان اثر نامعلومه")

    def test_unsupported_claim_not_repaired_or_hidden(self):
        story={"slides":[{"n":1,"text":"مشتری حس کرد سرش کلاه رفته"}]}
        fixed,changed=editorial.repair_colloquial_passive_without_new_claims(story)
        self.assertFalse(changed)
        self.assertEqual(fixed,story)

    def test_story_prompt_requires_evidence_based_closed_ending(self):
        from datetime import date
        instruction=editorial.narrative_prompts(date(2026,11,8))
        self.assertIn("آخرین فریم نباید",instruction)
        self.assertIn("قابل‌آزمایش",instruction)
        self.assertIn("هیچ عدد",instruction)

    def test_only_actual_passive_phrases(self):
        story={"slides":[{"n":1,"text":"این طرح در شهر دیده شده و نتیجه ارائه شد"}]}
        fixed,changed=editorial.repair_colloquial_passive_without_new_claims(story)
        self.assertTrue(changed)
        self.assertNotIn("FORMAL_1",audience_issues(fixed["slides"][0]["text"]))

if __name__=="__main__":
    unittest.main()
