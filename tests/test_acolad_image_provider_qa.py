import base64
import io
import os
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import acolad_image_provider_qa as q

BRIEF={"article_fact":"The verified source reports a test of a new online checkout process.",
       "scene_idea":"A tiny shop owner watches an oversized shopping basket with one missing wheel.",
       "stock_query":"small business shopping cart"}

class Reply:
    def __init__(self,status=200,payload=None):
        self.status_code=status;self.payload=payload or {}
    def json(self):return self.payload

class Session:
    def __init__(self,post=None,get=None):self.post_reply=post;self.get_reply=get;self.calls=[]
    def post(self,*args,**kw):self.calls.append(("post",args,kw));return self.post_reply
    def get(self,*args,**kw):self.calls.append(("get",args,kw));return self.get_reply

class ProviderTests(unittest.TestCase):
    def test_different_scenes_make_different_prompts(self):
        b=dict(BRIEF);b["scene_idea"]="A different metaphor with paper boats sailing through a maze."
        self.assertNotEqual(q.scene_prompt(BRIEF),q.scene_prompt(b))
    def test_no_fabricated_empty_prompt(self):
        with self.assertRaises(ValueError):q.scene_prompt({"scene_idea":"x","article_fact":"y"})
    def test_no_approval_never_calls_openai(self):
        s=Session()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{"PEXELS_API_KEY":""}):
            result=q.run(BRIEF,tmp,approval=False,session=s)
        self.assertFalse(s.calls)
        self.assertEqual(result["image"]["status"],"PAID_GENERATION_NOT_APPROVED")
        self.assertEqual(result["published"],0)
    def test_429_requires_no_fake_image(self):
        s=Session(post=Reply(429))
        with patch.dict(os.environ,{"OPENAI_API_KEY":"placeholder"}):
            image,status=q.generate_openai(BRIEF,s)
        self.assertIsNone(image)
        self.assertEqual(status["status"],"LIMIT_OR_CREDIT")
    def test_valid_image_is_verified(self):
        im=Image.new("RGB",(600,800),"white");f=io.BytesIO();im.save(f,format="PNG")
        s=Session(post=Reply(200,{"data":[{"b64_json":base64.b64encode(f.getvalue()).decode()}]}))
        with patch.dict(os.environ,{"OPENAI_API_KEY":"placeholder"}):
            result,status=q.generate_openai(BRIEF,s)
        self.assertEqual(status["status"],"IMAGE_VERIFIED")
        self.assertEqual(result.size,(600,800))
    def test_stock_keeps_license_and_review(self):
        s=Session(get=Reply(200,{"photos":[{"id":23,"url":"https://www.pexels.com/photo/23/","src":{"large2x":"https://images.pexels.com/photo.jpg"},"photographer":"Jane"}]}))
        with patch.dict(os.environ,{"PEXELS_API_KEY":"placeholder"}):
            status=q.stock_candidate(BRIEF,s)
        self.assertEqual(status["status"],"STOCK_CANDIDATE_REQUIRES_HUMAN_REVIEW")
        self.assertIn("license_url",status)
    def test_no_stock_key_no_network(self):
        s=Session()
        with patch.dict(os.environ,{"PEXELS_API_KEY":""}):
            self.assertEqual(q.stock_candidate(BRIEF,s)["status"],"STOCK_UNAVAILABLE")
        self.assertFalse(s.calls)

if __name__=="__main__":unittest.main()
