import json, tempfile, unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
import acolad_v4_hourly_publish as p
import acolad_v4_resume_verified_artifact as loader

D=date(2026,11,7)
STORY={"topic":"بازبینی واقعی UX","slides":[{"n":1,"text":"نمونه",
       "scene_id":1,"visual_action":"new_scene","beat":"hook"}]}
EVIDENCE=[{"id":"S01","url":"https://doi.org/10.1234/test","title":"Source"}]

class CheckpointSafety(unittest.TestCase):
 def test_save_then_resume_without_recalling_original_research(self):
  with tempfile.TemporaryDirectory() as root:
   target=Path(root)/"verified_story_checkpoint.json"
   with patch.object(p,"EDITORIAL_CACHE",target),patch.object(p,"OUT",Path(root)),patch.object(p,"READY",Path(root)/"hourly_ready.json"):
    with patch.object(p,"check_verified_editorial",return_value=True):
     p.save_editorial(D,STORY,EVIDENCE)
     self.assertEqual(p.saved_editorial(D),(STORY,EVIDENCE))
     with self.assertRaisesRegex(RuntimeError,"WRONG_DAY"):
      p.saved_editorial(date(2026,11,8))
 def test_429_happens_after_story_persisted_and_next_try_skips_research(self):
  with tempfile.TemporaryDirectory() as root:
   with patch.object(p,"EDITORIAL_CACHE",Path(root)/"verified_story_checkpoint.json"),patch.object(p,"OUT",Path(root)),patch.object(p,"READY",Path(root)/"hourly_ready.json"),patch.object(p,"check_verified_editorial",return_value=True),patch.object(p.engine,"generate_editorial",return_value=(STORY,EVIDENCE)) as gen,patch.object(p.engine,"make_channel_copies",side_effect=RuntimeError("GEMINI_FALLBACK_HTTP_429")):
    with self.assertRaisesRegex(RuntimeError,"429"):p.prepare(D)
    self.assertTrue(p.EDITORIAL_CACHE.exists())
    gen.reset_mock()
    with self.assertRaisesRegex(RuntimeError,"429"):p.prepare(D)
    gen.assert_not_called()
 def test_not_ready_artifact_never_seeds_cache(self):
  with tempfile.TemporaryDirectory() as root:
   basedir=Path(root)
   (basedir/"acolad_luna_research_preview").mkdir()
   (basedir/"acolad_daily_editorial_output").mkdir()
   (basedir/"acolad_luna_research_preview"/"status.json").write_text(json.dumps(
       {"status":"QA_BLOCKED_HUMAN_REVIEW_REQUIRED","issues":["bad"],"novinhub_api_calls":0}))
   (basedir/"acolad_daily_editorial_output"/"preview_status.json").write_text(json.dumps(
       {"dynamic_story_ready_for_design":False,"day_tehran":"2026-11-07"}))
   with self.assertRaisesRegex(RuntimeError,"HISTORIC_ARTIFACT_NOT_VALIDATED"):
    loader.restore_from_artifact(basedir,D)
 def test_verified_artifact_restored_only_after_second_validation(self):
  with tempfile.TemporaryDirectory() as root:
   r=Path(root)
   a=r/"acolad_luna_research_preview";a.mkdir()
   b=r/"acolad_daily_editorial_output";b.mkdir()
   (a/"status.json").write_text(json.dumps({"status":"PREVIEW_NEEDS_HUMAN_REVIEW",
       "issues":[],"novinhub_api_calls":0}))
   (b/"preview_status.json").write_text(json.dumps({
       "dynamic_story_ready_for_design":True,"day_tehran":"2026-11-07",
       "voice_v4_gate":{"passed":True},
       "independent_editorial_gate":{"passed":True}}))
   (a/"stories.json").write_text(json.dumps(STORY))
   (a/"selected_evidence.json").write_text(json.dumps(EVIDENCE))
   with patch.object(loader,"check_verified_editorial",return_value=True),patch.object(loader,"save_editorial") as save:
    loader.restore_from_artifact(r,D)
   save.assert_called_once_with(D,STORY,EVIDENCE)

if __name__=="__main__":unittest.main()
