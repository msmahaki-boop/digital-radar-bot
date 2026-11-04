import base64
import io
import os
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import acolad_gapgpt_gemini25_one_image as g

class Reply:
    def __init__(self,status=200,obj=None,payload=b""):
        self.status_code=status;self.obj=obj or {};self.content=payload
    def json(self):return self.obj

class Session:
    def __init__(self,listed=True,post=None,image=None):
        self.listed=listed;self.post_reply=post;self.image=image;self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append(("GET",url))
        if url.endswith("/models"):
            return Reply(obj={"data":[{"id":g.MODEL if self.listed else "unrelated"}]})
        return self.image
    def post(self,url,**kwargs):
        self.calls.append(("POST",url,kwargs["json"]))
        return self.post_reply

def sample_png():
    f=io.BytesIO()
    Image.new("RGB",(1024,1024),"white").save(f,"PNG")
    return f.getvalue()

class ModelTests(unittest.TestCase):
    def test_catalog_model_id(self):
        session=Session()
        self.assertTrue(g.check_catalog(session,"key")["model_present"])
        self.assertFalse(any(x[0]=="POST" for x in session.calls))
    def test_no_approval_no_post(self):
        s=Session()
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"test"}),tempfile.TemporaryDirectory() as d:
            r=g.run("generate","",d,s)
        self.assertEqual(r["status"],"APPROVAL_REQUIRED")
        self.assertFalse(any(x[0]=="POST" for x in s.calls))
    def test_no_model_no_post(self):
        s=Session(listed=False)
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"test"}),tempfile.TemporaryDirectory() as d:
            r=g.run("generate",g.APPROVAL,d,s)
        self.assertEqual(r["status"],"MODEL_NOT_AVAILABLE_NO_CHARGE")
        self.assertFalse(any(x[0]=="POST" for x in s.calls))
    def test_api_http_error_is_not_success(self):
        s=Session(post=Reply(status=429))
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"test"}),tempfile.TemporaryDirectory() as d:
            r=g.run("generate",g.APPROVAL,d,s)
        self.assertEqual(r["status"],"IMAGE_HTTP_ERROR")
        self.assertEqual(r["image_result"]["http_status"],429)
        self.assertEqual(sum(x[0]=="POST" for x in s.calls),1)
    def test_b64_image_one_call(self):
        encoded=base64.b64encode(sample_png()).decode()
        s=Session(post=Reply(obj={"data":[{"b64_json":encoded}]}))
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"test"}),tempfile.TemporaryDirectory() as d:
            r=g.run("generate",g.APPROVAL,d,s)
        self.assertEqual(r["status"],"IMAGE_VERIFIED")
        self.assertEqual(r["image_result"]["response_type"],"b64_json")
        self.assertEqual(sum(x[0]=="POST" for x in s.calls),1)
        self.assertEqual(r["published"],0)
    def test_url_image_one_call(self):
        s=Session(post=Reply(obj={"data":[{"url":"https://images.example.org/g.png"}]}),
                  image=Reply(payload=sample_png()))
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"test"}),tempfile.TemporaryDirectory() as d:
            r=g.run("generate",g.APPROVAL,d,s)
        self.assertEqual(r["status"],"IMAGE_VERIFIED")
        self.assertEqual(r["image_result"]["response_type"],"url")
        self.assertEqual(sum(x[0]=="POST" for x in s.calls),1)
    def test_prompt_no_specific_artist_or_UI(self):
        self.assertIn("NO phone",g.PROMPT)
        self.assertIn("75 percent",g.PROMPT)
        self.assertNotIn("Shel Silverstein",g.PROMPT)
    def test_preflight_no_generation(self):
        s=Session()
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"test"}),tempfile.TemporaryDirectory() as d:
            r=g.run("preflight",output=d,session=s)
        self.assertEqual(r["external_generation_requests"],0)
        self.assertFalse(any(x[0]=="POST" for x in s.calls))

if __name__=="__main__":unittest.main()
