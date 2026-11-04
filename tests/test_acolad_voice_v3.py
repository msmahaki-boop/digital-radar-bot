import json,unittest
from pathlib import Path
from acolad_voice_v3_guard import check_carousel,check_progressive,audience_errors,ROOT

def load(filename):
 return json.loads((ROOT/filename).read_text(encoding="utf-8"))

class VoiceV3Regression(unittest.TestCase):
 def test_nine_independent_slides_35_to_65_words(self):
  story=load("voice_v3_return_button_carousel.json")
  r=check_carousel(story)
  self.assertTrue(r["passed"],r["issues"])
  self.assertFalse(r["publish_allowed"])
  self.assertEqual(r["human_score"],"UNASSESSED")

 def test_nine_progressive_frames_in_three_scenes(self):
  x=check_progressive(load("voice_v3_return_button_progressive.json"))
  self.assertTrue(x["passed"],x["issues"])
  self.assertFalse(x["publish_allowed"])

 def test_old_passive_machine_translation_rejected(self):
  self.assertIn("BOOKISH_FORMAL_PASSIVE",audience_errors("این صحنه در یک آزمون واقعی دیده شد"))
  self.assertIn("BOOKISH_TRANSLATED",audience_errors("از نگاه سیستم، گزینه‌ای حذف شد"))

 def test_bookish_formal_verb_rejected(self):
  self.assertIn("BOOKISH_FORMAL_VERB",audience_errors("و سپس مشخص می‌شود که این امکان وجود ندارد"))

 def test_15_minutes_unsubstantiated_rejected(self):
  self.assertIn("INVENTED_FACT_DURATION_15MIN",audience_errors("پونزده دقیقه کل سایت رو زیرورو کرد"))

 def test_seven_day_limit_unsubstantiated_rejected(self):
  self.assertIn("INVENTED_FACT_RETURN_7DAYS",audience_errors("مهلت هفت روزه مرجوعی تمام شد"))

 def test_unsubstantiated_cheated_emotion_rejected(self):
  self.assertIn("INVENTED_FACT_DEFINITE_CHEATED_FEELING",audience_errors("مشتری حس کرد سرش کلاه رفته"))

 def test_speculative_reader_emotion_allowed(self):
  self.assertEqual(audience_errors("اگه جای اون بودی شاید می‌گفتی نکنه قایمش کردن"),[])

 def test_raw_sources_and_internal_ids_rejected(self):
  self.assertIn("LEAK_SOURCE_URL",audience_errors("https://baymard.com/research"))
  self.assertIn("LEAK_TECHNICAL_MARKER",audience_errors("ACOLAD-NARRATIVE-20261104"))

 def test_original_inverted_chronology_rejected(self):
  s=load("voice_v3_return_button_carousel.json")
  s["slides"][0]["text"]="💭 دکمه مرجوعی نبود! بعد سفارش رو باز کرد\n\n📌 "+s["slides"][0]["text"]
  s["slides"][0]["words"]=len(s["slides"][0]["text"].split())
  self.assertIn("CHRONOLOGY_RESULT_BEFORE_ACTION",check_carousel(s)["issues"])

 def test_missing_source_evidence_rejected(self):
  s=load("voice_v3_return_button_carousel.json")
  del s["evidence"]
  self.assertIn("FIRST_PARTY_EVIDENCE_MISSING",check_carousel(s)["issues"])

 def test_draft_gate_cannot_be_enabled_by_technical_pass(self):
  s=load("voice_v3_return_button_carousel.json")
  s["publication"]="PUBLISHED"
  self.assertIn("UNSAFE_PUBLICATION_STATUS",check_carousel(s)["issues"])

 def test_accumulation_not_accepted_as_carousel(self):
  s=load("voice_v3_return_button_carousel.json")
  s["slides"][1]["text"]="📌 یه جمله کوتاه"
  self.assertTrue(any("SLIDE_2_WORD_COUNT" in x for x in check_carousel(s)["issues"]))

 def test_bad_progressive_scene_order_rejected(self):
  s=load("voice_v3_return_button_progressive.json")
  s["frames"][4]["scene_id"]=3
  self.assertIn("FRAME_5_SCENE_OR_ORDER",check_progressive(s)["issues"])

if __name__=="__main__":unittest.main()
