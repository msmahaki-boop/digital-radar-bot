import base64
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

import acolad_gapgpt_transparent_art as art


class TransparentImageQA(unittest.TestCase):
    def story(self):
        return {"slides":[{"scene_id":1,"visual_idea":"A store owner puzzled by a large maze of shopping carts."}]}

    def png(self, alpha=True):
        im = Image.new("RGBA" if alpha else "RGB", (1024,1024),
                       (0,0,0,0) if alpha else (255,255,255))
        d=ImageDraw.Draw(im)
        d.ellipse((250,200,770,830),fill=(16,18,21,255) if alpha else (0,0,0))
        out=io.BytesIO()
        im.save(out,format="PNG")
        return out.getvalue()

    def test_expected_provider_model_and_background(self):
        self.assertEqual(art.MODEL,"gpt-image-2.5-sunburst")
        self.assertIn("transparent",art.prompt_for_scene(self.story(),1))
        self.assertIn("No text",art.prompt_for_scene(self.story(),1))
        api=Mock(status_code=200)
        api.json.return_value={"data":[{"b64_json":base64.b64encode(self.png()).decode()}]}
        session=Mock(post=Mock(return_value=api))
        with TemporaryDirectory() as root:
            report=art.generate(self.story(),1,Path(root)/"scene_01.png",session,key="mock")
            self.assertTrue(report["real_ai_generated"])
            self.assertGreater(report["transparent_fraction"],0.12)
            with Image.open(Path(root)/"scene_01.png") as img:
                self.assertIn("A",img.getbands())
                self.assertEqual(img.getpixel((0,0))[3],0)
        payload=session.post.call_args.kwargs["json"]
        self.assertEqual(payload["model"],art.MODEL)
        self.assertEqual(payload["background"],"transparent")
        self.assertEqual(payload["output_format"],"png")

    def test_opaque_white_poster_never_accepted(self):
        with self.assertRaisesRegex(ValueError,"NO_REAL_ALPHA_CHANNEL"):
            art.verify_png(self.png(alpha=False))

    def test_fake_solid_rgba_never_accepted(self):
        raw=io.BytesIO()
        Image.new("RGBA",(1024,1024),(255,255,255,255)).save(raw,"PNG")
        with self.assertRaisesRegex(ValueError,"NOT_A_VISIBLE_TRANSPARENT_CUTOUT"):
            art.verify_png(raw.getvalue())

    def test_image_http_error_fails_closed(self):
        response=Mock(status_code=403)
        with TemporaryDirectory() as root:
            with self.assertRaisesRegex(RuntimeError,"IMAGE_PROVIDER_HTTP_403"):
                art.generate(self.story(),1,Path(root)/"scene_01.png",
                             Mock(post=Mock(return_value=response)),key="mock")
            self.assertEqual(list(Path(root).glob("*.png")),[])

    def test_missing_catalog_model_does_not_buy_images(self):
        session=Mock()
        session.get.return_value=Mock(status_code=200)
        session.get.return_value.json.return_value={"data":[{"id":"gpt-image-2"}]}
        with patch.dict(art.os.environ,{"GAPGPT_API_KEY":"mock"}):
            with TemporaryDirectory() as root:
                with self.assertRaisesRegex(RuntimeError,"NOT_IN_MODEL_CATALOG"):
                    art.generate_scenes(self.story(),[1],Path(root),session=session)
        session.post.assert_not_called()

    def test_limit_four_scenes(self):
        with self.assertRaisesRegex(RuntimeError,"SCENE_COUNT_OUT_OF_RANGE"):
            art.generate_scenes(self.story(),[1,2,3,4,5])

    def test_no_ai_art_with_json_url_only(self):
        response=Mock(status_code=200)
        response.json.return_value={"data":[{"url":"https://example.com/image.png"}]}
        with TemporaryDirectory() as root:
            with self.assertRaisesRegex(RuntimeError,"NO_BASE64"):
                art.generate(self.story(),1,Path(root)/"scene_01.png",
                             Mock(post=Mock(return_value=response)),key="mock")


if __name__=="__main__":
    unittest.main()
