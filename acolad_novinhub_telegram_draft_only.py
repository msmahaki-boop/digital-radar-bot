#!/usr/bin/env python3
"""Single Telegram draft validation only. Never publish. Avoid Instagram duplicates."""
import json,os,re,requests
from datetime import datetime,timedelta,timezone
from acolad_novinhub_bridge import token,headers,API,as_items
mark="ACOLAD-TELEGRAM-ONLY-DRAFT-20261104"
k=token();session=requests.Session()
r=session.get(API+"/post/draft",headers=headers(k),timeout=30)
report={"mode":"ONLY_TELEGRAM_DRAFT","publish":0,"instagram_writes":0,"http_status":None}
if r.status_code!=200:
    report["status"]="DRAFT_LIST_UNAVAILABLE"
else:
    obj=r.json()
    drafts=as_items(obj)
    if drafts is None:
        report["status"]="DRAFT_LIST_UNEXPECTED"
    elif any(mark in str(x.get("caption") or "") for x in drafts if isinstance(x,dict)):
        report["status"]="ALREADY_EXISTS"
    else:
        payload={"caption":"آکولاد | بررسی پیش‌نویس تلگرام (بدون انتشار) "+mark,
                 "type":"text","account_ids":[233472],"media_ids":[],
                 "is_draft":1,"is_scheduled":0,
                 "schedule_date":int((datetime.now(timezone.utc)+timedelta(days=1)).timestamp())}
        res=session.post(API+"/post",headers={**headers(k),"Content-Type":"application/json"},
            json=payload,timeout=50)
        report["http_status"]=res.status_code
        try:
            obj=res.json()
            if res.status_code in (200,201):
                post=obj.get("data",obj) if isinstance(obj,dict) else {}
                report["status"]="DRAFT_CREATED" if isinstance(post,dict) and post.get("id") else "UNVERIFIED_SUCCESS"
                if isinstance(post,dict):report["receipt_id"]=post.get("id")
            else:
                error=obj.get("error",{}) if isinstance(obj,dict) else {}
                msg=error.get("message","") if isinstance(error,dict) else ""
                msg=re.sub(r"(?i)(?:bearer|sk-|token|key)[\s:=]*[A-Za-z0-9_-]{6,}","[REDACTED]",str(msg))
                msg=re.sub(r"https?://\S+","[URL]",msg)
                report["provider_validation_message"]=msg[:220]
                report["status"]="VALIDATION_REJECTED"
        except ValueError:
            report["status"]="NON_JSON_PROVIDER_ERROR"
print("NOVINHUB_TELEGRAM_DRAFT_ONLY "+json.dumps(report,ensure_ascii=False))
