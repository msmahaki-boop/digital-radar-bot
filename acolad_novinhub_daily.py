#!/usr/bin/env python3
"""Acolad daily Instagram Story via NovinHub only when no Buffer/NovinHub duplicate exists.
Telegram remains with existing proven GitHub Bot workflow until separately migrated.
"""
from __future__ import annotations
import argparse,hashlib,json,os,subprocess,sys
from datetime import datetime,time,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from acolad_novinhub_bridge import token,account_report,get_json,as_items,upload_file,create_post,check_story_files
from daily_story_pipeline import buffer_identity,recent_buffer_posts,DAILY_MARKER

TZ=ZoneInfo("Asia/Tehran")
OUTPUT=Path("acolad_novinhub_daily")
PREFIX="ACOLAD-NOVINHUB-DAILY-"
SAFE_ACCOUNT=230527

def local_day(now=None):
    return (now or datetime.now(TZ)).astimezone(TZ).date()

def target_utc(now=None):
    n=(now or datetime.now(TZ)).astimezone(TZ)
    local=datetime.combine(n.date(),time(18,0),tzinfo=TZ)
    if local-n<timedelta(minutes=35):
        return None
    return local.astimezone(timezone.utc)

def prevent_buffer_dup(date_str):
    if not os.getenv("BUFFER_API_KEY"):
        raise RuntimeError("Cannot read Buffer history; blocking migration publish")
    org,channel=buffer_identity()
    entries=recent_buffer_posts(org,channel)
    for p in entries:
        text=str(p.get("text") or "")
        state=str(p.get("status") or "").lower()
        if state not in ("error","draft") and DAILY_MARKER+date_str in text:
            return {"status":"BUFFER_ALREADY_HAS_DATE","post_id":p.get("id"),
                    "buffer_post_status":state}
    return {"status":"BUFFER_DATE_CLEAR"}

def prevent_novin_dup(key,date_str):
    # Provider's documented GET /post. Do not trust an empty page if pagination is unknown.
    obj=get_json("/post",key,requests,{"account_ids[]":str(SAFE_ACCOUNT),
         "publish_from":date_str,"publish_to":date_str,"order":"id"})
    rows=as_items(obj)
    if rows is None:raise RuntimeError("Cannot parse NovinHub history")
    data=obj.get("data") if isinstance(obj,dict) else None
    paging=obj.get("paging") if isinstance(obj,dict) else None
    if isinstance(paging,dict) and (paging.get("next") or int(paging.get("totalPage") or 1)>1):
        raise RuntimeError("NovinHub history has multiple pages: fail closed")
    for p in rows:
        if not isinstance(p,dict):continue
        caption=str(p.get("caption") or p.get("text") or "")
        if PREFIX+date_str in caption:
            return {"status":"NOVINHUB_ALREADY_HAS_DATE","post_id":p.get("id")}
    return {"status":"NOVINHUB_DATE_CLEAR","records_checked":len(rows)}

def verify_editorial_manifest(folder):
    manifest=json.loads((Path(folder)/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("publication_status")!="PREVIEW ONLY - NOTHING PUBLISHED":
        raise RuntimeError("No approved preview manifest")
    articles=manifest.get("articles") or []
    if len(articles)!=4:raise RuntimeError("Need four distinct verified articles")
    links=[str(a.get("article_url_for_editor_only") or "") for a in articles]
    if len(set(links))!=4 or any(not x.startswith("https://") for x in links):
        raise RuntimeError("Source URLs missing or duplicated")
    frames=check_story_files(folder)
    return manifest,frames

def run(mode="preview",out=OUTPUT):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    now=datetime.now(TZ)
    day=now.date().isoformat()
    report={"mode":mode,"tehran_date":day,"network":"Instagram","provider":"NovinHub",
        "telegram_provider_unchanged":"Existing Telegram Bot","image_preference":"gpt-image-2",
        "status":"NOT_STARTED","drafts":0,"scheduled":0,"published":0}
    try:
        goal=target_utc(now)
        if not goal:
            report["status"]="SKIP_SCHEDULING_WINDOW_PASSED"
            return report
        report["target_due_utc"]=goal.isoformat()
        b=prevent_buffer_dup(day)
        report["buffer_guard"]=b
        if b["status"]!="BUFFER_DATE_CLEAR":
            report["status"]="SKIP_EXISTING_BUFFER_POST"
            return report
        key=token()
        report["novinhub_accounts"]=account_report(key)
        n=prevent_novin_dup(key,day)
        report["novinhub_guard"]=n
        if n["status"]!="NOVINHUB_DATE_CLEAR":
            report["status"]="SKIP_EXISTING_NOVINHUB_POST"
            return report
        if mode=="preview":
            report["status"]="SAFE_TO_PREVIEW"
            return report
        if mode!="auto" or os.getenv("ACOLAD_NOVINHUB_AUTO_APPROVAL")!="AUTO_INSTAGRAM_SCHEDULE_APPROVED":
            raise RuntimeError("Explicit auto scheduling gate required")
        # Generate after BOTH duplicate checks, so retries do not spend image credits.
        env=os.environ.copy()
        env["ACOLAD_IMAGE_LADDER_ENABLED"]="true"
        env["ACOLAD_IMAGE_API_PAID_ENABLED"]="true"
        subprocess.run([sys.executable,"story_test.py"],env=env,check=True,timeout=1000)
        manifest,images=verify_editorial_manifest("stories_output")
        # Recheck both providers immediately before first external upload.
        if prevent_buffer_dup(day)["status"]!="BUFFER_DATE_CLEAR":
            raise RuntimeError("Buffer duplicate appeared during generation")
        if prevent_novin_dup(key,day)["status"]!="NOVINHUB_DATE_CLEAR":
            raise RuntimeError("NovinHub duplicate appeared during generation")
        media=[upload_file(key,p) for p in images]
        hashes=[hashlib.sha256(x["article_url_for_editor_only"].encode("utf-8")).hexdigest()[:12]
                for x in manifest["articles"]]
        caption="آکولاد | چهار داستان خبری و کاربردی امروز\n"+PREFIX+day+"\nSOURCES:"+",".join(hashes)
        receipt=create_post(key,"instagram",caption,media,draft=False,
                 schedule_epoch=int(goal.timestamp()))
        report["post_id"]=receipt["post_id"]
        report["status"]="NOVINHUB_SCHEDULE_CREATED_NOT_PUBLISHED"
        report["scheduled"]=1
        return report
    except Exception as e:
        report["status"]="BLOCKED_"+type(e).__name__
        report["safe_error"]=str(e)[:170]
        return report
    finally:
        (out/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("ACOLAD_NOVINHUB_DAILY "+json.dumps(report,ensure_ascii=False),flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=("preview","auto"),default="preview")
    args=ap.parse_args()
    result=run(args.mode)
    return 0 if not result["status"].startswith("BLOCKED") else 2

if __name__=="__main__":
    raise SystemExit(main())
