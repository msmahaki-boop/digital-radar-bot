import unittest
from datetime import datetime,date
from zoneinfo import ZoneInfo
from unittest.mock import patch
import acolad_v4_daily_autopublish as p

class Response:
 def __init__(self,code=200,data=None):
  self.status_code=code;self.data=data or {}
 def json(self):return self.data

class Safety(unittest.TestCase):
 def test_publication_times_tehran(self):
  d=date(2026,11,5)
  self.assertEqual(p.due(d,"telegram").strftime("%H:%M"),"17:30")
  self.assertEqual(p.due(d,"bale").strftime("%H:%M"),"17:35")
  self.assertEqual(p.due(d,"instagram").strftime("%H:%M"),"18:00")
 def test_window_closes_before_publication(self):
  with patch.object(p,"tehran_now",return_value=datetime(2026,11,5,17,1,tzinfo=ZoneInfo("Asia/Tehran"))):
   with self.assertRaisesRegex(RuntimeError,"SAFE_SCHEDULING_WINDOW"):
    p.check_time()
 def test_real_bale_submission_not_a_draft(self):
  payload={}
  def fake(url,headers,json,timeout):
   payload.update(json);return Response(201,{"data":{"id":123}})
  with patch.object(p.requests,"post",side_effect=fake):
   self.assertEqual(p.schedule_bale("key","text",1793885700),123)
  self.assertEqual([payload["is_scheduled"],payload["is_draft"]],[1,0])
  self.assertEqual(payload["account_ids"],[233497])
 def test_wrong_account_blocks_all_networks(self):
  with patch.object(p.requests,"get",return_value=Response(200,{"data":[{"id":230527,"type":"instagram"}]})):
   with self.assertRaisesRegex(RuntimeError,"UNVERIFIED"):p.provider_accounts("test")
 def test_any_existing_post_blocks_duplicate(self):
  with patch.object(p,"provider_accounts"),patch.object(p,"posted_for_day",side_effect=[[],[{"id":1}],[]]):
   with self.assertRaisesRegex(RuntimeError,"DAILY_PROVIDER_POST_EXISTS"):
    p.preflight("key",date(2026,11,5))
 def test_absent_approval_never_submits(self):
  with patch.object(p,"check_time",return_value=date(2026,11,5)),patch.object(p,"token",return_value="x"),patch.object(p,"preflight"),patch.object(p,"generate_editorial",return_value=({"slides":[{"text":"Hi"}]},[{"url":"https://example.com"}])),patch.object(p,"make_channel_copies",return_value={}),patch.object(p,"critics_approve",return_value=[{"veto":False},{"veto":False}]),patch.object(p,"illustrate",return_value=([],[])),patch.object(p,"submit") as submit:
   with patch.dict(p.os.environ,{"ACOLAD_AUTOPUBLISH_APPROVAL":"NO"}):
    result=p.run("auto")
   self.assertIn("BLOCKED",result["status"])
   submit.assert_not_called()
 def test_critic_rejection_prevents_image_billing(self):
  with patch.object(p,"tehran_now",return_value=datetime(2026,11,5,10,tzinfo=ZoneInfo("Asia/Tehran"))),patch.object(p,"token",return_value="x"),patch.object(p,"provider_accounts"),patch.object(p,"generate_editorial",return_value=({"slides":[]},[])),patch.object(p,"make_channel_copies",return_value={}),patch.object(p,"critics_approve",return_value=[{"veto":True,"score":65},{"veto":False,"score":91}]),patch.object(p,"illustrate") as art:
   r=p.run("preview")
   self.assertTrue(r["status"].startswith("SKIPPED_CRITIC"))
   art.assert_not_called()
 def test_footer_exact(self):
  self.assertTrue(p.FOOTER.endswith("ارتباط و مشاوره: [@acolad_agency](https://t.me/acolad_agency)"))
if __name__=="__main__":unittest.main()
