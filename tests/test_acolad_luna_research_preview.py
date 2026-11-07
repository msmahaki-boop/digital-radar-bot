import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch

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
    def test_diverse_source_selection(self):
        rows=[{'id':str(i),'publisher':'ناشر الف' if i<9 else ('ناشر ب' if i<12 else 'ناشر ج')}
              for i in range(15)]
        chosen=e.diversified_source_sample(rows,6,max_each=2)
        self.assertEqual(len(chosen),6)
        self.assertEqual({x['publisher'] for x in chosen},{'ناشر الف','ناشر ب','ناشر ج'})

    def test_compact_research_prompt_keeps_all_19_sources(self):
        rows=[{'id':'S'+str(i).zfill(2),'title':'داستان فروش آنلاین و مشتری '+str(i),
               'date':'2026-11-02','publisher':'ناشر '+str(i%4),
               'evidence_depth':'full_article','excerpt':'تحلیل رفتار خرید و هزینه '*100,
               'institutions':[]} for i in range(1,20)]
        packed=e.source_data_for_llm(rows)
        import json
        obj=json.loads(packed)
        self.assertEqual(len(obj),19)
        self.assertEqual(obj[-1]['id'],'S19')
        self.assertLessEqual(len(packed),19000)

    def test_fresh_official_original_read_before_secondary_headlines(self):
        today=e.now().date().isoformat()
        official={'title':'Official Search Controls for AI Training',
            'publisher':'Google Search Central','date':today,
            'url':'https://developers.google.com/search/blog/2026/11/example',
            'excerpt':'official announcement of new controls','source_type':'rss_summary',
            'evidence_depth':'summary_only'}
        secondary=[{'title':f'Customer marketing experiment digest number {i}',
            'publisher':f'Secondary {i}','date':today,
            'url':f'https://digiato.com/test-{i}',
            'excerpt':'consumer customer brand marketing retail commerce price ' * 6,
            'source_type':'rss_summary','evidence_depth':'summary_only'} for i in range(22)]
        attempted=[]
        def excerpt(url):
            attempted.append(url)
            return 'Direct original first-party article with concrete context on website controls. ' * 4
        with (patch.object(e,'search_news',return_value=secondary+[official]),
              patch.object(e,'search_scholar',return_value=[]),
              patch.object(e,'search_openalex',return_value=[]),
              patch.object(e,'get_article_excerpt',side_effect=excerpt)):
            selected=e.collect_sources('marketing',[])
        self.assertEqual(attempted[0],official['url'])
        self.assertEqual(selected[0]['url'],official['url'])
        self.assertEqual(selected[0]['evidence_depth'],'full_article')

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

    def test_cross_language_consumer_research_bridge(self):
        n={'id':'S01','title':'هزینه تعویض لاستیک ایرانی و جدول قیمت بازار',
           'date':e.now().date().isoformat(),'publisher':'دیجیاتو',
           'source_type':'rss_summary','evidence_depth':'full_article','rank':25}
        a={'id':'S06','title':'The Economics of Consumer Loyalty in Quick Commerce: Price Sensitivity and Brand Switching',
           'date':'2025-03-06','publisher':'Independent Journal',
           'source_type':'academic_doi','evidence_depth':'abstract','rank':19}
        self.assertTrue(e.related_source_pair(n,a))
        self.assertFalse(e.unrelated_selected_subjects([n,a]))
        pairs=e.suggested_evidence_pairs([n,a])
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs[0]['source_ids'],['S01','S06'])
        issues=e.validate_plan({'source_ids':['S01','S06']},[n,a])
        self.assertNotIn('plan: no shared concrete topic across selected articles',issues)
    def test_unrelated_labor_and_gold_still_blocked(self):
        news={'id':'S01','title':'مرجع صدور مجوز فروش آنلاین طلا',
              'date':e.now().date().isoformat(),'publisher':'دیجیاتو',
              'source_type':'rss_summary','evidence_depth':'full_article'}
        other={'id':'S02','title':'وقتی درآمد دیجیتال است و بیمه سنتی',
               'date':e.now().date().isoformat(),'publisher':'زومیت',
               'source_type':'rss_summary','evidence_depth':'full_article'}
        self.assertTrue(e.unrelated_selected_subjects([news,other]))
        self.assertEqual(e.suggested_evidence_pairs([news,other]),[])

    def test_replan_call_count_gate(self):
        usage={'requests_sent':4,'cost_estimated_usd':0.0,'budget_usd':0.02}
        with self.assertRaisesRegex(RuntimeError,'MAX_CALLS reached'):
            e.api_call('never_sent','sys','user',100,usage)

    def test_json_extraction(self):
        self.assertEqual(e.json_from_model('```json\n{"a":1}\n```'),{'a':1})
    def test_bold_repair_preserves_words_and_numbers(self):
        message='🚨 توی فروشگاه لاستیک، قیمت چهار حلقه ۴۰ میلیون می‌شه؛ این فقط مثال فرضیه.'
        story={'slides':[{'n':1,'text':message}]}
        notes=e.repair_missing_bold(story)
        self.assertEqual(len(notes),1)
        amended=story['slides'][0]['text']
        self.assertGreaterEqual(amended.count('**'),2)
        self.assertEqual(amended.replace('**',''),message)
        self.assertEqual(e.repair_missing_bold(story),[])

    def test_bold_repair_keeps_existing_emphasis(self):
        message='یه روز **قیمت خرید** بالا رفت و مشتری مکث کرد.'
        story={'slides':[{'n':1,'text':message}]}
        self.assertEqual(e.repair_missing_bold(story),[])
        self.assertEqual(story['slides'][0]['text'],message)

    def test_variable_length_storyboard_and_additive_background(self):
        s={'id':'S01','title':'رفتار خرید و مشتری','excerpt':'خریدار به قیمت توجه دارد',
           'date':'2026-11-02','evidence_depth':'full_article'}
        a={'id':'S02','title':'رفتار قیمت','excerpt':'تصمیم و قیمت',
           'date':'2026-11-02','evidence_depth':'abstract'}
        frames=[]
        for i in range(1,12):
            scene=(i-1)//3+1
            is_new=(i-1)%3==0
            frames.append({'n':i,'scene_id':scene,
                'visual_action':'new_scene' if is_new else 'add_text',
                'text':'ولی مهدی هنوز نمی‌فهمه مشتری کجا مکث می‌کنه',
                'source_ids':['S01'] if i%2 else ['S02'],
                'visual_idea':'تصویر فروشگاه مهدی'})
        story={'slides':frames,'interaction':{'type':'poll','options':['قیمت','اعتماد']}}
        self.assertEqual(e.story_quality(story,[s,a]),[])
        preview=e.storyboard_frames(story)
        self.assertEqual(len(preview),11)
        self.assertEqual(preview[1]['scene_id'],1)
        self.assertEqual(preview[1]['display_text'].count('ولی مهدی'),2)
        self.assertEqual(preview[3]['display_text'].count('ولی مهدی'),1)
        self.assertEqual(preview[2]['visual_idea'],preview[0]['visual_idea'])

    def test_add_text_without_same_scene_blocked(self):
        sample={'slides':[{'n':1,'scene_id':1,'visual_action':'new_scene',
                            'text':'یه ماجرای عجیب برای مشتری اتفاق افتاد','source_ids':['S01']},
                           {'n':2,'scene_id':2,'visual_action':'add_text',
                            'text':'ولی هنوز نمیدونه چرا','source_ids':['S02']}],
                 'interaction':{'type':'poll','options':['الف','ب']}}
        issues=e.story_quality(sample,[])
        self.assertTrue(any('add_text must keep' in x for x in issues))

    def test_bold_and_emoji_are_optional_on_individual_frames(self):
        story={'slides':[{'n':1,'scene_id':1,'visual_action':'new_scene',
                           'text':'مهدی تازه یه سایت ساخته و خوشحاله', 'source_ids':['S01']},
                          {'n':2,'scene_id':1,'visual_action':'add_text',
                           'text':'ولی سفارش زیادی نمیاد','source_ids':['S02']}],
               'interaction':{'type':'question','question':'چرا؟','options':[]}}
        sources=[{'id':'S01','title':'یک خبر','excerpt':'داستان','evidence_depth':'full_article'},
                 {'id':'S02','title':'یک پژوهش','excerpt':'رفتار','evidence_depth':'abstract'}]
        self.assertEqual(e.story_quality(story,sources),[])

    def test_too_many_accumulated_words_fail_without_count_cap(self):
        text=' '.join(['مشتری']*23)
        story={'slides':[{'n':1,'scene_id':1,'visual_action':'new_scene','text':text,'source_ids':[]},
                         {'n':2,'scene_id':1,'visual_action':'add_text','text':text,'source_ids':[]},
                         {'n':3,'scene_id':1,'visual_action':'add_text','text':text,'source_ids':[]}],
               'interaction':{'type':'poll','options':['الف','ب']}}
        self.assertTrue(any('accumulated scene text' in x for x in e.story_quality(story,[])))

    def test_study_design_survey_vs_experiment(self):
        experimental={'source_type':'academic_doi','evidence_depth':'abstract',
                       'excerpt':'Randomized experiments compared shoppers across conditions.'}
        survey={'source_type':'academic_doi','evidence_depth':'abstract',
                'excerpt':'188 shoppers answered a survey with Likert questionnaires.'}
        self.assertEqual(e.study_design_hint(experimental),'EXPERIMENT_METHOD_IN_ABSTRACT')
        self.assertEqual(e.study_design_hint(survey),'OBSERVATIONAL_SURVEY')

    def test_cinema_filler_and_open_ending_blocked(self):
        frames=[{'n':i,'beat':None,'text':'مهدی یه سایت درست کرد.'} for i in range(1,28)]
        frames[-1]['text']='اما مهدی هنوز نمی‌دونه چرا خرید نمی‌کنن'
        issues=e.cinematic_quality({'slides':frames},[])
        self.assertTrue(any('missing story beat' in x for x in issues))
        self.assertTrue(any('ending reopens' in x for x in issues))
        self.assertTrue(any('resolution missing' in x for x in issues))

    def test_cinema_complete_story(self):
        beats=['hook','setup','conflict','evidence','discovery','action','payoff','cta']
        words=[
            'فرض کن مهدی یه سایت فروشگاه داره',
            'یه روز به آمار سایتش نگاه می‌کنه',
            'بازدید هست ولی خیلی‌ها خرید رو کامل نمی‌کنن',
            'یه مطالعه واقعی درباره نمایش گزینه پرداخت خونده',
            'پس شاید واضح بودن گزینه‌ها هم مهم باشه',
            'روش پرداخت رو زودتر کنار قیمت نشون می‌ده',
            'حالا دو نسخه رو با نرخ خرید واقعی مقایسه می‌کنه',
            'آکولاد می‌تونه همین آزمایش رو طراحی و بررسی کنه',
        ]
        frames=[{'n':i+1,'beat':beat,'text':words[i]}
                for i,beat in enumerate(beats)]
        story={'slides':frames,'resolution':{
            'central_question':'چرا مشتری سبدش رو رها می‌کنه؟',
            'answer':'دلیل قطعی روشن نیست ولی قیمت می‌تونه مانع باشه',
            'action':'قیمت کل و گزینه‌ها رو زودتر نشون بده و نرخ خرید رو بسنج',
            'payoff_frame':7}}
        self.assertEqual(e.cinematic_quality(story,[]),[])

    def test_no_fake_neuromarketing(self):
        story={'slides':[{'beat':'hook','text':'آزمایش نورومارکتینگ: مغز درد می‌کشه!'}]}
        refs=[{'source_type':'academic_doi','evidence_depth':'abstract',
               'excerpt':'Survey 188 respondents using questionnaires'}]
        self.assertTrue(any('unverified experiment' in x for x in e.cinematic_quality(story,refs)))

    def test_iran_payment_news_matches_payment_experiment(self):
        today=e.now().date().isoformat()
        news={'id':'S01','title':'گزارش اسنپ‌پی: سهم خرید اعتباری آنلاین در ایران',
              'publisher':'زومیت','source_type':'rss_summary','evidence_depth':'full_article',
              'date':today,'rank':21}
        academic={'id':'S05','title':'When payment options stand out: Payment option salience on the product page increases purchase likelihood',
                  'publisher':'Journal of Retailing','source_type':'academic_doi',
                  'evidence_depth':'abstract','date':'2026-09-01','rank':30}
        self.assertTrue(e.related_source_pair(news,academic))
        pairs=e.suggested_evidence_pairs([news,academic])
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs[0]['shared_theme'],'payment_option_visibility')
        self.assertNotIn('plan: no shared concrete topic across selected articles',
                         e.validate_plan({'source_ids':['S01','S05']},[news,academic]))

    def test_cinema_flags_filler_transition(self):
        frames=[{'n':1,'beat':'hook','text':'فرض کن مهدی به یک مانع واقعی برخورد کرده'},
                {'n':2,'beat':'conflict','text':'اما مشتری خرید را نیمه کاره رها می‌کند'},
                {'n':3,'beat':'evidence','text':'حالا چی؟'},
                {'n':4,'beat':'action','text':'روش پرداخت را نشان بده'},
                {'n':5,'beat':'payoff','text':'دو نسخه را با شاخص نهایی بسنج'}]
        s={'slides':frames,'resolution':{'central_question':'مانع خرید کجاست؟',
           'answer':'نمایش انتخاب‌ها ممکن است کمک کند',
           'action':'آزمایش دو نسخه صفحه و سود سفارش',
           'payoff_frame':5}}
        self.assertTrue(any('filler transition' in x for x in e.cinematic_quality(s,[])))

    def test_cinema_flags_repeated_text(self):
        beats=['hook','conflict','evidence','action','payoff']
        lines=['فرض کن مهدی سایت فروشگاه داره','مشتری به صفحه محصول می‌رسه',
               'مشتری به صفحه محصول می‌رسه','تغییر مشخص می‌ده','اثر رو می‌سنجه']
        f=[{'beat':b,'text':x} for b,x in zip(beats,lines)]
        s={'slides':f,'resolution':{'central_question':'چرا مشتری خرید نمی‌کند؟',
           'answer':'نامعلوم ولی فرضیه مشخصی داریم','action':'تست نمایش انتخاب‌های پرداخت',
           'payoff_frame':5}}
        self.assertTrue(any('repeats frame' in x for x in e.cinematic_quality(s,[])))

    def test_cinema_flags_order_inversion(self):
        beats=['hook','conflict','action','evidence','payoff']
        f=[{'beat':b,'text':'فریم شماره '+str(i)} for i,b in enumerate(beats)]
        s={'slides':f,'resolution':{'central_question':'چرا خرید سخت شده؟',
           'answer':'داده‌ها راه‌حل قطعی نشان نمی‌دهند','action':'یک تغییر مشخص را آزمایش کن',
           'payoff_frame':5}}
        self.assertIn('cinema: action jumps ahead of evidence',e.cinematic_quality(s,[]))

    def test_model_luna_only(self):
        self.assertEqual(e.MODEL,'gpt-6-luna')
        self.assertEqual(e.MAX_CALLS,4)

if __name__=='__main__':unittest.main()
