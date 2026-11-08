import unittest
import acolad_daily_editorial_v1 as ed

class DenseProgressiveRepairQA(unittest.TestCase):
 def test_split_dense_frames_without_rewriting_any_word_or_source(self):
  frames=[]
  for i in range(1,9):
   count=29 if i==3 else 34 if i==8 else 11
   frames.append({"n":i,"text":" ".join(["واژه"+str(i)]*count),
    "source_ids":["id"+str(i)],"beat":"evidence",
    "scene_id":i,"visual_action":"new_scene","visual_idea":"تحلیل یک نمودار"})
  original={"slides":frames,"story_link":"https://example.com/primary"}
  result,changed=ed.repair_dense_frame_as_progressive_reveal(original,
   ["frame 3: 29 new words make this frame too dense",
    "frame 8: 34 new words make this frame too dense"])
  self.assertTrue(changed)
  self.assertEqual(len(result["slides"]),10)
  self.assertEqual([x["n"] for x in result["slides"]],list(range(1,11)))
  self.assertEqual(result["story_link"],original["story_link"])
  for i in (3,8):
   pieces=[x for x in result["slides"] if x.get("source_ids")==["id"+str(i)]]
   self.assertEqual(len(pieces),2)
   self.assertEqual(sum(len(x["text"].split()) for x in pieces),
       29 if i==3 else 34)
   self.assertEqual(pieces[1]["visual_action"],"add_text")
   self.assertEqual(pieces[0]["scene_id"],pieces[1]["scene_id"])
   self.assertEqual(" ".join(x["text"] for x in pieces).split(),
       original["slides"][i-1]["text"].split())
  self.assertEqual(len(original["slides"]),8)
 def test_unrelated_errors_do_not_trigger_shortening(self):
  story={"slides":[{"n":1,"text":"هیچ متن اضافی نیست"}]}
  output,changed=ed.repair_dense_frame_as_progressive_reveal(
    story,["cinema: ending reopens unresolved question"])
  self.assertFalse(changed)
  self.assertEqual(output,story)
 def test_refuses_too_many_frames(self):
  story={"slides":[{"n":i,"text":" ".join(["کلمه"]*33)} for i in range(1,16)]}
  output,changed=ed.repair_dense_frame_as_progressive_reveal(
    story,["frame 3: 33 new words make this frame too dense"])
  self.assertFalse(changed)
  self.assertEqual(output,story)
if __name__=="__main__":
 unittest.main()
