#!/usr/bin/env python3
"""NovinHub Bale schema probe; exactly one 0-publication draft test."""
import json,re,requests
from datetime import datetime,timedelta,timezone
from acolad_novinhub_bridge import API,token,headers,as_items
key=token();sess=requests.Session()
marker="ACOLAD-BALE-SCHEMA-DRAFT-20261104"
rows=sess.get(API+"/post/draft",headers=headers(key),timeout=25)
if rows.status_code!=200:raise SystemExit("Draft preflight HTTP error")
items=as_items(rows.json())
report={"mode":"BALE_DRAFT_ONLY","published":0,"queued":0}
if items is None:report["status"]="DRAFT_LIST_UNREADABLE"
elif any(marker in str(r.get("caption") or "") for r in items if isinstance(r,dict)):
    report["status"]="DRAFT_ALREADY_EXISTS"
else:
    payload={"type":"text","caption":"آکولاد | تست پیش‌نویس بله "+marker,
      "account_ids":[233497],"media_ids":[],"is_draft":1,"is_scheduled":0,
      "schedule_date":int((datetime.now(timezone.utc)+timedelta(days=1)).timestamp()),
      "bale_has_signature":0}
    resp=sess.post(API+"/post",headers={**headers(key),"Content-Type":"application/json"},
                   json=payload,timeout=60)
    report["http_status"]=resp.status_code
    try:
        body=resp.json()
        if resp.status_code in (200,201):
            obj=body.get("data",body) if isinstance(body,dict) else {}
            report["id"]=obj.get("id") if isinstance(obj,dict) else None
            report["status"]="DRAFT_CREATED" if report["id"] else "SUCCESS_NO_ID"
        else:
            err=(body.get("error") or {}) if isinstance(body,dict) else {}
            msg=str(err.get("message") or "") if isinstance(err,dict) else ""
            msg=re.sub(r"(?i)(?:bearer|sk-|key|token)[\\s:=]*[A-Za-z0-9_-]{6,}","[REDACTED]",msg)
            report["status"]="VALIDATION_FAILED"
            report["error_message"]=msg[:270]
    except ValueError:report["status"]="NON_JSON_ERROR"
print("ACOLAD_BALE_DRAFT_DIAGNOSTIC "+json.dumps(report,ensure_ascii=False))
