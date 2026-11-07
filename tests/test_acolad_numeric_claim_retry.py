import unittest
import acolad_luna_research_preview as news

class UnverifiedNumericGate(unittest.TestCase):
 def test_two_unsupported_numbers_trigger_bounded_rewrite(self):
  self.assertTrue(news.only_unsupported_numeric_issues([
   "frame 2: numerical claim 1 not in approved evidence",
   "frame 3: numerical claim 10 not in approved evidence"]))
 def test_mixed_actual_factual_issues_are_not_automatically_rewritten(self):
  self.assertFalse(news.only_unsupported_numeric_issues([
   "frame 2: numerical claim 1 not in approved evidence",
   "frame 4: fake source ID S99"]))
 def test_empty_errors_no_rewrite(self):
  self.assertFalse(news.only_unsupported_numeric_issues([]))
 def test_budget_remains_bounded(self):
  self.assertLessEqual(news.MAX_CALLS,6)
  self.assertEqual(news.MAX_BUDGET_USD,0.025)

if __name__=="__main__":unittest.main()
