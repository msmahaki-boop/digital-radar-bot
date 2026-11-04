import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
import acolad_novinhub_daily as p
class Tests(unittest.TestCase):
    def test_early_tehran_target(self):
        now=datetime(2026,11,5,14,11,tzinfo=ZoneInfo("Asia/Tehran"))
        self.assertEqual(p.target_utc(now).isoformat(),"2026-11-05T14:30:00+00:00")
    def test_late_tehran_skip(self):
        now=datetime(2026,11,5,17,30,tzinfo=ZoneInfo("Asia/Tehran"))
        self.assertIsNone(p.target_utc(now))
    def test_buffer_duplicate_detected(self):
        posts=[{"text":p.DAILY_MARKER+"2026-11-05","status":"scheduled","id":"p1"}]
        with patch.dict(p.os.environ,{"BUFFER_API_KEY":"test"}),patch.object(p,"buffer_identity",return_value=("org","chan")),patch.object(p,"recent_buffer_posts",return_value=posts):
            self.assertEqual(p.prevent_buffer_dup("2026-11-05")["status"],"BUFFER_ALREADY_HAS_DATE")
    def test_no_buffer_key_fails_closed(self):
        with patch.dict(p.os.environ,{"BUFFER_API_KEY":""}):
            with self.assertRaises(RuntimeError):p.prevent_buffer_dup("2026-11-05")
    def test_manifest_missing_prevents_publish(self):
        with self.assertRaises(FileNotFoundError):p.verify_editorial_manifest("nonexistent_folder")
if __name__=="__main__":unittest.main()
