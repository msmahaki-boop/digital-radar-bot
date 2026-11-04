#!/usr/bin/env python3
"""Diagnose NovinHub POST /post with one story image + Telegram text test DRAFTS only."""
import json,os,requests
from acolad_novinhub_bridge import API,token,headers,as_items,CAPTION_MARKER
def keys_only(obj):
    if isinstance(obj,dict):
        err=obj.get("error")
        if isinstance(err,dict):
            safe={}
            for key,val in err.items():
                if isinstance(val,dict): safe[key]=sorted(val.keys())[:10]
                elif isinstance(val,list):safe[key]=[type(x).__name__ for x in val[:3]]
                else:safe[key]=type(val).__name__
            return {"top_keys":sorted(obj.keys())[:15],"error_shape":safe}
        return {"top_keys":sorted(obj.keys())[:15],
                "error_type":type(err).__name__,
                "data_type":type(obj.get("data")).__name__}
    return {"body_type":type(obj).__name__}
k=token()
s=requests.Session()
def get(path,params=None):
    r=s.get(API+path,headers=headers(k),params=params,timeout=30)
    if r.status_code!=200:raise RuntimeError("GET "+path+" HTTP "+str(r.status_code))
    return r.json()
report={"mode":"TWO_SINGLE_DRAFTS_ONLY","published":0,"queued":0,"drafts":0}
try:
    old=as_items(get("/post/draft"))
    if old is None:raise RuntimeError("Cannot read draft list")
    if any(CAPTION_MARKER in str(row) for row in old):raise RuntimeError("Test marker already exists")
    files=as_items(get("/file",{"search":"01_intro"}))
    if files is None:raise RuntimeError("Cannot read file list")
    files=[row for row in files if isinstance(row,dict) and row.get("title")=="01_intro.png"
           and str(row.get("id","")).isdigit()]
    if not files:raise RuntimeError("Prior uploaded cover image not found")
    files.sort(key=lambda x:int(x["id"]),reverse=True)
    fid=int(files[0]["id"])
    for net,payload in [
        ("instagram",{"type":"story","caption":"آکولاد | استوری آزمایشی (پیش‌نویس) "+CAPTION_MARKER,
                      "account_ids":[230527],"media_ids":[fid],"is_draft":1,"is_scheduled":0}),
        ("telegram",{"type":"text","caption":"آکولاد | تست اتصال تلگرام (فقط پیش‌نویس) "+CAPTION_MARKER,
                     "account_ids":[233472],"media_ids":[],"is_draft":1,"is_scheduled":0})]:
        r=s.post(API+"/post",headers={**headers(k),"Content-Type":"application/json"},
                 json=payload,timeout=60)
        row={"http_status":r.status_code,"network":net}
        try:
            j=r.json()
            row.update(keys_only(j))
            if r.status_code in (200,201):
                data=j.get("data",j) if isinstance(j,dict) else {}
                row["receipt_id_exists"]=bool(data.get("id")) if isinstance(data,dict) else False
                row["receipt_id_type"]=type(data.get("id")).__name__ if isinstance(data,dict) else None
                if row["receipt_id_exists"]:report["drafts"]+=1
        except ValueError:row["response"]="not json"
        report[net]=row
    report["status"]="PROBE_DONE"
except Exception as e:
    report["status"]="BLOCKED_"+type(e).__name__
    report["error_classification"]=str(e)[:120]
print("NOVINHUB_SAFE_POST_SCHEMA "+json.dumps(report,ensure_ascii=False))
