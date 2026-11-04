import json,unittest
from pathlib import Path
from acolad_voice_v4_guard import audience_issues,check_progressive

PATH=Path("editorial/previews/acolad_guest_checkout_v4_20261104.json")
FOOTER="🌐 [acolad.ir](https://acolad.ir/)\n📢 کانال تلگرام: [@acoladagency](https://t.me/acoladagency)\nارتباط و مشاوره: [@acolad_agency](https://t.me/acolad_agency)"

class PreviewContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=json.loads(PATH.read_text(encoding="utf8"))
    def test_preview_not_scheduled_or_published(self):
        d=self.d
        self.assertFalse(d["publication_allowed"])
        self.assertEqual([d["social_writes"],d["novinhub_drafts_created"],d["published"],d["scheduled"]],[0,0,0,0])
        self.assertEqual(d["human_quality_score"],"UNASSESSED")
    def test_nine_progressive_story_frames_with_real_beats(self):
        frames=self.d["frames"]
        self.assertEqual(len(frames),9)
        s={"status":"PREVIEW_ONLY","approved_by_owner":False,
           "character":{"fictional":True},
           "frames":[{"n":f["frame"],"scene_id":f["scene"],
                      "action":"new_scene" if f["frame"]%3==1 else "add_text",
                      "added_text":f["added_text"]} for f in frames]}
        gate=check_progressive(s)
        self.assertTrue(gate["passed"],gate["issues"])
        self.assertFalse(gate["publication_allowed"])
    def test_footers_are_exact_and_are_at_end_of_both_posts(self):
        for net in ("telegram","bale"):
            text=self.d["captions"][net]
            self.assertTrue(text.endswith(FOOTER),net)
            self.assertEqual(text.count(FOOTER),1,net)
        self.assertEqual(self.d["captions"]["footer"],FOOTER)
    def test_no_pin_no_accidental_source_leak(self):
        for k in ("instagram","telegram","bale"):
            t=self.d["captions"][k]
            self.assertNotIn("📌",t)
            self.assertNotIn("baymard.com",t.lower())
            self.assertNotIn("ACOLAD-NOVINHUB",t)
        for x in self.d["frames"]:
            self.assertFalse(audience_issues(x["added_text"]),x)
    def test_primary_source_stored_private(self):
        p=self.d["provenance"]
        self.assertIn("baymard.com",p["source_url_internal_only"])
        self.assertTrue(p["fictional_character_disclosed"])
        self.assertFalse(self.d["illustration_state"]["art_available_in_repo"])
    def test_no_unsupported_impact_claims(self):
        blob=self.d["captions"]["telegram"]+" "+self.d["captions"]["bale"]
        for claim in ("افزایش قطعی فروش","تضمینی","۱۵ دقیقه","هفت روزه"):
            self.assertNotIn(claim,blob)
    def test_post_lengths_suitable_for_manual_review(self):
        self.assertLess(len(self.d["captions"]["bale"]),900)
        self.assertLess(len(self.d["captions"]["telegram"]),2000)
if __name__=="__main__": unittest.main()
