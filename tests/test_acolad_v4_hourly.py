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
 def test_post_list_inclusive_day_exclusive_next_day_boundary(self):
  seen={}
  def fake_get(url,headers,params,timeout):
   seen.update(params)
   return Response(200,{"data":[]})
  with patch.object(p.requests,"get",side_effect=fake_get):
   self.assertEqual(p.provider_list("key","telegram",date(2026,11,7)),[])
  self.assertEqual(seen["publish_from"],"2026-11-07")
  self.assertEqual(seen["publish_to"],"2026-11-08")
 def test_bale_validation_is_explicit_refusal_not_ambiguous_network_acceptance(self):
  rejected=Response(400,{"error":{"type":"ValidationException",
      "message":"Invalid post payload","trace_id":"private-trace"}})
  with patch.object(p.requests,"post",return_value=rejected):
   with self.assertRaisesRegex(p.ProviderValidationRejected,"IMMEDIATE_POST_HTTP_bale_400"):
    p.send_now("key","bale","body",[])
 def test_unknown_telegram_receipt_does_not_prevent_independent_bale(self):
  import tempfile
  from pathlib import Path
  day=date(2026,11,7)
  states={"telegram":{"state":"PENDING_OR_UNKNOWN"},
          "bale":{"state":"ABSENT"},
          "instagram":{"state":"PENDING_OR_UNKNOWN"}}
  with tempfile.TemporaryDirectory() as root:
   with (patch.dict(os.environ,{"ACOLAD_HOURLY_PUBLISH_APPROVAL":p.APPROVAL}),
        patch.object(p,"OUT",Path(root)),
        patch.object(p,"token",return_value="key"),
        patch.object(p,"now",return_value=__import__('datetime').datetime(2026,11,7,19,0,tzinfo=p.TZ)),
        patch.object(p,"observe",return_value=states),
        patch.object(p,"provider_list",return_value=[]),
        patch.object(p,"existing_bundle",return_value=({"captions":{"bale":"approved copy"}},[])),
        patch.object(p,"send_now",return_value=888) as send,
        patch.object(p.time,"sleep",return_value=None)):
    result=p.execute("immediate")
    self.assertEqual(result["status"],"SUBMITTED_WAITING_EXTERNAL_PUBLICATION")
    send.assert_called_once_with("key","bale","approved copy",[])
 def test_failed_bale_validation_does_not_prevent_original_instagram_story(self):
  import tempfile
  from pathlib import Path
  states={"telegram":{"state":"PUBLISHED","ids":[3698156]},
          "bale":{"state":"ABSENT"},
          "instagram":{"state":"ABSENT"}}
  uploads=[Path(f"frame_{i:02d}.png") for i in range(7)]
  with tempfile.TemporaryDirectory() as root:
   with (patch.dict(os.environ,{"ACOLAD_HOURLY_PUBLISH_APPROVAL":p.APPROVAL}),
        patch.object(p,"OUT",Path(root)),
        patch.object(p,"token",return_value="key"),
        patch.object(p,"now",return_value=__import__('datetime').datetime(2026,11,7,19,0,tzinfo=p.TZ)),
        patch.object(p,"observe",return_value=states),
        patch.object(p,"provider_list",return_value=[]),
        patch.object(p,"existing_bundle",return_value=({"captions":{"bale":"reviewed bale","instagram":"reviewed instagram"}},uploads)),
        patch.object(p,"upload_file",side_effect=list(range(100,107))),
        patch.object(p,"send_now",side_effect=[p.ProviderValidationRejected("IMMEDIATE_POST_HTTP_bale_400"),999]) as send,
        patch.object(p.time,"sleep",return_value=None)):
    result=p.execute("immediate")
    self.assertEqual(send.call_count,2)
    self.assertEqual(send.call_args_list[0].args[1],"bale")
    self.assertEqual(send.call_args_list[1].args[1],"instagram")
    self.assertFalse(result["publication_verified"])
    import json
    intents=json.loads((Path(root)/"send_intents.json").read_text(encoding='utf8'))
    self.assertEqual(intents["sent_or_unknown"]["bale"]["state"],"REJECTED_VALIDATION_400")
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
 def test_bad_provider_format_fails_closed(self):
  with patch.object(p.requests,"get",return_value=Response(200,{"bad":1})):
   with self.assertRaisesRegex(RuntimeError,"PROVIDER_LIST_UNRECOGNIZED"):
    p.provider_list("key","telegram",date(2026,11,7))

if __name__=="__main__":unittest.main()
