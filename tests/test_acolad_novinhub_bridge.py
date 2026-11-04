import unittest
from unittest.mock import patch
import acolad_novinhub_bridge as n
class Resp:
    status_code=200
    def __init__(self,data):self.data=data
    def json(self):return self.data
class Session:
    def __init__(self):self.calls=[]
    def get(self,url,**kw):
        self.calls.append(("GET",url))
        if url.endswith("/account"):
            return Resp([{"id":230527,"type":"Instagram","login_required":False},
                         {"id":233472,"type":"Telegram","login_required":False}])
        if url.endswith("/post"):return Resp({"data":[{"id":123,"status":"scheduled"}]})
        raise AssertionError(url)
    def post(self,url,**kw):
        self.calls.append(("POST",url))
        return Resp({"data":{"id":456}})
class Tests(unittest.TestCase):
    def test_preflight_no_posts(self):
        s=Session();r=n.account_report("test",s)
        self.assertEqual(r["status"],"CONNECTED_READ_ONLY")
        self.assertEqual(len([x for x in s.calls if x[0]=="POST"]),0)
    def test_draft_mutation_is_explicit(self):
        s=Session()
        with self.assertRaises(ValueError):n.create_post("key","instagram","caption",[],s)
        self.assertFalse(any(x[0]=="POST" for x in s.calls))
    def test_story_payload_draft(self):
        s=Session();r=n.create_post("key","instagram","caption",[111],s,draft=True)
        self.assertEqual(r["mode"],"DRAFT")
        self.assertEqual(r["post_id"],456)
if __name__=="__main__":unittest.main()
