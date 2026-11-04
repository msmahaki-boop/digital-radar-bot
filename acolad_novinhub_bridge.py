#!/usr/bin/env python3
"""NovinHub v2 Acolad adapter. Read-only default. Mutations are explicit and receipt-checked.
This does not edit active Telegram/Buffer workflows or published media.
"""
from __future__ import annotations
import argparse,json,os,re,sys
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import requests
from PIL import Image

API="https://api.novinhub.com/token/v2"
OUT=Path("acolad_novinhub_e2e")
TEHRAN=ZoneInfo("Asia/Tehran")
NETWORKS={"instagram":230527,"telegram":233472}
CAPTION_MARKER="ACOLAD-NOVINHUB-VERIFY-20261104"
def token():
    items=[os.getenv(k,"").strip() for k in ("NOVINHUB_API_TOKEN","NOVINHUB_TOKEN","NOVINHUB_ACCESS_TOKEN")]
    found=[v for v in items if v]
    if len(found)!=1:raise RuntimeError("Expected exactly one NovinHub token secret")
    return found[0]

def headers(key):
    return {"Authorization":"Bearer "+key,"Accept":"application/json"}

def get_json(path,key,session=requests,params=None):
    if path not in ("/account","/post","/post/draft"):raise ValueError("unapproved GET path")
    r=session.get(API+path,headers=headers(key),params=params,timeout=40)
    if r.status_code!=200:raise RuntimeError("NovinHub GET "+path+" HTTP "+str(r.status_code))
    obj=r.json()
    if isinstance(obj,dict) and obj.get("error"):raise RuntimeError("NovinHub returned API error")
    return obj

def as_items(obj):
    if isinstance(obj,list):return obj
    if not isinstance(obj,dict):return None
    a=obj.get("data")
    if isinstance(a,list):return a
    if isinstance(a,dict):
        for k in ("data","items"):
            if isinstance(a.get(k),list):return a[k]
    return None

def accounts(key,session=requests):
    rows=as_items(get_json("/account",key,session))
    if rows is None:raise RuntimeError("Unexpected NovinHub account response")
    matched={}
    for network,expected in NETWORKS.items():
        # Exact ID and type rather than user-supplied display name.
        candidates=[a for a in rows if isinstance(a,dict) and str(a.get("id"))==str(expected)]
        if len(candidates)!=1:raise RuntimeError("Missing or ambiguous "+network+" account")
        a=candidates[0]
        kind=str(a.get("type","")).lower()
        if network not in kind:raise RuntimeError("Account type mismatch for "+network)
        if bool(a.get("login_required")):raise RuntimeError("Re-login required for "+network)
        matched[network]=expected
    return matched

def novinhub_post_list(key,session=requests):
    result={}
    for k,aid in NETWORKS.items():
        obj=get_json("/post",key,session,{"account_ids[]":str(aid),"order":"id"})
        rows=as_items(obj)
        if rows is None:raise RuntimeError("Unrecognized NovinHub /post response; no writes allowed")
        result[k]={"checked":True,"count_page":len(rows),
                   "recent":[{"id":p.get("id"),"status":p.get("status"),
                              "schedule_date":p.get("schedule_date"),
                              "type":p.get("type")}
                             for p in rows[:12] if isinstance(p,dict)]}
    return result

def account_report(key,session=requests):
    acc=accounts(key,session)
    recent=novinhub_post_list(key,session)
    return {"status":"CONNECTED_READ_ONLY","account_ids":acc,"recent_posts":recent}

def check_story_files(folder):
    folder=Path(folder)
    manifest=folder/"manifest.json"
    if manifest.is_file():
        meta=json.loads(manifest.read_text(encoding="utf-8"))
        if meta.get("publication_status")!="PREVIEW ONLY - NOTHING PUBLISHED":
            raise RuntimeError("Not a verified preview manifest")
        articles=meta.get("articles") or []
        if len(articles)!=4:raise RuntimeError("Expected four editorial news slides")
        paths=[folder/"01_intro.png"]
        for article in articles:
            name=Path(str(article.get("file",""))).name
            if not re.fullmatch(r"0[2-5]_[a-z_]+_(?:photo|text_only)[.]png",name):
                raise RuntimeError("Unexpected story filename")
            paths.append(folder/name)
    else:
        paths=sorted(folder.glob("story_*.png"))
    if len(paths) not in (5,8):raise RuntimeError("Expect complete validated 5 or 8 frame story")
    for p in paths:
        if p.stat().st_size>18_000_000:raise RuntimeError("Media too large")
        with Image.open(p) as im:
            if im.format!="PNG" or im.size!=(1080,1920):raise RuntimeError("Invalid story PNG")
            im.verify()
    return paths

