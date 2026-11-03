import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import acolad_luna_research_preview as research
import acolad_concept_art_pipeline_v2 as art

class SafeEditorialGate(unittest.TestCase):
    def test_no_billable_call_if_no_verified_evidence_pair(self):
        now=dt.datetime.now(dt.timezone.utc).date().isoformat()
        items=[
          {"id":"S01","title":"خبر معتبر کسب و کار","publisher":"رسانه الف",
           "date":now,"source_type":"rss_summary","evidence_depth":"full_article",
           "excerpt":"متن بدنه معتبر","url":"https://example.org/1","rank":30},
          {"id":"S02","title":"گزارش معتبر بازاریابی","publisher":"رسانه ب",
           "date":now,"source_type":"rss_summary","evidence_depth":"full_article",
           "excerpt":"متن بدنه معتبر","url":"https://example.org/2","rank":30},
          {"id":"S03","title":"Study of consumer purchase decisions","publisher":"Journal X",
           "date":now,"source_type":"academic_doi","evidence_depth":"abstract",
           "excerpt":"Evidence from a rigorous study","url":"https://doi.org/10.0000/example",
           "rank":33},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(research,"ROOT",Path(tmp)):
                with patch.dict(os.environ,{"GAPGPT_API_KEY":"NOT_A_REAL_KEY_BUT_NEVER_SENT"}):
                    with patch.object(research,"collect_sources",return_value=items):
                        with patch.object(research,"suggested_evidence_pairs",return_value=[]):
                            with patch.object(research,"api_call",side_effect=RuntimeError("MOCKED_PAID_CALL_NO_SPEND")) as fake:
                                code=research.main([
                                    "--focus","auto",
                                    "--budget-usd","0.018",
                                    "--approval",research.APPROVAL,
                                    "--gift-confirmation",research.GIFT])
            self.assertEqual(code,0)
            report=json.loads((Path(tmp)/"status.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"],"PIPELINE_ERROR_NO_PUBLICATION")
            # The narrative is now allowed to TRY a single grounded source,
            # while this test prevents any real paid request.
            fake.assert_called_once()
            self.assertEqual(report["gapgpt_requests_sent"],0)
            self.assertEqual(report["publication"],"NEVER")

    def test_original_artwork_for_hidden_guest_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"scene_03.png"
            result=art.ink_sketch(3,"کلید کوچک خرید مهمان پشت پرده پنهان",path)
            self.assertTrue(path.is_file())
            self.assertTrue(result["transparent"])
            self.assertEqual(result["status"],"ORIGINAL_PROCEDURAL_PNG")

if __name__=="__main__":unittest.main()
