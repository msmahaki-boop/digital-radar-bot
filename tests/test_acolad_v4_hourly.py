import os,unittest
from datetime import date
from unittest.mock import patch
import acolad_v4_hourly_publish as p
import acolad_daily_editorial_v1 as ed

class Response:
 def __init__(self,code=201,content=None):
  self.status_code=code;self.content=content if content is not None else {"data":{"id":998}}
 def json(self):return self.content

class HourlySafety(unittest.TestCase):
 def test_old_doi_not_eligible_for_daily_publication(self):
  day=date(2026,11,7)
  old=[{"date":"2026-01-01","evidence_depth":"abstract","source_type":"academic_doi"}]
  recent=[{"date":"2026-11-04","evidence_depth":"full_article","source_type":"rss_summary"}]
  self.assertFalse(p.has_current_substantive_evidence(old,day))
  self.assertTrue(p.has_current_substantive_evidence(recent,day))
  self.assertFalse(p.has_current_substantive_evidence([{"date":"2026-11-09","evidence_depth":"abstract"}],day))
  self.assertFalse(p.has_current_substantive_evidence([{"date":"2026-11-06","evidence_depth":"headline_only"}],day))
 def test_stale_verified_checkpoint_falls_through_to_fresh_generation(self):
  import json,tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as d:
   stale=Path(d)/"verified_story_checkpoint.json"
   stale.write_text(json.dumps({"day":"2026-11-07","validated":True,
      "story":{"slides":[]},"evidence":[{"date":"2026-01-01","evidence_depth":"abstract"}]}))
   with patch.object(p,"EDITORIAL_CACHE",stale),patch.object(p,"check_verified_editorial") as validator:
    self.assertIsNone(p.saved_editorial(date(2026,11,7)))
    validator.assert_not_called()
 def test_pending_is_never_absent(self):
  a=p.assess([{"id":17,"post":[{"account_id":233472,"status":"in_progress"}]}],"telegram")
  self.assertEqual(a["state"],"PENDING_OR_UNKNOWN")
 def test_published_requires_external_receipt(self):
  a=[{"id":17,"post":[{"account_id":233472,"status":"published","accountPost":{"post_id":"123"}}]}]
  self.assertEqual(p.assess(a,"telegram")["state"],"PUBLISHED")
  a[0]["post"][0]["accountPost"]={}
  self.assertEqual(p.assess(a,"telegram")["state"],"PENDING_OR_UNKNOWN")
 def test_failed_not_double_sent(self):
  a=[{"id":17,"post":[{"account_id":233497,"status":"failed"}]}]
  self.assertEqual(p.assess(a,"bale"),{"state":"FAILED","group_id":17})
 def test_immediate_post_not_draft_or_scheduled(self):
  payload={}
  def fake(url,headers,json,timeout):
   payload.update(json);return Response()
  with patch.object(p.requests,"post",side_effect=fake):
   self.assertEqual(p.send_now("key","telegram","hello",[]),998)
  self.assertEqual((payload["is_draft"],payload["is_scheduled"]),(0,0))
  self.assertEqual(payload["type"],"text")
 def test_story_has_all_image_ids(self):
  payload={}
  def fake(url,headers,json,timeout):
   payload.update(json);return Response()
  with patch.object(p.requests,"post",side_effect=fake):
   p.send_now("key","instagram","caption",[1,2,3,4,5,6,7,8,9])
  self.assertEqual(payload["type"],"story")
  self.assertEqual(len(payload["media_ids"]),9)
  self.assertEqual(payload["is_scheduled"],0)
 def test_bale_payload(self):
  payload={}
  def fake(url,headers,json,timeout):
   payload.update(json);return Response()
  with patch.object(p.requests,"post",side_effect=fake):p.send_now("key","bale","body",[])
  self.assertEqual(payload["bale_has_signature"],0)
 def test_approval_missing_blocks_network(self):
  with patch.dict(os.environ,{"ACOLAD_HOURLY_PUBLISH_APPROVAL":"NO"}),patch.object(p,"token") as tok:
   r=p.execute("immediate")
   self.assertEqual(r["status"],"BLOCKED_APPROVAL_GATE")
   tok.assert_not_called()
 def test_three_successes_quit_today_without_cost(self):
  allgood={x:{"state":"PUBLISHED"} for x in p.NETWORKS}
  with patch.dict(os.environ,{"ACOLAD_HOURLY_PUBLISH_APPROVAL":p.APPROVAL}),patch.object(p,"token",return_value="key"),patch.object(p,"observe",return_value=allgood),patch.object(p,"prepare") as prep:
   r=p.execute("immediate")
   self.assertTrue(r["publication_verified"])
   prep.assert_not_called()
 def test_content_conflict_is_metadata_only(self):
  item={"slides":[{"beat":"hook","text":"شروع"},{"beat":"setup","text":"ولی راه نبود"},{"beat":"payoff","text":"پایان"}]}
  a,changed=ed.repair_missing_conflict_beat(item)
  self.assertTrue(changed)
  self.assertEqual(a["slides"][1]["beat"],"conflict")
  self.assertEqual([x["text"] for x in item["slides"]],[x["text"] for x in a["slides"]])
 def test_overlong_scene_repair_preserves_source(self):
  x={"slides":[
   {"scene_id":1,"visual_action":"new_scene","text":"الف","source_ids":["S1"],"beat":"hook"},
   {"scene_id":1,"visual_action":"add_text","text":"ب","source_ids":["S1"],"beat":"evidence"},
   {"scene_id":1,"visual_action":"add_text","text":"ج","source_ids":["S1"],"beat":"payoff"}]}
  a,changed=ed.repair_overlong_progressive_scene(x,["frame 3: accumulated scene text 64 words, change background sooner"])
  self.assertTrue(changed)
  self.assertNotEqual(a["slides"][2]["scene_id"],a["slides"][1]["scene_id"])
  self.assertEqual([f["text"] for f in a["slides"]],[f["text"] for f in x["slides"]])
 def test_novinhub_date_window_contains_same_day_published_message(self):
  from unittest.mock import Mock
  from datetime import date
  response=Response(200,{"data":[{"id":3698156,"post":[{"account_id":233472,
      "status":"published","accountPost":{"post_id":"47"}}]}]})
  with patch.object(p.requests,"get",return_value=response) as fetch:
   result=p.provider_list("not-real","telegram",date(2026,11,7))
  self.assertEqual(fetch.call_args.kwargs["params"]["publish_to"],"2026-11-08")
  self.assertEqual(p.assess(result,"telegram")["state"],"PUBLISHED")
 def test_bale_400_diagnostic_never_dumps_caption(self):
  payload={"error":{"errors":{"caption":["invalid text"]},"trace_id":"ABC123"}}
  with patch.object(p.requests,"post",return_value=Response(400,payload)):
   with self.assertRaises(RuntimeError) as issue:
    p.send_now("not-real","bale","PRIVATE CAPTION CONTENT",[])
  message=str(issue.exception)
  self.assertIn("IMMEDIATE_POST_HTTP_bale_400",message)
  self.assertIn("FIELDS_caption",message)
  self.assertNotIn("PRIVATE CAPTION CONTENT",message)
 def test_bad_provider_format_fails_closed(self):
  with patch.object(p.requests,"get",return_value=Response(200,{"bad":1})):
   with self.assertRaisesRegex(RuntimeError,"PROVIDER_LIST_UNRECOGNIZED"):
    p.provider_list("key","telegram",date(2026,11,7))

if __name__=="__main__":unittest.main()
