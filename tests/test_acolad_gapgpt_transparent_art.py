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
        self.assertEqual(art.MODEL,"gpt-image-2.5-flare")
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

    def test_precise_gapgpt_per_key_quota_blocks_without_art(self):
        response=Mock(status_code=403)
        response.json.return_value={"error":{"code":"pre_consume_token_quota_failed"}}
        with TemporaryDirectory() as root:
            dest=Path(root)/"scene_01.png"
            with self.assertRaisesRegex(RuntimeError,"PRECONSUME_QUOTA_BLOCKED"):
                art.generate(self.story(),1,dest,
                             Mock(post=Mock(return_value=response)),key="mock")
            self.assertFalse(dest.exists())

    def test_gapgpt_documented_image_url_is_supported(self):
        response=Mock(status_code=200)
        response.json.return_value={"data":[{"url":"https://images.example.com/art.png"}]}
        image_response=Mock(status_code=200,content=self.png())
        session=Mock(post=Mock(return_value=response),get=Mock(return_value=image_response))
        with TemporaryDirectory() as root:
            report=art.generate(self.story(),1,Path(root)/"scene_01.png",session,key="mock")
            self.assertEqual(report["image_response"],"provider_url")
            self.assertTrue(Path(root,"scene_01.png").exists())
        self.assertEqual(session.get.call_args.args[0],"https://images.example.com/art.png")
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])

    def test_image_url_localhost_refused_before_download(self):
        session=Mock()
        with self.assertRaisesRegex(RuntimeError,"UNSAFE_HOST"):
            art.read_provider_image({"url":"https://localhost/private.png"},session)
        session.get.assert_not_called()

    def test_gapgpt_https_redirect_to_cdn_is_bounded(self):
        redirected=Mock(status_code=302,headers={"Location":"https://cdn.example.com/generated.png"})
        image=Mock(status_code=200,content=self.png())
        session=Mock()
        session.get.side_effect=[redirected,image]
        result,origin=art.read_provider_image({"url":"https://images.example.com/start"},session)
        self.assertEqual(origin,"provider_url")
        self.assertGreater(len(result),100)
        self.assertEqual(session.get.call_count,2)
    def test_gapgpt_redirect_to_local_network_rejected(self):
        redirected=Mock(status_code=302,headers={"Location":"http://localhost/image"})
        session=Mock()
        session.get.return_value=redirected
        with self.assertRaisesRegex(RuntimeError,"NOT_SAFE_HTTPS"):
            art.read_provider_image({"url":"https://images.example.com/start"},session)
        self.assertEqual(session.get.call_count,1)

    def test_actual_gpt_black_ink_on_white_can_be_knocked_out_without_new_art(self):
        from PIL import ImageDraw
        src=Image.new("RGB",(1024,1024),"white")
        draw=ImageDraw.Draw(src)
        draw.ellipse((300,250,720,780),outline="black",width=14)
        raw=io.BytesIO()
        src.save(raw,"PNG")
        converted=art.white_paper_to_alpha_for_real_ai_drawing(raw.getvalue())
        image,stats=art.verify_png(converted)
        self.assertGreater(stats["transparent_fraction"],0.12)
        self.assertEqual(image.getpixel((0,0))[3],0)
        self.assertGreater(image.getpixel((300,500))[3],0)

    def test_white_blank_is_not_accepted_as_real_ai_line_art(self):
        blank=io.BytesIO()
        Image.new("RGB",(1024,1024),"white").save(blank,"PNG")
        with self.assertRaisesRegex(ValueError,"NOT_A_SPARSE"):
            art.white_paper_to_alpha_for_real_ai_drawing(blank.getvalue())

    def test_provider_opaque_ink_art_is_reported_as_genuine_art_with_alpha_postprocess(self):
        from PIL import ImageDraw
        src=Image.new("RGB",(1024,1024),"white")
        d=ImageDraw.Draw(src)
        d.rectangle((260,250,760,770),outline="black",width=20)
        raw=io.BytesIO()
        src.save(raw,"PNG")
        response=Mock(status_code=200)
        response.json.return_value={"data":[{"b64_json":base64.b64encode(raw.getvalue()).decode()}]}
        with TemporaryDirectory() as root:
            dest=Path(root)/"scene_01.png"
            report=art.generate(self.story(),1,dest,Mock(post=Mock(return_value=response)),key="mock")
            self.assertEqual(report["transparency_method"],"white_paper_knockout_on_gpt_generated_art")
            self.assertTrue(report["real_ai_generated"])
            with Image.open(dest) as im:
                self.assertIn("A",im.getbands())
                self.assertEqual(im.getpixel((0,0))[3],0)

    def test_missing_catalog_model_does_not_buy_images(self):
        session=Mock()
        session.get.return_value=Mock(status_code=200)
        session.get.return_value.json.return_value={"data":[{"id":"gpt-image-2"}]}
        with patch.dict(art.os.environ,{"GAPGPT_API_KEY":"mock"}):
            with TemporaryDirectory() as root:
                with self.assertRaisesRegex(RuntimeError,"NOT_IN_MODEL_CATALOG"):
                    art.generate_scenes(self.story(),[1],Path(root),session=session)
        session.post.assert_not_called()

    def test_stricter_gpt_api_prompt_after_alpha_failure(self):
        from unittest.mock import patch
        original=art.prompt_for_scene(self.story(),1)
        response=Mock(status_code=200)
        response.json.return_value={"data":[{"b64_json":base64.b64encode(self.png()).decode()}]}
        session=Mock(post=Mock(return_value=response))
        with TemporaryDirectory() as root:
            art.generate(self.story(),1,Path(root)/"a.png",session,key="mock",alpha_retry=1)
        submitted=session.post.call_args.kwargs["json"]
        self.assertIn(original,submitted["prompt"])
        self.assertIn("STRICT CUTOUT CORRECTION 1",submitted["prompt"])
        self.assertEqual(submitted["model"],"gpt-image-2.5-flare")
        self.assertEqual(submitted["background"],"transparent")

    def test_alpha_retries_only_actual_gpt_generations_and_records_count(self):
        with patch.dict(art.os.environ,{"GAPGPT_API_KEY":"safe-test"}), \
             patch.object(art,"models_available",return_value=True), \
             patch.object(art,"generate",side_effect=[
                ValueError("NOT_A_VISIBLE_TRANSPARENT_CUTOUT"),
                ValueError("AI_IMAGE_NOT_A_SPARSE_WHITE_PAPER_INK_DRAWING"),
                {"path":"scene_01.png","real_ai_generated":True,
                 "transparent_fraction":0.64,"model":"gpt-image-2.5-flare"}]) as api:
            with TemporaryDirectory() as root:
                manifest=art.generate_scenes(self.story(),[1],Path(root))
        self.assertEqual(api.call_count,3)
        self.assertEqual([x.kwargs["alpha_retry"] for x in api.call_args_list],[0,1,2])
        self.assertEqual(manifest["records"][0]["transparent_image_attempts"],3)
        self.assertEqual(manifest["procedural_assets"],0)

    def test_three_failed_alphas_block_without_procedural_substitute(self):
        with patch.dict(art.os.environ,{"GAPGPT_API_KEY":"safe-test"}), \
             patch.object(art,"models_available",return_value=True), \
             patch.object(art,"generate",
                          side_effect=ValueError("NOT_A_VISIBLE_TRANSPARENT_CUTOUT")) as api:
            with TemporaryDirectory() as root:
                with self.assertRaisesRegex(RuntimeError,"REAL_GPT_IMAGE_ALPHA_EXHAUSTED_SCENE_1"):
                    art.generate_scenes(self.story(),[1],Path(root))
                self.assertFalse((Path(root)/"transparent_ai_provenance.json").exists())
        self.assertEqual(api.call_count,3)

    def test_quota_error_never_retries_image_api(self):
        with patch.dict(art.os.environ,{"GAPGPT_API_KEY":"safe-test"}), \
             patch.object(art,"models_available",return_value=True), \
             patch.object(art,"generate",side_effect=RuntimeError(
                          "GAPGPT_IMAGE_KEY_PRECONSUME_QUOTA_BLOCKED")) as api:
            with TemporaryDirectory() as root:
                with self.assertRaisesRegex(RuntimeError,"PRECONSUME_QUOTA_BLOCKED"):
                    art.generate_scenes(self.story(),[1],Path(root))
        api.assert_called_once()

    def test_limit_max_ten_scenes(self):
        with self.assertRaisesRegex(RuntimeError,"SCENE_COUNT_OUT_OF_RANGE"):
            art.generate_scenes(self.story(),list(range(1,art.MAX_IMAGES+2)))

    def test_no_ai_art_with_json_url_only(self):
        response=Mock(status_code=200)
        response.json.return_value={"data":[{"url":"https://example.com/image.png"}]}
        with TemporaryDirectory() as root:
            with self.assertRaisesRegex(RuntimeError,"IMAGE_RETURN_DOWNLOAD_HTTP_"):
                art.generate(self.story(),1,Path(root)/"scene_01.png",
                             Mock(post=Mock(return_value=response)),key="mock")


if __name__=="__main__":
    unittest.main()
