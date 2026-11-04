import os
import tempfile
import unittest
from unittest.mock import patch
import acolad_crosschannel_preflight as p
class Reply:
    status_code=200
    def json(self):return [{"id":11,"type":"InstagramOfficial","name":"acolad.agency","login_required":0},{"id":12,"type":"telegram","identifier":"other"}]
class Session:
    def __init__(self):self.calls=[]
    def get(self,url,**kwargs):self.calls.append(url);return Reply()
class Tests(unittest.TestCase):
    def test_no_key_no_call(self):
        s=Session()
        with patch.dict(os.environ,{"NOVINHUB_API_TOKEN":"","NOVINHUB_TOKEN":"","NOVINHUB_ACCESS_TOKEN":""}):
            r=p.novinhub_status(s)
        self.assertEqual(r["status"],"SECRET_NOT_SET");self.assertFalse(s.calls)
    def test_match_only_target(self):
        s=Session()
        with patch.dict(os.environ,{"NOVINHUB_API_TOKEN":"mock","NOVINHUB_TOKEN":"","NOVINHUB_ACCESS_TOKEN":""}):
            r=p.novinhub_status(s)
        self.assertEqual(r["matched_accounts"],1);self.assertEqual(r["matches"][0]["id"],11)
        self.assertEqual(len(s.calls),1)
    def test_multiple_tokens_fail_closed(self):
        s=Session()
        with patch.dict(os.environ,{"NOVINHUB_API_TOKEN":"mock","NOVINHUB_TOKEN":"mock2","NOVINHUB_ACCESS_TOKEN":""}):
            r=p.novinhub_status(s)
        self.assertEqual(r["status"],"MULTIPLE_TOKEN_VARIABLES_SET_ABORT")
        self.assertFalse(s.calls)
if __name__=="__main__":unittest.main()
