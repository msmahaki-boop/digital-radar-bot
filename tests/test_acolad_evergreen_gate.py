import unittest
from datetime import date,timedelta
import acolad_luna_research_preview as m

def article(domain,days,source_type="news"):
 return {"id":"S01","url":"https://"+domain+"/research/example","title":"A firsthand usability study",
  "publisher":domain,"source_type":source_type,"date":(date.today()-timedelta(days=days)).isoformat(),
  "evidence_depth":"full_article","excerpt":"Original sourced observation "*15}

class TrustedEvergreen(unittest.TestCase):
 def test_two_month_old_baymard_original_is_eligible(self):
  a=article("baymard.com",60)
  self.assertTrue(m.eligible_original_evergreen(a))
  self.assertEqual(m.validate_plan({"source_ids":["S01"]},[a]),[])
 def test_old_secondary_news_is_never_evergreen_evidence(self):
  a=article("digiato.com",60)
  self.assertFalse(m.eligible_original_evergreen(a))
  self.assertIn("plan: no current news or verified original evergreen source",
                m.validate_plan({"source_ids":["S01"]},[a]))
 def test_original_study_older_than_one_year_is_not_current(self):
  self.assertFalse(m.eligible_original_evergreen(article("baymard.com",367)))
 def test_today_original_blog_still_counts_as_fresh(self):
  a=article("seths.blog",1)
  self.assertEqual(m.validate_plan({"source_ids":["S01"]},[a]),[])
 def test_abstract_not_a_full_evergreen_article(self):
  a=article("baymard.com",60)
  a["evidence_depth"]="summary_only"
  self.assertFalse(m.eligible_original_evergreen(a))

if __name__=="__main__":unittest.main()
