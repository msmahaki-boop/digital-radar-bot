#!/usr/bin/env python3
"""NovinHub read-only draft/queue status; no media or social writes."""
import json,os,requests
from acolad_novinhub_bridge import token,headers,API,as_items
KEY=token()
session=requests.Session()
result={"mode":"READ_ONLY","targets":{"instagram":3692949,"telegram":3692937,"bale":3692942},
        "bale_account_id":233497,"social_writes":0}
for path in ("/post/draft","/post","/account"):
    try:
        r=session.get(API+path,headers=headers(KEY),timeout=30)
        row={"status_http":r.status_code}
        if r.status_code==200:
            obj=r.json()
            rows=as_items(obj)
            if isinstance(obj,list):rows=obj
            row["count"]=len(rows) if isinstance(rows,list) else None
            if isinstance(rows,list):
                if path=="/account":
                    row["target_accounts"]=[{"id":x.get("id"),"type":x.get("type"),
                                             "login_required":bool(x.get("login_required"))}
                                            for x in rows if str(x.get("id")) in ("233497","233472","230527")]
                else:
                    wanted=[x for x in rows if str(x.get("id")) in ("3692949","3692937","3692942")]
                    row["target_drafts"]=[{"id":x.get("id"),"type":x.get("type"),
                        "caption_length":len(str(x.get("caption") or "")),
                        "caption_sample":str(x.get("caption") or "")[:120],
                        "schedule_date":x.get("schedule_date"),
                        "is_scheduled":x.get("is_scheduled"),
                        "field_names":sorted(x.keys())[:22]} for x in wanted]
        result[path]=row
    except Exception as e:
        result[path]={"error":type(e).__name__}
print("ACOLAD_NOVINHUB_REAL_DRAFT_STATE "+json.dumps(result,ensure_ascii=False))
