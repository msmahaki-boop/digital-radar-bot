import unittest
from acolad_new_telegram_preview import same_event,is_evergreen,select_new_topics

class BridgeTests(unittest.TestCase):
    def test_cross_source_same_event(self):
        a={'url':'https://peivast.com/p/268958','title':'اسنپ و دیجی کالا بالاترین امتیاز تجربه کاربری را کسب کردند'}
        b={'url':'https://dmboard.media/example','title':'دیجی کالا و اسنپ در ارزیابی تجربه کاربری پلتفرم های بومی در سطح اول قرار گرفتند'}
        self.assertTrue(same_event(a,b))
    def test_tutorial_vs_news(self):
        self.assertTrue(is_evergreen({'title':'چرا با افزایش فروش، سود کسب و کار بیشتر نمی شود؟ ۷ نکته','excerpt':'راهنمای کلی مدیریت سود'}))
        self.assertFalse(is_evergreen({'title':'اسنپ و دیجی کالا بالاترین امتیاز تجربه کاربری را کسب کردند','excerpt':'طبق گزارش تازه'}))
    def test_dedup_across_topics(self):
        def item(t,score,url):
            return {'title':t,'excerpt':'توضیحات مربوط به یک خبر معتبر واقعی با اطلاعات کافی برای بررسی تخصصی', 'url':url,'score':score,'source':'publisher','decision':'consider'}
        a=item('انجمن تجارت الکترونیک درباره طرح نظام بخشی فضای مجازی انتقاد کرد',85,'https://example.com/a')
        b=item('انجمن تجارت الکترونیک درباره طرح نظام بخشی فضای مجازی انتقاد کرد',78,'https://example.com/a')
        c=item('اسنپ و دیجی کالا بالاترین امتیاز تجربه کاربری را کسب کردند',82,'https://example.com/c')
        report={'topics':{'iran_economy':{'status':'OK (model)','items':[a]},'small_business_growth':{'status':'OK (model)','items':[b]},'iran_platforms':{'status':'OK (model)','items':[c]}}}
        selected, skips=select_new_topics(report)
        self.assertEqual([s['category'] for s in selected],['iran_economy','iran_platforms'])
        self.assertTrue(any('same event' in s.get('reason','') for s in skips))

if __name__=='__main__':unittest.main()
