import base64
import io
import os
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import acolad_gapgpt_qwen_image_once as q

class Reply:
    def __init__(self,status=200,data=None,content=b""):
        self.status_code=status
        self.data={} if data is None else data
        self.content=content
    def json(self):return self.data

class Session:
    def __init__(self,catalog=None,post=None,asset=None):
        self.catalog=catalog or Reply(200,{"data":[{"id":q.MODEL}]})
        self.post_reply=post
        self.asset=asset
        self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append(("GET",url))
        return self.catalog if url.endswith("/models") else self.asset
    def post(self,url,**kwargs):
        self.calls.append(("POST",url,kwargs["json"]))
        return self.post_reply

def png():
    b=io.BytesIO()
    Image.new("RGB",(1024,1024),"white").save(b,format="PNG")
    return b.getvalue()

class QwenTests(unittest.TestCase):
    def test_catalog_does_not_post(self):
        s=Session()
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"placeholder"}),tempfile.TemporaryDirectory() as d:
            result=q.run("preflight",output=d,session=s)
        self.assertEqual(result["status"],"PREFLIGHT_DONE")
        self.assertEqual(len([x for x in s.calls if x[0]=="POST"]),0)
    def test_no_generate_without_approval(self):
        s=Session()
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"placeholder"}),tempfile.TemporaryDirectory() as d:
            result=q.run("generate",output=d,session=s)
        self.assertEqual(result["status"],"APPROVAL_REQUIRED")
        self.assertFalse(any(x[0]=="POST" for x in s.calls))
    def test_b64(self):
        s=Session(post=Reply(200,{"data":[{"b64_json":base64.b64encode(png()).decode()}]}))
        image,status=q.generate_once("placeholder",s)
        self.assertEqual(status["response_type"],"b64_json")
        self.assertEqual(image.size,(1024,1024))
    def test_url(self):
        url="https://images.example.org/image.png"
        s=Session(post=Reply(200,{"data":[{"url":url}]}),asset=Reply(content=png()))
        image,status=q.generate_once("placeholder",s)
        self.assertEqual(status["response_type"],"url")
        self.assertEqual(image.size,(1024,1024))
    def test_http_error_no_fake_image(self):
        s=Session(post=Reply(429,{"error":{"message":"dont log"}}))
        image,status=q.generate_once("placeholder",s)
        self.assertIsNone(image)
        self.assertEqual(status,{"status":"GENERATE_HTTP_ERROR","http_status":429})
    def test_no_internal_url(self):
        with self.assertRaises(ValueError):q._safe_image_url("http://127.0.0.1/img")
        with self.assertRaises(ValueError):q._safe_image_url("https://127.0.0.1/img")
    def test_one_call_only(self):
        s=Session(post=Reply(200,{"data":[{"b64_json":base64.b64encode(png()).decode()}]}))
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"placeholder"}),tempfile.TemporaryDirectory() as d:
            r=q.run("generate",q.APPROVAL,d,s)
        self.assertEqual(r["status"],"IMAGE_VERIFIED")
        self.assertEqual(len([x for x in s.calls if x[0]=="POST"]),1)
        self.assertEqual(r["published"],0)
    def test_unlisted_model_blocks_spend(self):
        s=Session(catalog=Reply(200,{"data":[{"id":"other"}]}))
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"placeholder"}),tempfile.TemporaryDirectory() as d:
            r=q.run("generate",q.APPROVAL,d,s)
        self.assertEqual(r["status"],"MODEL_NOT_VERIFIED_STOP_BEFORE_SPEND")
        self.assertFalse(any(x[0]=="POST" for x in s.calls))

if __name__=="__main__":unittest.main()
