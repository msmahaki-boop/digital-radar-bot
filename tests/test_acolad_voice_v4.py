import copy,json,unittest
from acolad_voice_v4_guard import (ROOT,check_carousel,check_progressive,audience_issues)

def data(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))

class AcoladVoiceV4Tests(unittest.TestCase):
    def test_owner_style_carousel_passes_mechanical_gate_only(self):
        x=check_carousel(data("voice_v4_return_button_carousel.json"))
        self.assertTrue(x["passed"],x["issues"])
        self.assertFalse(x["publication_allowed"])
        self.assertEqual(x["human_score"],"UNASSESSED")
    def test_user_progressive_version_is_separate(self):
        x=check_progressive(data("voice_v4_return_button_progressive.json"))
        self.assertTrue(x["passed"],x["issues"])
        self.assertFalse(x["publication_allowed"])
    def test_pushpin_rejected(self):
        self.assertIn("LEAK_0",audience_issues("📌 این‌ها پیشنهاد آزمایشن"))
    def test_emotional_emoji_is_accepted(self):
        self.assertEqual(audience_issues("😕 محمد مونده از کجا باید کار رو شروع کنه!"),[])
    def test_formal_bookish_language_rejected(self):
        self.assertIn("FORMAL_0",audience_issues("با این کار مشکل حل می‌شود"))
        self.assertIn("FORMAL_1",audience_issues("این رفتار در جلسه‌ای مشاهده شد"))
    def test_unverified_duration_rejected(self):
        self.assertIn("UNSUPPORTED_0",audience_issues("پونزده دقیقه کل سایت رو گشت"))
        self.assertIn("UNSUPPORTED_1",audience_issues("مهلت هفت روزه تموم شده بود"))
    def test_definite_emotions_not_assumed(self):
        self.assertIn("UNSUPPORTED_2",audience_issues("مشتری حس کرد سرش کلاه رفته"))
    def test_name_must_be_fictional(self):
        x=data("voice_v4_return_button_carousel.json")
        x["character"]["fictional"]=False
        self.assertIn("FICTIONAL_CHARACTER_NOT_LABELED",check_carousel(x)["issues"])
    def test_breaking_chronology_rejected(self):
        x=data("voice_v4_return_button_carousel.json")
        x["slides"][0]["beat"]="reveals_cause"
        self.assertIn("BROKEN_CHRONOLOGY",check_carousel(x)["issues"])
    def test_causes_must_be_based_on_research(self):
        x=data("voice_v4_return_button_carousel.json")
        x["slides"][3]["body"]="خب اتفاق افتاد و ماجرا ادامه داشت"
        self.assertIn("CAUSE_NOT_REVEALED",check_carousel(x)["issues"])
    def test_hypothetical_feeling_must_be_labeled(self):
        x=data("voice_v4_return_button_carousel.json")
        x["slides"][4]["body"]=x["slides"][4]["body"].replace("شاید","قطعا")
        self.assertIn("HYPOTHETICAL_FEELING_UNLABELED",check_carousel(x)["issues"])
    def test_business_impact_should_not_be_asserted_as_observed(self):
        x=data("voice_v4_return_button_carousel.json")
        x["slides"][5]["body"]=x["slides"][5]["body"].replace("ممکنه","قطعاً")
        self.assertIn("UNVERIFIED_BUSINESS_IMPACT_NOT_HEDGED",check_carousel(x)["issues"])
    def test_source_url_cannot_go_into_public_caption(self):
        self.assertIn("LEAK_1",audience_issues("برای اطلاعات بیشتر https://baymard.com"))
    def test_technical_marker_rejected(self):
        self.assertIn("LEAK_2",audience_issues("ACOLAD-TEST-AB12"))
    def test_overlong_caption_is_a_layout_problem(self):
        x=data("voice_v4_return_button_carousel.json")
        x["slides"][1]["body"]="این جمله فقط فضا را می‌گیرد "*95
        self.assertIn("BAD_PARAGRAPH_LENGTH_2",check_carousel(x)["issues"])
    def test_word_minimum_is_not_forced_back_on_to_user(self):
        x=data("voice_v4_return_button_carousel.json")
        self.assertTrue(any(len(s["body"].split())<35 for s in x["slides"]))
        self.assertTrue(check_carousel(x)["passed"])
    def test_duplicate_numbering_rejected_in_progressive(self):
        x=data("voice_v4_return_button_progressive.json")
        x["frames"][3]["n"]=1
        self.assertIn("PROGRESSIVE_SCENE_ORDER_4",check_progressive(x)["issues"])
    def test_change_is_not_a_publish_permission(self):
        x=data("voice_v4_return_button_carousel.json")
        x["status"]="PUBLISHED"
        self.assertIn("PUBLICATION_NOT_GATED",check_carousel(x)["issues"])

if __name__=="__main__":
    unittest.main()
