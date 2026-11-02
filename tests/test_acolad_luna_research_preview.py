import unittest
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('engine',Path(__file__).resolve().parents[1]/'acolad_luna_research_preview.py')
e=importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)

class LunaResearchTests(unittest.TestCase):
    def test_no_publishing_methods_in_code(self):
        code=(Path(__file__).resolve().parents[1]/'acolad_luna_research_preview.py').read_text()
        for dangerous in ('api.novinhub.com','api.buffer.com','api.telegram.org','graph.instagram.com',
                          'POST/post','instagram_content_publish'):
            self.assertNotIn(dangerous,code)
    def test_feed_parse_news(self):
        xml=b'<rss><channel><item><title>Business test</title><link>https://digiato.com/test</link><pubDate>Mon, 02 Nov 2026 06:00:00 +0000</pubDate><description>Test</description></item></channel></rss>'
        out=e.feed_entries(xml,'test','https://digiato.com/feed')
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['date'],'2026-11-02')
    def test_no_untrusted_url(self):
        self.assertFalse(e.safe_url('http://127.0.0.1/admin'))
        self.assertFalse(e.safe_url('file:///etc/passwd'))
        self.assertTrue(e.safe_url('https://peivast.com/articles/one'))
        self.assertFalse(e.is_allowed_article('https://peivast.com.attacker.test/one'))
    def test_source_tiers(self):
        self.assertEqual(e.source_tier({'evidence_depth':'abstract'}),'ACADEMIC_ABSTRACT')
        self.assertEqual(e.source_tier({'evidence_depth':'headline_only'}),'AGGREGATOR_HEADLINE_ONLY')
    def test_currency(self):
        self.assertEqual(e.EXCHANGE_TOMAN,250000)
        self.assertEqual(round((1360*e.INPUT_PER_M+810*e.OUTPUT_PER_M)/1_000_000*250000,1),135.2)
    def test_unsupported_statistics_blocked(self):
        src=[{'id':'S01','title':'Example','excerpt':'only fact','evidence_depth':'full_article'}]
        slides=[{'n':i,'text':'فقط فکر کن **مشتری** چقدر از این داستان تعجب می‌کنه وقتی ۹۸٪ مغازه‌ها خراب شدن و هیچ منبعی نداریم ولی ما حرف می‌زنیم.', 'source_ids':['S01']} for i in range(1,6)]
        story={'slides':slides,'interaction':{'type':'poll','options':['A','B']}}
        issues=e.story_quality(story,src)
        self.assertTrue(any('numerical claim' in x for x in issues))
    def test_plan_bad_ids_blocked(self):
        plan={'source_ids':['S01','S99']}
        sources=[{'id':'S01','publisher':'one','date':e.now().date().isoformat(),'source_type':'rss_summary'}]
        self.assertTrue(any('invented' in x for x in e.validate_plan(plan,sources)))
    def test_cross_publisher_requirement(self):
        today=e.now().date().isoformat()
        records=[
            {'id':'S01','publisher':'دیجیاتو','date':today,'source_type':'rss_summary','evidence_depth':'full_article'},
            {'id':'S02','publisher':'دیجیاتو','date':today,'source_type':'rss_summary','evidence_depth':'full_article'},
            {'id':'S03','publisher':'زومیت','date':today,'source_type':'rss_summary','evidence_depth':'full_article'},
        ]
        self.assertIn('plan: insufficient publisher diversity',e.validate_plan({'source_ids':['S01','S02']},records))
        self.assertNotIn('plan: insufficient publisher diversity',e.validate_plan({'source_ids':['S01','S03']},records))
    def test_unrelated_topics_blocked(self):
        today=e.now().date().isoformat()
        records=[
            {'id':'S04','publisher':'دیجیاتو','date':today,'title':'مرجع صدور مجوز فروش آنلاین طلا',
             'source_type':'rss_summary','evidence_depth':'full_article'},
            {'id':'S05','publisher':'زومیت','date':today,'title':'وقتی درآمد دیجیتال است و بیمه سنتی',
             'source_type':'rss_summary','evidence_depth':'full_article'},
        ]
        self.assertIn('plan: no shared concrete topic across selected articles',
                      e.validate_plan({'source_ids':['S04','S05']},records))

    def test_related_topics_pass(self):
        today=e.now().date().isoformat()
        records=[
            {'id':'S01','publisher':'رسانه الف','date':today,'title':'مجوز فروش آنلاین طلا',
             'source_type':'rss_summary','evidence_depth':'full_article'},
            {'id':'S02','publisher':'رسانه ب','date':today,'title':'صدور مجوز طلا در سامانه جدید',
             'source_type':'rss_summary','evidence_depth':'full_article'},
        ]
        issues=e.validate_plan({'source_ids':['S01','S02']},records)
        self.assertNotIn('plan: no shared concrete topic across selected articles',issues)

    def test_publication_year_is_valid_metadata(self):
        sources=[
            {'id':'S01','title':'مجوز طلا','date':'2026-11-02',
             'excerpt':'صدور مجوز در یک نهاد اعلام شد','evidence_depth':'full_article'},
            {'id':'S02','title':'مجوز طلا گزارش دوم','date':'2026-11-02',
             'excerpt':'اطلاعات تایید شده','evidence_depth':'full_article'}
        ]
        body='مشتری می‌پرسه وقتی سال ۲۰۲۶ درباره مجوز حرف می‌زنیم، **چطوری** باید راه بررسی رسمی رو پیدا کنه و از پاسخ درست مطمئن بشه؟'
        slides=[{'n':i,'text':body,'source_ids':['S01' if i%2 else 'S02']} for i in range(1,6)]
        story={'slides':slides,'interaction':{'type':'poll','options':['الف','ب']}}
        self.assertFalse(any('numerical claim 2026' in i for i in e.story_quality(story,sources)))

    def test_replan_call_count_gate(self):
        usage={'requests_sent':4,'cost_estimated_usd':0.0,'budget_usd':0.02}
        with self.assertRaisesRegex(RuntimeError,'MAX_CALLS reached'):
            e.api_call('never_sent','sys','user',100,usage)

    def test_json_extraction(self):
        self.assertEqual(e.json_from_model('```json\n{"a":1}\n```'),{'a':1})
    def test_model_luna_only(self):
        self.assertEqual(e.MODEL,'gpt-6-luna')
        self.assertEqual(e.MAX_CALLS,4)

if __name__=='__main__':unittest.main()
