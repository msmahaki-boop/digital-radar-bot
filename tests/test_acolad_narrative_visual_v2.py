import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image,ImageChops
import acolad_narrative_visual_v2 as v

STORY_PATH=Path("examples/acolad_narrative_v2_fixed_demo.json")

class FrozenSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=(v.REG,v.MEDIUM,v.BOLD)
        cls.font_issue=v.font_integrity()
        cls.story=json.loads(STORY_PATH.read_text(encoding="utf8"))
        cls.using_test_fallback=(cls.font_issue!="VALID")
        # Fallback is strictly a test fixture for geometry diagnostics when
        # the repository font is damaged. Once valid fonts are installed,
        # ALL rendering tests use the actual brand IRANSans files.
        cls.test_font=Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        cls.test_bold=Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if cls.using_test_fallback:
            if not cls.test_font.is_file():raise unittest.SkipTest("test-only font missing")
            v.REG=cls.test_font
            v.MEDIUM=cls.test_font
            v.BOLD=cls.test_bold

    @classmethod
    def tearDownClass(cls):
        v.REG,v.MEDIUM,v.BOLD=cls.original

    def test_brand_fonts_are_valid_and_renderer_uses_real_iransans(self):
        self.assertEqual(self.original[0].as_posix(),
                         "assets/fonts/IRANSans-Regular.ttf")
        self.assertEqual(self.original[2].as_posix(),
                         "assets/fonts/IRANSans-Bold.ttf")
        self.assertEqual(self.font_issue,"VALID",
                         "Real brand font files must be nonzero and valid")
        self.assertFalse(self.using_test_fallback,
                         "Real IRANSans must be used after installation")
        # Header/bytes check is not enough: FreeType must truly load the
        # regular and bold fonts, and RAQM must shape Persian correctly.
        v.check_assets()
        regular,bold=v.font_set(58)
        self.assertIsNotNone(regular.getbbox("آکولاد"))
        self.assertIsNotNone(bold.getbbox("داستان"))

    def test_scene_order_and_frozen_preset(self):
        groups=v.scene_chunks(self.story)
        self.assertEqual(len(groups),6)
        self.assertEqual(len(groups[0]),2)
        one=groups[0]
        layout=v.plan_scene([x["added_text"] for x in one],photo=False)
        self.assertEqual(layout[0]["size"],layout[1]["size"])
        self.assertLess(layout[0]["y"],layout[1]["y"])

    def test_prior_words_do_not_shift_after_next_frame(self):
        group=v.scene_chunks(self.story)[0]
        plans=v.plan_scene([x["added_text"] for x in group],photo=False)
        base=Image.open(v.BASE).convert("RGBA")
        v.render_rows(base,plans[0])
        frozen=base.copy()
        v.render_rows(base,plans[1])
        # The entire first caption area must be byte-identical.
        boundary=plans[1]["y"]-4
        region=(60,400,1020,boundary)
        self.assertIsNone(ImageChops.difference(frozen.crop(region),
                                                base.crop(region)).getbbox())

    def test_markdown_bold_preserves_branded_accent(self):
        p=v.plan_scene(["مهدی **سبد خرید** رو نگاه می‌کنه"],photo=False)
        self.assertEqual(len(p),1)
        self.assertTrue(any(t[1] for line in p[0]["lines"] for t in line))

    def test_missing_external_secret_is_irrelevant(self):
        import inspect
        body=inspect.getsource(v)
        for phrase in ("requests.post(","createPost","is_draft","novinhub_api_token"):
            self.assertNotIn(phrase,body.lower() if phrase=="novinhub_api_token" else body)

if __name__=="__main__":unittest.main()