def upload_file(key,path,session=requests):
    with path.open("rb") as f:
        r=session.post(API+"/file",headers=headers(key),
                       files={"file":(path.name,f,"image/png")},timeout=100)
    if r.status_code not in (200,201):raise RuntimeError("NovinHub file upload HTTP "+str(r.status_code))
    obj=r.json()
    data=obj.get("data",obj) if isinstance(obj,dict) else {}
    raw_id=data.get("id") if isinstance(data,dict) else None
    if not isinstance(raw_id,(int,str)) or not str(raw_id).isdigit():
        raise RuntimeError("File upload returned no decimal ID")
    return int(raw_id)

def create_post(key,network,caption,media_ids,session=requests,draft=True,schedule_epoch=None):
    if network not in NETWORKS:raise ValueError("Unknown network")
    if not isinstance(caption,str) or not caption.strip():raise ValueError("Empty caption")
    if network=="instagram" and not media_ids:raise ValueError("Story requires media")
    if network=="telegram" and media_ids:raise ValueError("Telegram test should be text only")
    if not draft and not isinstance(schedule_epoch,int):raise ValueError("Live send requires future date")
    payload={"type":"story" if network=="instagram" else "text",
             "account_ids":[NETWORKS[network]],"caption":caption,
             "media_ids":media_ids,"is_draft":1 if draft else 0,
             "is_scheduled":0 if draft else 1}
    if schedule_epoch is not None:payload["schedule_date"]=schedule_epoch
    r=session.post(API+"/post",json=payload,headers={**headers(key),"Content-Type":"application/json"},
                   timeout=70)
    if r.status_code not in (200,201):raise RuntimeError("NovinHub post HTTP "+str(r.status_code))
    obj=r.json()
    data=obj.get("data",obj) if isinstance(obj,dict) else {}
    if not isinstance(data,dict):raise RuntimeError("NovinHub returned no post object")
    post_id=data.get("id")
    if not post_id:raise RuntimeError("NovinHub returned no post ID; check manually for ambiguous status")
    return {"post_id":post_id,"mode":"DRAFT" if draft else "SCHEDULED",
            "account_id":NETWORKS[network],"type":payload["type"]}

def run(mode="read",story_dir="stories_output",session=requests):
    OUT.mkdir(parents=True,exist_ok=True)
    result={"mode":mode,"date_tehran":datetime.now(TEHRAN).date().isoformat(),
            "published":0,"drafts_created":0,"posts_created":0,
            "note":"Draft != queued != published. Account verification only unless mode=draft."}
    try:
        key=token()
        result["preflight"]=account_report(key,session)
        if mode=="read":
            result["status"]="READ_ONLY_OK"
        elif mode=="draft":
            if os.getenv("ACOLAD_NOVINHUB_DRAFT_APPROVAL")!="APPROVED_CREATE_TEST_DRAFTS":
                raise RuntimeError("Draft write not approved")
            existing_obj=get_json("/post/draft",key,session)
            existing=as_items(existing_obj)
            if existing is None:raise RuntimeError("Cannot verify existing drafts; refuse to create")
            if any(CAPTION_MARKER in str(row.get("caption","")) or CAPTION_MARKER in str(row.get("text",""))
                   for row in existing if isinstance(row,dict)):
                raise RuntimeError("Identical NovinHub test draft already exists")
            paths=check_story_files(story_dir)
            # Only create drafts; never post public stories or Telegram messages.
            media_ids=[]
            for path in paths:media_ids.append(upload_file(key,path,session))
            story=create_post(key,"instagram","آکولاد | پیش‌نویس آزمایشی استوری | " + CAPTION_MARKER,media_ids,session,draft=True)
            result["instagram"]=story
            result["drafts_created"]+=1
            telegram=create_post(key,"telegram","آکولاد | پیش‌نویس آزمایشی اتصال تلگرام (بدون انتشار) | " + CAPTION_MARKER,[],session,draft=True)
            result["telegram"]=telegram
            result["drafts_created"]+=1
            result["status"]="NOVINHUB_TWO_DRAFTS_CREATED"
        else:raise RuntimeError("Unapproved mode")
    except Exception as e:
        result["status"]="BLOCKED_"+type(e).__name__
        result["error_category"]=str(e)[:160]
    (OUT/"status.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("NOVINHUB_TWO_CHANNEL_TEST "+json.dumps(result,ensure_ascii=False),flush=True)
    return result

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=("read","draft"),default="read")
    ap.add_argument("--story-dir",default="stories_output")
    args=ap.parse_args()
    result=run(args.mode,args.story_dir)
    sys.exit(0 if result["status"] in ("READ_ONLY_OK","NOVINHUB_TWO_DRAFTS_CREATED") else 2)
