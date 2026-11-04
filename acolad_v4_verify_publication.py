#!/usr/bin/env python3
"""NovinHub read-only real publishing check; never equates a green Action to sent."""
import json,os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from acolad_novinhub_bridge import API,headers,token,as_items

TZ=ZoneInfo("Asia/Tehran")
OUT=Path("acolad_v4_publish_check")
ACCOUNTS={"telegram":233472,"bale":233497,"instagram":230527}
ACCEPT={"published","sent","success","completed","complete"}
DATE=datetime.now(TZ).date()

def records():
    k=token();out={"date":DATE.isoformat(),"mode":"PROVIDER_READ_ONLY",
        "publication_verified":False,"networks":{}}
    for net,aid in ACCOUNTS.items():
        r=requests.get(API+"/post",headers=headers(k),
            params={"account_ids[]":str(aid),"order":"id",
                "publish_from":DATE.isoformat(),"publish_to":DATE.isoformat(),
                "with":"post(accountPost)"},timeout=40)
        if r.status_code!=200:
            out["networks"][net]={"verification":"API_UNAVAILABLE","http":r.status_code};continue
        obj=r.json();rows=as_items(obj)
        if rows is None:
            out["networks"][net]={"verification":"UNEXPECTED_API_FORMAT"};continue
        posts=[]
        for entry in rows:
            if not isinstance(entry,dict):continue
            details=entry.get("post") or entry.get("posts") or []
            if isinstance(details,dict):details=[details]
            for detail in details:
                if not isinstance(detail,dict):continue
                if str(detail.get("account_id"))!=str(aid):continue
                remote=detail.get("accountPost") or {}
                post_id=remote.get("post_id") if isinstance(remote,dict) else None
                state=str(detail.get("status") or "").lower()
                posts.append({"group_id":entry.get("id"),"status":state,
                              "external_post_id_present":bool(post_id),
                              "verification":"PUBLISHED_PROVIDER_AND_EXTERNAL_ID"
                                  if state in ACCEPT and post_id else "NOT_YET_PROVEN"})
        out["networks"][net]={"verification":"PUBLISHED_PROVIDER_AND_EXTERNAL_ID"
                              if any(p["verification"]=="PUBLISHED_PROVIDER_AND_EXTERNAL_ID" for p in posts)
                              else "NOT_PROVEN_FROM_PROVIDER","posts":posts[:10]}
    out["publication_verified"]=all(x["verification"]=="PUBLISHED_PROVIDER_AND_EXTERNAL_ID"
        for x in out["networks"].values())
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"status.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ACOLAD_V4_PUBLISHED_CHECK "+json.dumps(out,ensure_ascii=False),flush=True)
    return out

if __name__=="__main__":
    records()
