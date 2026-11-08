import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import acolad_v4_daily_autopublish as pipeline
import acolad_gpt25_strict_renderer as strict


class StrictPipelineTests(unittest.TestCase):
    def story(self):
        return {"slides":[
            {"n":1,"scene_id":1,"visual_action":"new_scene","visual_idea":"a tiny store owner"},
            {"n":2,"scene_id":2,"visual_action":"new_scene","visual_idea":"a line chart"}]}

    def test_live_feature_gate_calls_only_strict_layer(self):
        with patch.dict(os.environ,{"ACOLAD_REQUIRE_REAL_GPT25_ART":"1"}):
            with patch.object(strict,"illustrate_strict",return_value=(["image"],[])) as generate:
                result=pipeline.illustrate(self.story())
        self.assertEqual(result,(["image"],[]))
        generate.assert_called_once()

    def test_real_pillow_alpha_verify_order_does_not_false_fail(self):
        from PIL import Image, ImageDraw
        with TemporaryDirectory() as root:
            path=Path(root)/"genuine.png"
            image=Image.new("RGBA",(1024,1024),(255,255,255,0))
            ImageDraw.Draw(image).ellipse((300,280,725,770),fill=(15,15,15,255))
            image.save(path,"PNG")
            self.assertTrue(strict.verify_generated_alpha_file(path))

    def test_solid_opaque_png_still_refused(self):
        from PIL import Image
        with TemporaryDirectory() as root:
            path=Path(root)/"bad.png"
            Image.new("RGBA",(1024,1024),(255,255,255,255)).save(path,"PNG")
            with self.assertRaisesRegex(RuntimeError,"GPT25_ALPHA_NOT_TRANSPARENT"):
                strict.verify_generated_alpha_file(path)

    def test_no_procedural_fallback_after_api_403(self):
        with TemporaryDirectory() as root:
            with patch.object(strict,"CONCEPT_DIR",Path(root)/"cutouts"), \
                 patch.object(strict,"generate_scenes",side_effect=RuntimeError("IMAGE_PROVIDER_HTTP_403")), \
                 patch.object(strict,"render") as visual:
                with self.assertRaisesRegex(RuntimeError,"HTTP_403"):
                    strict.illustrate_strict(self.story())
                visual.assert_not_called()

    def test_repeated_scene_id_rejected_before_billing(self):
        bad=self.story()
        bad["slides"][1]["scene_id"]=1
        with patch.object(strict,"generate_scenes") as api:
            with self.assertRaisesRegex(ValueError,"New scene reused"):
                strict.illustrate_strict(bad)
            api.assert_not_called()

    def test_above_strict_max_scenes_rejected_before_billing(self):
        story={"slides":[{"n":i,"scene_id":i,"visual_action":"new_scene"} for i in range(1,strict.MAX_IMAGES+2)]}
        with patch.object(strict,"generate_scenes") as api:
            with self.assertRaisesRegex(RuntimeError,"DISTINCT_SCENE_COUNT"):
                strict.illustrate_strict(story)
            api.assert_not_called()


if __name__=="__main__":
    unittest.main()
