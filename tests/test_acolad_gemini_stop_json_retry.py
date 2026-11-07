import json,os,unittest
from unittest.mock import patch
import acolad_model_gemini_failover as g

class FakeResponse:
    status_code=200
    def __init__(self,content,reason="STOP"):
        self.content=content
        self.reason=reason
    def json(self):
        return {"candidates":[{"content":{"parts":[{"text":self.content}]},
                               "finishReason":self.reason}],
                "usageMetadata":{"promptTokenCount":23,"candidatesTokenCount":30}}

class FakeSession:
    def __init__(self,*replies):
        self.replies=list(replies)
        self.payloads=[]
    def post(self,url,headers,json,timeout):
        self.payloads.append(json)
        assert len(self.replies),"unexpected third request"
        return self.replies.pop(0)

class SafeRetry(unittest.TestCase):
    def setUp(self):
        self.k=patch.dict(os.environ,{"GEMINI_API_KEY":"fake_key_no_real_secret"})
        self.reset=patch.object(g,"_fallback_calls",0)
        self.k.start();self.reset.start()
    def tearDown(self):
        self.k.stop();self.reset.stop()
    def test_stop_but_invalid_json_retry_with_lower_temperature(self):
        s=FakeSession(FakeResponse('{"ok":'),FakeResponse('{"ok":true}'))
        result=g.generate_json("instructions","original evidence",650,json.loads,{},session=s)
        self.assertEqual(result,{"ok":True})
        self.assertEqual(len(s.payloads),2)
        self.assertEqual(s.payloads[0]["generationConfig"]["temperature"],0.55)
        self.assertEqual(s.payloads[1]["generationConfig"]["temperature"],0.12)
        self.assertEqual(s.payloads[1]["contents"],s.payloads[0]["contents"])
        self.assertEqual(s.payloads[1]["systemInstruction"],s.payloads[0]["systemInstruction"])
        self.assertEqual(s.payloads[1]["generationConfig"]["maxOutputTokens"],650)
    def test_second_stop_invalid_json_must_fail_closed(self):
        s=FakeSession(FakeResponse('{"no":'),FakeResponse('{"still_no":'))
        with self.assertRaisesRegex(RuntimeError,"GEMINI_FALLBACK_INVALID_JSON"):
            g.generate_json("inst","evidence",1000,json.loads,{},session=s)
        self.assertEqual(len(s.payloads),2)
    def test_max_tokens_retry_increases_token_budget_only_once(self):
        s=FakeSession(FakeResponse('{"no":',"MAX_TOKENS"),FakeResponse('{"ok":true}',"STOP"))
        self.assertTrue(g.generate_json("inst","evidence",5900,json.loads,{},session=s)["ok"])
        self.assertEqual(s.payloads[1]["generationConfig"]["maxOutputTokens"],8100)
    def test_non_200_http_never_retries(self):
        s=FakeSession(FakeResponse('{"ok":true}'))
        s.replies[0].status_code=403
        with self.assertRaisesRegex(RuntimeError,"GEMINI_FALLBACK_HTTP_403"):
            g.generate_json("inst","evidence",600,json.loads,{},session=s)
        self.assertEqual(len(s.payloads),1)

if __name__=="__main__":unittest.main()
