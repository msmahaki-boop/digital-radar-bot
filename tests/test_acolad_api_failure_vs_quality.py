import json,tempfile,unittest
from pathlib import Path
from datetime import date
from unittest.mock import patch
import acolad_v4_hourly_publish as p

class PublishReporting(unittest.TestCase):
 def test_transport_failure_is_not_labeled_quality_veto(self):
  with tempfile.TemporaryDirectory() as root:
   state=Path(root)/"status.json"
   state.write_text(json.dumps({"status":"PIPELINE_ERROR_NO_PUBLICATION","issues":["GapGPT HTTP 403"]}))
   with patch.object(p.engine,"STATUS",state),patch.object(p.engine,"generate_editorial",return_value=(None,None)):
    with self.assertRaisesRegex(RuntimeError,"EDITORIAL_UPSTREAM_TECHNICAL_FAILURE"):
     p.prepare(date(2026,11,7))
 def test_real_quality_veto_still_safely_skips(self):
  with tempfile.TemporaryDirectory() as root:
   state=Path(root)/"status.json"
   state.write_text(json.dumps({"status":"QA_BLOCKED_HUMAN_REVIEW_REQUIRED"}))
   with patch.object(p.engine,"STATUS",state),patch.object(p.engine,"generate_editorial",return_value=(None,None)):
    self.assertIsNone(p.prepare(date(2026,11,7)))

if __name__=="__main__":unittest.main()
