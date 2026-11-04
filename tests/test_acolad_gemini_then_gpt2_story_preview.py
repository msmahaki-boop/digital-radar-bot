import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import acolad_gemini_then_gpt2_story_preview as p

class MockResponse:
    def __init__(self,status,data=None):
        self.status_code=status;self.data=data or {}
    def json(self):return self.data

class Session:
    def __init__(self,statuses):
        self.statuses=list(statuses);self.post_calls=[];self.get_calls=[]
    def get(self,url,**kwargs):
        self.get_calls.append(url)
        return MockResponse(200,{"data":[{"id":p.GEMINI},{"id":p.FALLBACK}]})
    def post(self,url,**kwargs):
        self.post_calls.append(kwargs["json"]["model"])
        return MockResponse(self.statuses.pop(0))

class FakeArt:
    def save(self,*args,**kwargs):pass

class Tests(unittest.TestCase):
    def test_exact_stories_and_preview(self):
        story=p.make_story()
        self.assertEqual(len(story["slides"]),8)
        self.assertTrue(story["is_fictional_character"])
        self.assertEqual(story["publication_permission"],"NONE_PREVIEW_ONLY")
    def test_one_503_then_fallback_one_call(self):
        s=Session([503,429])
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"test"}),tempfile.TemporaryDirectory() as tmp,patch.object(p,"render",return_value={"test":"mock"}):
            # Make eight fake files to mock actual rendering without brand fonts.
            def fake_render(story,output,allow_stock):
                Path(output).mkdir(parents=True,exist_ok=True)
                for n in range(1,9):(Path(output)/f"story_{n:02d}.png").write_bytes(b"test")
                return {"status":"FROZEN_LAYOUT_PREVIEW_ONLY"}
            with patch.object(p,"render",side_effect=fake_render):
                r=p.run(s,p.APPROVAL,tmp)
        self.assertEqual(s.post_calls,[p.GEMINI,p.FALLBACK])
        self.assertEqual(r["image_requests"],2)
        self.assertEqual(r["published"],0)
    def test_429_does_not_fallback(self):
        s=Session([429])
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"test"}),tempfile.TemporaryDirectory() as tmp:
            def fake_render(story,output,allow_stock):
                Path(output).mkdir(parents=True,exist_ok=True)
                for n in range(1,9):(Path(output)/f"story_{n:02d}.png").write_bytes(b"test")
                return {}
            with patch.object(p,"render",side_effect=fake_render):
                r=p.run(s,p.APPROVAL,tmp)
        self.assertEqual(s.post_calls,[p.GEMINI])
        self.assertFalse(r["fallback_executed_only_after_gemini_http_503"])
    def test_no_approval_no_spend(self):
        s=Session([])
        with patch.dict(os.environ,{"GAPGPT_API_KEY":"test"}),tempfile.TemporaryDirectory() as tmp:
            def fake_render(story,output,allow_stock):
                Path(output).mkdir(parents=True,exist_ok=True)
                for n in range(1,9):(Path(output)/f"story_{n:02d}.png").write_bytes(b"test")
                return {}
            with patch.object(p,"render",side_effect=fake_render):
                r=p.run(s,"",tmp)
        self.assertEqual(s.post_calls,[])
        self.assertEqual(r["image_requests"],0)

if __name__=="__main__":unittest.main()
