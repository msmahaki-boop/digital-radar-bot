import unittest
from acolad_editorial_trust_gate import evaluate,check_public_copy,require_human_release,load_policy

def story(text="فرض کن یک مشتری بسته را باز می‌کند و متوجه یک تفاوت تازه می‌شود"):
    return {"topic":"چرا این تجربه خرید این بار فرق دارد؟","slides":[
        {"text":text},{"text":"فروشنده متوجه می‌شود یک انتخاب غیرمنتظره پیش روی مشتری است"},
        {"text":"مشتری تصمیم می‌گیرد از روی شواهد مقایسه کند"},
        {"text":"حالا روشن است چه چیزی را باید آزمایش کرد"}
      ],"resolution":{"answer":"مقایسه عملی دو تجربه خرید به جای حدس"}}

def source(domain,evidence="full_article",category="rss_summary"):
    return {"id":"S02","url":"https://"+domain+"/research/retention",
            "evidence_depth":evidence,"source_type":category}

class TrustGateTests(unittest.TestCase):
    def test_reject_exact_nov_4_secondary_source_only(self):
        s=story("خبر می‌گه آنتروپیک در حال توسعهٔ ابزاری برای اثبات منشأ جواب‌هاست")
        result=evaluate(s,[source("digiato.com")])
        self.assertIn("ONLY_SECONDARY_MEDIA",result["hard_vetoes"])
        self.assertIn("NO_PRIMARY_OR_SPECIALIST_SOURCE",result["hard_vetoes"])
        self.assertFalse(result["passed"])
        self.assertFalse(result["publish_allowed"])
    def test_primary_specialist_evidence_can_reach_human_review(self):
        result=evaluate(story(),[source("baymard.com")])
        self.assertTrue(result["passed"])
        self.assertFalse(result["human_approved"])
        self.assertFalse(result["publish_allowed"])
        self.assertEqual(result["quality_score"],"UNASSESSED")
    def test_raw_source_url_blocked_in_public_copy(self):
        result=check_public_copy("منبع: https://digiato.com/article")
        self.assertFalse(result["clean"])
        self.assertIn("raw_link",result["violations"])
    def test_internal_marker_blocked(self):
        result=check_public_copy("آکولاد | ACOLAD-BALE-NARRATIVE-20261104")
        self.assertFalse(result["clean"])
        self.assertIn("technical_marker",result["violations"])
    def test_source_label_blocked(self):
        result=check_public_copy("منبع خبر: یک روزنامه")
        self.assertFalse(result["clean"])
        self.assertIn("source_label",result["violations"])
    def test_editorial_rejection_not_overridden_by_one_reviewer(self):
        policy=load_policy()
        rubric=policy["approval_rubric"]
        perfect={k:v for k,v in rubric.items()}
        perfect["explicit_approve"]=True
        self.assertFalse(require_human_release([perfect]))
        self.assertTrue(require_human_release([perfect,perfect]))
    def test_second_review_under_85_is_rejected(self):
        p=load_policy();rubric=p["approval_rubric"]
        first={**rubric,"explicit_approve":True}
        second={**rubric,"explicit_approve":True}
        second["story_arc_and_scene_progress"]=0
        second["business_insight"]=0
        self.assertFalse(require_human_release([first,second]))
    def test_no_evidence_blocks(self):
        self.assertIn("NO_SUBSTANTIVE_VERIFIED_ARTICLE",evaluate(story(),[])["hard_vetoes"])
    def test_single_original_research_source_is_accepted_for_human_review(self):
        result=evaluate(story(),[source("journals.sagepub.com",category="academic_doi")])
        self.assertTrue(result["passed"])
        self.assertFalse(result["publish_allowed"])
if __name__=="__main__": unittest.main()
