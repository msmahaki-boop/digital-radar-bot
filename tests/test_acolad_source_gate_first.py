import unittest
import acolad_daily_editorial_v1 as editor

class SourceFirstGate(unittest.TestCase):
 def test_secondary_reportage_never_reaches_paid_writer(self):
  candidates=[
   {"url":"https://digiato.com/artificial-intelligence/example","source_type":"news","evidence_depth":"full_article"},
   {"url":"https://techcrunch.com/2026/11/07/ai","source_type":"news","evidence_depth":"full_article"},
   {"url":"https://baymard.com/research-articles/checkout","source_type":"expert_research","evidence_depth":"full_article"},
   {"url":"https://seths.blog/2026/11/automation","source_type":"expert_blog","evidence_depth":"full_article"},
   {"url":"https://doi.org/10.1234/example","source_type":"academic_doi","evidence_depth":"abstract"}]
  log=[]
  vetted=editor.first_party_expert_sources(candidates,log)
  self.assertEqual(len(vetted),3)
  self.assertTrue(all("digiato" not in x["url"] and "techcrunch" not in x["url"] for x in vetted))
  self.assertEqual([x["id"] for x in vetted],["S01","S02","S03"])
  self.assertTrue(any("PRIMARY_EXPERT_ONLY_BEFORE_LUNA" in x for x in log))
 def test_no_primary_returns_empty_not_secondary_fallback(self):
  doc=[{"url":"https://digiato.com/foo","source_type":"news","evidence_depth":"full_article"}]
  self.assertEqual(editor.first_party_expert_sources(doc,[]),[])
 def test_official_firstparty_accepted(self):
  doc=[{"url":"https://openai.com/index/example","source_type":"official","evidence_depth":"full_article"}]
  self.assertEqual(len(editor.first_party_expert_sources(doc,[])),1)

if __name__=="__main__": unittest.main()
