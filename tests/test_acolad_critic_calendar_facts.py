import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch

import acolad_v4_daily_autopublish as app


class CriticCalendarQA(unittest.TestCase):
    def test_october_24_precedes_november_8_by_fifteen_days(self):
        observations=[]
        def judge(prompt, data):
            observations.append((prompt,data))
            return {"score":92,"veto":False,"reason":"تاریخ محاسبه شد، شاهد قابل بررسی است."}
        with patch.object(app,"tehran_now",return_value=datetime(2026,11,8,12,30,tzinfo=ZoneInfo("Asia/Tehran"))), \
             patch.object(app,"model_json",side_effect=judge):
            reviewers=app.critics_approve(
                {"slides":[{"text":"فقط متن نمونه برای تست تقویم"}]},
                [{"date":"2026-10-24","title":"source","excerpt":"published study"}],
                {"telegram":"تست","bale":"تست","instagram":"تست"})
        self.assertEqual(len(reviewers),2)
        self.assertTrue(all(r["score"]==92 and r["veto"] is False for r in reviewers))
        self.assertEqual(len(observations),2)
        for prompt,data in observations:
            self.assertIn("2026-10-24",prompt)
            self.assertIn("2026-11-08",prompt)
            self.assertEqual(data["evidence"][0]["days_before_today_calculated"],15)
            self.assertFalse(data["evidence"][0]["date_is_future_calculated"])

    def test_future_date_computed_negative_for_both_critics(self):
        observed=[]
        with patch.object(app,"tehran_now",return_value=datetime(2026,11,8,tzinfo=ZoneInfo("Asia/Tehran"))), \
             patch.object(app,"model_json",side_effect=lambda p,d:(observed.append(d) or
                  {"score":0,"veto":True,"reason":"date in future"})):
            reviewers=app.critics_approve({"slides":[{"text":"تست"}]},
                [{"date":"2026-11-15","title":"future","excerpt":"example"}],
                {"telegram":"t","bale":"b","instagram":"i"})
        self.assertTrue(all(r["veto"] for r in reviewers))
        self.assertEqual(observed[0]["evidence"][0]["days_before_today_calculated"],-7)
        self.assertTrue(observed[1]["evidence"][0]["date_is_future_calculated"])

if __name__=="__main__":
    unittest.main()
