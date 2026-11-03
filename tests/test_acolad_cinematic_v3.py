import json
from pathlib import Path
import unittest
from PIL import Image,ImageDraw
import acolad_narrative_visual_v2 as r
import acolad_concept_image_gapgpt_preview as api

STORY=Path("examples/acolad_narrative_v2_fixed_demo.json")

class NarrativeV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r.check_assets()
        cls.story=json.loads(STORY.read_text(encoding="utf8"))
    def test_clarified_copy_no_ambiguity(self):
        self.assertEqual(self.story["slides"][1]["text"],
             "آمار بازدید سایت بالاست\nولی **سبد خریدها خالیه!** 🤔")
    def test_more_legible_centered_size(self):
        self.assertEqual(r.TEXT_X,540)
        self.assertLess(max(r.FONT_SIZES),74)
    def test_highlight_variants_and_phrase_grouping(self):
        self.assertGreaterEqual(len(r.HIGHLIGHT_INKS),4)
        row=[("سبد",True),("خریدها",True),("خالیه",False)]
        runs=r._row_runs(row)
        self.assertEqual(runs[0],("سبد خریدها",True,False))
    def test_full_scene_preplanned_not_recentered(self):
        group=r.scene_chunks(self.story)[0]
        layouts=r.plan_scene([frame["added_text"] for frame in group])
        self.assertEqual(layouts[0]["size"],layouts[1]["size"])
        self.assertLess(layouts[0]["y"],layouts[1]["y"])
    def test_image_budget_rejects_unapproved(self):
        with self.assertRaises(ValueError):
            api.prepare_request(2,0.081)
        with self.assertRaises(ValueError):
            api.prepare_request(3,0.08)
        req,expected=api.prepare_request(2,.08)
        self.assertEqual(req["n"],1)
        self.assertEqual(req["quality"],"low")
        self.assertEqual(req["model"],"gpt-image-1-mini")
        self.assertLess(expected,.08)
    def test_no_publication_side_effects(self):
        import inspect
        for module in (r,api):
            text=inspect.getsource(module)
            self.assertNotIn("api.novinhub.com",text)
            self.assertNotIn("api.telegram.org",text)
    def test_illustration_layer_bounds(self):
        im=Image.new("RGBA",(1080,1920),(255,250,247,255))
        art=Image.new("RGBA",(600,600),(255,255,255,0))
        d=ImageDraw.Draw(art)
        d.line((40,100,520,480),fill=(0,0,0,255),width=13)
        r.add_concept_illustration(im,art)
        self.assertEqual(im.size,(1080,1920))

if __name__=="__main__":unittest.main()
