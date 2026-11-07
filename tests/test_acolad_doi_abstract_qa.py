import unittest
from datetime import date,timedelta
import acolad_luna_research_preview as m

def source(domain="https://doi.org/10.1234/research",age=90,words=50):
 return {"id":"S01","title":"Research based on a reported study",
  "url":domain,"publisher":"Journal","source_type":"academic_doi",
  "date":(date.today()-timedelta(days=age)).isoformat(),
  "evidence_depth":"abstract","excerpt":"This is an original research summary with observation and scope. "*words}

class DOIOriginalOnly(unittest.TestCase):
 def test_real_doi_abstract_passes_for_evergreen(self):
  a=source()
  self.assertTrue(m.eligible_scholarly_abstract(a))
  self.assertEqual(m.validate_plan({"source_ids":["S01"]},[a]),[])
 def test_brief_or_empty_abstract_rejected(self):
  a=source(words=1)
  self.assertFalse(m.eligible_scholarly_abstract(a))
 def test_bad_doi_rejected(self):
  a=source(domain="https://example.com/article")
  self.assertFalse(m.eligible_scholarly_abstract(a))
 def test_old_doi_rejected(self):
  self.assertFalse(m.eligible_scholarly_abstract(source(age=370)))
 def test_fake_academic_source_rejected(self):
  a=source()
  a["source_type"]="news_aggregator_headline"
  self.assertFalse(m.eligible_scholarly_abstract(a))

if __name__=="__main__": unittest.main()
