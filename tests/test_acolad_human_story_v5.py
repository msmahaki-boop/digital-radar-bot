import copy,json,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image,ImageDraw

import acolad_human_story_v5 as h
import acolad_v5_visual as visual

EXAMPLE=Path("examples/acolad_human_story_v5_returns_example.json")

class HumanStoryV5QA(unittest.TestCase):
 def setUp(self):
  self.story=json.loads(EXAMPLE.read_text(encoding="utf8"))
  self.sources=self.story["sources"]

 def test_nine_beats_are_source_labeled_and_human(self):
  self.assertEqual(h.validate(self.story,self.sources),[])
  self.assertEqual(len(self.story["slides"]),9)
  self.assertTrue(all(35<=h.word_count(s["text"])<=65
                      for s in self.story["slides"]))
  self.assertTrue(all("**" in s["overlay"] for s in self.story["slides"]))
  self.assertEqual(sum(s["scene_id"]==3 for s in self.story["slides"]),3)

 def test_no_real_paper_claim_about_fictional_customer(self):
  bad=copy.deepcopy(self.story)
  bad["fictional_example"]=False
  self.assertIn("FICTIONAL_EXAMPLE_NOT_LABELED",h.validate(bad,self.sources))
  bad=copy.deepcopy(self.story)
  bad["slides"][0]["text"]=bad["slides"][0]["text"].replace("فرض کن ","")
  self.assertIn("HYPOTHETICAL_CHARACTER_PRESENTED_AS_REAL",
                h.validate(bad,self.sources))

 def test_native_captions_are_three_different_acts_and_never_repeat_full_text(self):
  for net in ("telegram","bale"):
   parts=h.thread_parts(self.story,net)
   self.assertEqual(len(parts),3)
   self.assertNotIn("روایت آکولاد |", "".join(parts))
   self.assertNotIn("از ۳", "".join(parts))
   self.assertIn("اولین جایی که محمد",parts[0])
   self.assertIn("حالا پیچ قصه",parts[1])
   self.assertIn("یعنی چهار تغییر",parts[2])
   self.assertLess(len(parts[0]),986)
   self.assertEqual(sum(p.count("اولین جایی که محمد") for p in parts),1)
   self.assertNotIn("](","".join(parts))
   self.assertIn("کانال "+("تلگرام" if net=="telegram" else "بله"),parts[2])

 def test_rejects_unknown_source_or_uncited_factual_statement(self):
  bad=copy.deepcopy(self.story)
  bad["source_url"]="https://invalid.example/fabricated-study"
  self.assertIn("SOURCE_URL_NOT_IN_VERIFIED_INPUT",h.validate(bad,self.sources))
  bad=copy.deepcopy(self.story)
  bad["slides"][5]["source_ids"]=[]
  self.assertIn("SLIDE_6_FACT_WITHOUT_SOURCE",h.validate(bad,self.sources))

 def test_overlay_freeze_scene_ids_and_actions(self):
  storyboard=h.visual_story(self.story)
  self.assertEqual(len(storyboard["slides"]),9)
  for i,s in enumerate(storyboard["slides"]):
   self.assertEqual(s["scene_id"],i//3+1)
   self.assertEqual(s["visual_action"],"new_scene" if i%3==0 else "add_text")
   self.assertEqual(s["text"],self.story["slides"][i]["overlay"])
   self.assertNotEqual(s["text"],self.story["slides"][i]["text"])

 def test_separate_square_cover_has_four_iransans_weights_available(self):
  # Mock illustration demonstrates compositor geometry only; not provider provenance.
  with TemporaryDirectory() as d:
   art=Path(d)/"scene_01.png"
   im=Image.new("RGBA",(1024,1024),(255,255,255,0))
   ImageDraw.Draw(im).ellipse((250,200,760,780),fill=(20,20,20,255))
   im.save(art,"PNG")
   data=visual.social_cover(art,self.story["title"],Path(d)/"social_cover_square.png")
   self.assertTrue(data["story_frame_reused"] is False)
   self.assertEqual(data["size"],[1080,1080])
   self.assertIn("Black",data["weights"])
   for weight in ("Regular","Medium","Bold","Black"):
    self.assertIsNotNone(visual.font(weight,28))
   with Image.open(Path(d)/"social_cover_square.png") as photo:
    self.assertEqual(photo.size,(1080,1080))

if __name__=="__main__":unittest.main()
