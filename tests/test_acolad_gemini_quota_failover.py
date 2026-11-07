import os,unittest
from unittest.mock import patch,Mock
import acolad_luna_research_preview as news
import acolad_model_gemini_failover as gemini

def usage():
    return {"requests_sent":0,"cost_estimated_usd":0.0,"budget_usd":0.018,"stages":[]}

class QuotaFailover(unittest.TestCase):
    def setUp(self):
        news.GAPGPT_KEY_QUOTA_BLOCKED_IN_PROCESS=False
        gemini._fallback_calls=0
    def tearDown(self):
        news.GAPGPT_KEY_QUOTA_BLOCKED_IN_PROCESS=False
        gemini._fallback_calls=0
    def test_quota_code_403_switches_to_verified_gemini(self):
        response=Mock(status_code=403)
        response.json.return_value={"error":{"code":"pre_consume_token_quota_failed","message":"opaque"}}
        with patch.object(news.requests,"post",return_value=response) as provider:
            with patch.object(news.model_fallback,"generate_json",return_value={"source_ids":["S01"]}) as alt:
                result=news.api_call("fake","System","Original evidence",500,usage())
        self.assertEqual(result,{"source_ids":["S01"]})
        self.assertTrue(news.GAPGPT_KEY_QUOTA_BLOCKED_IN_PROCESS)
        provider.assert_called_once()
        alt.assert_called_once()
    def test_after_quota_error_only_gemini_no_repeated_gapgpt(self):
        news.GAPGPT_KEY_QUOTA_BLOCKED_IN_PROCESS=True
        with patch.object(news.requests,"post") as provider:
            with patch.object(news.model_fallback,"generate_json",return_value={"ok":True}):
                self.assertEqual(news.api_call("fake","System","Data",500,usage()),{"ok":True})
            provider.assert_not_called()
    def test_unrelated_403_never_bypasses_access_controls(self):
        r=Mock(status_code=403)
        r.json.return_value={"error":{"code":"forbidden","message":"Access denied"}}
        with patch.object(news.requests,"post",return_value=r),patch.object(news.model_fallback,"generate_json") as alt:
            with self.assertRaisesRegex(RuntimeError,"GapGPT HTTP 403"):
                news.api_call("fake","system","data",500,usage())
            alt.assert_not_called()
    def test_valid_gapgpt_still_preferred(self):
        r=Mock(status_code=200)
        r.json.return_value={"choices":[{"message":{"content":'{"ok":true}'}}],"usage":{"prompt_tokens":20,"completion_tokens":8}}
        with patch.object(news.requests,"post",return_value=r),patch.object(news.model_fallback,"generate_json") as alt:
            self.assertEqual(news.api_call("fake","system","data",500,usage()),{"ok":True})
            alt.assert_not_called()
    def test_gemini_response_json_real_shape(self):
        r=Mock(status_code=200)
        r.json.return_value={"candidates":[{"content":{"parts":[{"text":'{"ok":true}'}]}}],
            "usageMetadata":{"promptTokenCount":200,"candidatesTokenCount":30}}
        u=usage()
        with patch.dict(os.environ,{"GEMINI_API_KEY":"test-key-not-real"}):
            with patch.object(gemini.requests,"post",return_value=r) as fn:
                result=gemini.generate_json("System","Story",500,news.json_from_model,u)
        self.assertEqual(result,{"ok":True})
        self.assertEqual(u["gemini_fallback_calls"],1)
        self.assertEqual(u["stages"][-1]["provider"],"gemini-3.1-flash-lite")
        self.assertEqual(fn.call_args.kwargs["json"]["generationConfig"]["responseMimeType"],"application/json")
        self.assertEqual(fn.call_args.kwargs["json"]["generationConfig"]["thinkingConfig"]["thinkingLevel"],"minimal")
    def test_max_tokens_truncated_json_retried_once_with_same_source(self):
        first=Mock(status_code=200)
        first.json.return_value={"candidates":[{"finishReason":"MAX_TOKENS",
            "content":{"parts":[{"text":'{"unfinished":'}]}}]}
        second=Mock(status_code=200)
        second.json.return_value={"candidates":[{"finishReason":"STOP",
            "content":{"parts":[{"text":'{"ok":true}'}]}}]}
        with patch.dict(os.environ,{"GEMINI_API_KEY":"test-key-not-real"}):
            with patch.object(gemini.requests,"post",side_effect=[first,second]) as post:
                result=gemini.generate_json("SYSTEM","UNCHANGED ORIGINAL EVIDENCE",
                    500,news.json_from_model,usage())
        self.assertEqual(result,{"ok":True})
        self.assertEqual(post.call_count,2)
        self.assertEqual(post.call_args_list[0].kwargs["json"]["contents"],
                         post.call_args_list[1].kwargs["json"]["contents"])
        self.assertEqual(post.call_args_list[1].kwargs["json"]["generationConfig"]["maxOutputTokens"],2700)
        self.assertEqual(gemini._fallback_calls,2)
    def test_malformed_non_truncated_json_does_not_retry(self):
        r=Mock(status_code=200)
        r.json.return_value={"candidates":[{"finishReason":"STOP",
            "content":{"parts":[{"text":'{"unfinished":'}]}}]}
        with patch.dict(os.environ,{"GEMINI_API_KEY":"test-key-not-real"}):
            with patch.object(gemini.requests,"post",return_value=r) as post:
                with self.assertRaisesRegex(RuntimeError,"FINISH_STOP"):
                    gemini.generate_json("SYS","EVIDENCE",500,news.json_from_model,usage())
        self.assertEqual(post.call_count,1)
    def test_second_truncated_json_fails_closed_after_one_retry(self):
        r=Mock(status_code=200)
        r.json.return_value={"candidates":[{"finishReason":"MAX_TOKENS",
            "content":{"parts":[{"text":'{"unfinished":'}]}}]}
        with patch.dict(os.environ,{"GEMINI_API_KEY":"test-key-not-real"}):
            with patch.object(gemini.requests,"post",return_value=r) as post:
                with self.assertRaisesRegex(RuntimeError,"FINISH_MAX_TOKENS"):
                    gemini.generate_json("SYS","EVIDENCE",500,news.json_from_model,usage())
        self.assertEqual(post.call_count,2)
    def test_missing_google_secret_stops_before_external_send(self):
        with patch.dict(os.environ,{"GEMINI_API_KEY":""}):
            with patch.object(gemini.requests,"post") as send:
                with self.assertRaisesRegex(RuntimeError,"SECRET_MISSING"):
                    gemini.generate_json("a","b",500,news.json_from_model,usage())
                send.assert_not_called()
    def test_bad_google_json_never_passes_as_story(self):
        r=Mock(status_code=200)
        r.json.return_value={"candidates":[{"content":{"parts":[{"text":"bad JSON"}]}}]}
        with patch.dict(os.environ,{"GEMINI_API_KEY":"test-key-not-real"}):
            with patch.object(gemini.requests,"post",return_value=r):
                with self.assertRaisesRegex(RuntimeError,"GEMINI_FALLBACK_INVALID_JSON"):
                    gemini.generate_json("System","Story",500,news.json_from_model,usage())
    def test_total_fallback_cap_remains_hard(self):
        gemini._fallback_calls=gemini.MAX_TOTAL_FALLBACK_CALLS
        with patch.dict(os.environ,{"GEMINI_API_KEY":"test-key-not-real"}):
            with self.assertRaisesRegex(RuntimeError,"DAILY_CALL_LIMIT"):
                gemini.generate_json("a","b",500,news.json_from_model,usage())
if __name__=="__main__":unittest.main()
