import unittest
from unittest.mock import patch
from acolad_mixed_qa_recovery import (
    supported_recovery_issues,presentation_only,recover_mixed_issues)

class SourceLockedMixedQA(unittest.TestCase):
    def story(self):
        return {"slides":[
            {"n":1,"beat":"hook","text":"شروع داستان."},
            {"n":2,"beat":"setup","text":"ولی یه مانع جدی جلوی مشتری بود."},
            {"n":3,"beat":"payoff","text":"۱۰ اتفاق خوب افتاده."},
            {"n":4,"beat":"evidence","text":"داده اصلی این موضوع رو توضیح می‌ده."},
            {"n":5,"beat":"action","text":"اول باید مسیر رو بسنجیم."},
            {"n":6,"beat":"payoff","text":"بعدش می‌شه بهتر تصمیم گرفت."}
        ]}
    def issues(self):
        return ["frame 3: numerical claim 10 not in approved evidence",
                "cinema: payoff jumps ahead of action",
                "cinema: missing conflict beat",
                "cinema: too many final periods"]
    def test_only_approved_mixed_issues_receive_paid_repair(self):
        self.assertTrue(supported_recovery_issues(self.issues()))
        self.assertFalse(supported_recovery_issues(self.issues()+[
            "frame 3: invented source ID S99"]))
        self.assertFalse(supported_recovery_issues([]))
    def test_cosmetic_repair_preserves_every_number_and_source_text(self):
        s=self.story()
        cleaned,changed=presentation_only(s,self.issues())
        self.assertTrue(changed)
        self.assertIn("۱۰",cleaned["slides"][2]["text"])
        self.assertEqual(cleaned["slides"][1]["beat"],"conflict")
        self.assertEqual(s["slides"][1]["beat"],"setup")
        self.assertTrue(cleaned["slides"][0]["text"].endswith("داستان"))
    def test_source_locked_rewrite_must_clear_all_original_hard_vetoes(self):
        s=self.story()
        approved={"slides":[
            {"n":1,"beat":"hook","text":"شروع"},
            {"n":2,"beat":"conflict","text":"ولی مانع هست"},
            {"n":3,"beat":"evidence","text":"شاهد"},
            {"n":4,"beat":"action","text":"آزمایش"},
            {"n":5,"beat":"payoff","text":"تصمیم"}
        ]}
        usage={"requests_sent":4}
        calls=[]
        def fake_model(prompt):
            calls.append(prompt)
            usage["requests_sent"]+=1
            return approved
        def qa(story):
            return [] if story==approved else [
                "frame 3: numerical claim 10 not in approved evidence",
                "cinema: payoff jumps ahead of action"]
        result,errors,notes=recover_mixed_issues(
            s,self.issues(),[{"id":"S01"}],"original verified source",usage,6,
            fake_model,qa)
        self.assertEqual(errors,[])
        self.assertEqual(result,approved)
        self.assertEqual(len(calls),1)
        self.assertIn("original verified source",calls[0])
        self.assertIn("numerical",calls[0])
        self.assertTrue(any("REWRITE_REDUCED_ERRORS" in n for n in notes))
    def test_no_api_call_once_call_limit_hit(self):
        with patch("acolad_daily_editorial_v1.repair_missing_conflict_beat",
                   return_value=(self.story(),False)):
            out,issues,notes=recover_mixed_issues(
                self.story(),self.issues(),[],"source",{"requests_sent":6},6,
                lambda prompt:self.fail("should not call model"),
                lambda candidate:self.issues())
        self.assertEqual(issues,self.issues())
    def test_source_fraud_veto_never_rewritten_as_cosmetic(self):
        errors=self.issues()+["frame 3: fake source ID S99"]
        out,remaining,_=recover_mixed_issues(
            self.story(),errors,[],"source",{"requests_sent":0},6,
            lambda prompt:self.fail("should never use model"),
            lambda cand:self.fail("should never call QA"))
        self.assertEqual(remaining,errors)
    def test_failed_model_does_not_publish_or_mark_clean(self):
        out,remaining,notes=recover_mixed_issues(
            self.story(),self.issues(),[],"source",{"requests_sent":3},6,
            lambda prompt: (_ for _ in ()).throw(RuntimeError("HTTP 503")),
            lambda _:self.issues())
        self.assertNotEqual(remaining,[])
        self.assertIn("MIXED_REWRITE_FAILED_RuntimeError",notes)

if __name__=="__main__":unittest.main()
