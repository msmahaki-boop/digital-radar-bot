import unittest
import acolad_narrative_visual_preview as v

class VisualSafetyTests(unittest.TestCase):
    def test_no_story_changes_on_accumulation(self):
        frames=v.frames_from_story(v.DEMO)
        self.assertEqual(len(frames),6)
        self.assertEqual(frames[0]["scene"],frames[1]["scene"])
        self.assertTrue(frames[1]["text"].startswith(frames[0]["text"]))
        self.assertNotEqual(frames[1]["scene"],frames[2]["scene"])
    def test_markdown_bold_preserved(self):
        w=v.split_markup("یه سایت **خوب** داره")
        self.assertIn(("خوب",True),w)
        self.assertIn(("سایت",False),w)
    def test_stock_query_topic_relevant(self):
        self.assertEqual(v.stock_query(v.DEMO),"online shopping")
    def test_license_failclosed(self):
        class Fake:
            def get(self,*a,**kwargs):
                class Response:
                    def raise_for_status(self):pass
                    def json(self):return {"query":{"pages":{
                        "99":{"title":"File:online shopping.jpeg","imageinfo":[{
                            "width":1920,"height":1080,
                            "thumburl":"https://upload.wikimedia.org/pic.jpg",
                            "extmetadata":{"LicenseShortName":{"value":"All rights reserved"}}}]}}}}
                return Response()
        result=v.select_stock("laptop computer",session=Fake())
        self.assertIsNone(result["chosen"])
        self.assertNotEqual(result["status"],"LICENSED_RELEVANT_CANDIDATE")
    def test_stock_host_locked(self):
        self.assertFalse(v.image_host_allowed("https://unsafe.example/steal"))
    def test_missing_secret_is_never_post(self):
        import os
        previous=os.environ.pop("NOVINHUB_API_TOKEN",None)
        try:self.assertEqual(v.novinhub_readonly()["status"],"SECRET_NOT_VISIBLE_TO_JOB")
        finally:
            if previous is not None:os.environ["NOVINHUB_API_TOKEN"]=previous

if __name__=="__main__":
    unittest.main()
