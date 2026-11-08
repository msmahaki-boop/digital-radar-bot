import unittest
from unittest.mock import patch

import acolad_gpt25_owner_release_preflight as release


class Nov8OwnerPreflightQA(unittest.TestCase):
    def test_bale_native_footer_replaces_only_old_reviewed_footer(self):
        source="پژوهش معتبر درباره تجربه خرید.\n\n"+release.OLD_FOOTER
        bale="🌐 acolad.ir\n📢 کانال بله: @acoladagency"
        with patch.object(release.engine,"footer_for",return_value=bale,create=True), \
             patch.object(release.engine,"clean_old_markup",side_effect=lambda value:value,create=True):
            result=release.normalize_reviewed_channel_footer(source,"bale")
        self.assertTrue(result.endswith(bale))
        self.assertIn("پژوهش معتبر درباره تجربه خرید.",result)
        self.assertNotIn("](",result)
        self.assertNotIn("t.me",result)

    def test_unknown_public_caption_is_never_silently_rebranded(self):
        with patch.object(release.engine,"footer_for",return_value="@acoladagency",create=True):
            with self.assertRaisesRegex(RuntimeError,"ORIGINAL_REVIEWED_SOCIAL_FOOTER"):
                release.normalize_reviewed_channel_footer("محتوای تأییدنشده","telegram")

    def test_rejects_instagram_as_native_bale_telegram_footer(self):
        with self.assertRaises(ValueError):
            release.normalize_reviewed_channel_footer("چیزی","instagram")

if __name__=="__main__":
    unittest.main()
