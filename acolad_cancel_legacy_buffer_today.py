#!/usr/bin/env python3
"""Cancel ONLY the previously identified 2026-11-04 Buffer Instagram story.
Idempotent, fail closed, verifies status. No other posts touched.
"""
import json,os,sys
from datetime import datetime,timezone
from daily_story_pipeline import buffer_graphql,buffer_identity,recent_buffer_posts,DAILY_MARKER
TARGET_ID="6aead890e478396c274412ec"
TARGET_DATE="2026-11-04"
def out(**kw): print("ACOLAD_BUFFER_CANCEL "+json.dumps(kw,ensure_ascii=False),flush=True)
def main():
    org,channel=buffer_identity()
    rows=recent_buffer_posts(org,channel)
    matches=[p for p in rows if str(p.get("id"))==TARGET_ID]
    if len(matches)!=1:out(status="BLOCKED_POST_NOT_FOUND_OR_AMBIGUOUS",count=len(matches));return 2
    p=matches[0];status=str(p.get("status") or "").lower()
    due=p.get("dueAt")
    if status in ("sent","sending"):
        out(status="TOO_LATE_ALREADY_"+status,post_id=TARGET_ID);return 2
    if status in ("draft","error"):
        out(status="ALREADY_NOT_SCHEDULED",post_id=TARGET_ID);return 0
    if status!="scheduled" or not due or DAILY_MARKER+TARGET_DATE not in str(p.get("text") or ""):
        out(status="BLOCKED_UNEXPECTED_POST_STATE",post_id=TARGET_ID,post_status=status);return 2
    expected=datetime.fromisoformat("2026-11-04T14:30:00+00:00")
    actual=datetime.fromisoformat(str(due).replace("Z","+00:00"))
    if abs((actual-expected).total_seconds())>60:
        out(status="BLOCKED_DUE_DATE_CHANGED",post_id=TARGET_ID);return 2
    if datetime.now(timezone.utc)>=actual:
        out(status="BLOCKED_TOO_LATE_TO_CANCEL",post_id=TARGET_ID);return 2
    meta=buffer_graphql('query { __type(name:"DeletePostInput") { inputFields { name type { name kind ofType { name kind } } } } }')
    fields=((meta.get("__type") or {}).get("inputFields") or [])
    required=[f["name"] for f in fields if f.get("type",{}).get("kind")=="NON_NULL"]
    names=[f["name"] for f in fields]
    # Accept only an unambiguous one-ID API contract, no other required fields.
    if required not in (["id"],["postId"]) or len(required)!=1:
        out(status="BLOCKED_DELETE_SCHEMA_UNEXPECTED",required_fields=required,field_names=names);return 2
    field=required[0]
    result=buffer_graphql('mutation { deletePost(input: {'+field+': "'+TARGET_ID+'"}) { __typename } }')
    typename=(result.get("deletePost") or {}).get("__typename")
    if not typename or "Error" in typename:
        out(status="DELETE_NOT_CONFIRMED",typename=typename);return 2
    after=recent_buffer_posts(org,channel)
    again=[q for q in after if str(q.get("id"))==TARGET_ID]
    if any(str(q.get("status")).lower() in ("scheduled","sending") for q in again):
        out(status="DELETE_UNVERIFIED_STILL_SCHEDULED",typename=typename);return 2
    out(status="CANCELED_VERIFIED",post_id=TARGET_ID,mutation_result=typename,post_still_listed=bool(again),published=0)
    return 0
if __name__=="__main__":sys.exit(main())
