#!/usr/bin/env python3
"""Ten-frame editorial Acolad narrative Instagram Story DRAFT in NovinHub.
Consumes verified completed artifact; never schedules or publishes.
"""
from __future__ import annotations
import json,os,sys
from pathlib import Path
import requests
from PIL import Image
from acolad_novinhub_bridge import API,token,headers,as_items,upload_file,create_post
OUT=Path("acolad_today_instagram_narrative_draft")
SOURCE=Path("acolad_today_narrative_draft")
MARK="ACOLAD-NARRATIVE-IG-20261104-FLASHPROVE"
ACCOUNT=230527
def run():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"mode":"INSTAGRAM_DRAFT_ONLY","posts_queued":0,"published":0,"scheduled":0}
    try:
        qa=json.loads((SOURCE/"narrative_qa.json").read_text(encoding="utf-8"))
        if qa.get("status")!="PREVIEW_HUMAN_REVIEW_REQUIRED" or qa.get("date")!="2026-11-04":
            raise ValueError("Story QA or date mismatch")
        files=sorted((SOURCE/"frames").glob("story_*.png"))
        if len(files)!=10 or qa.get("frames")!=10:raise ValueError("Incomplete ten-frame story")
        for path in files:
            with Image.open(path) as im:
                if im.size!=(1080,1920) or im.format!="PNG":
                    raise ValueError("Unexpected frame image")
                im.verify()
        k=token()
        r=requests.get(API+"/post/draft",headers=headers(k),timeout=30)
        if r.status_code!=200:raise RuntimeError("Cannot read existing drafts")
        posts=as_items(r.json())
        if posts is None:raise RuntimeError("NovinHub draft list shape unknown")
        if any(MARK in str(row.get("caption") or "") for row in posts if isinstance(row,dict)):
            report["status"]="EXISTING_DRAFT_NOT_DUPLICATED"
            return report
        ids=[upload_file(k,p) for p in files]
        if len(ids)!=10:raise ValueError("Incomplete media upload")
        caption=("آکولاد | روایت روز: چطور بفهمیم یک پاسخ هوش مصنوعی از چه مدلی آمده؟ "
                 "پیش‌نویس برای تأیید؛ منابع: Anthropic و دیجیاتو. "+MARK)
        receipt=create_post(k,"instagram",caption,ids,draft=True)
        report.update({"status":"INSTAGRAM_NARRATIVE_DRAFT_CREATED",
          "post_id":receipt["post_id"],"media_count":len(ids),"caption_length":len(caption)})
        after=requests.get(API+"/post/draft",headers=headers(k),timeout=30)
        if after.status_code==200:
            items=as_items(after.json()) or []
            found=[x for x in items if str(x.get("id"))==str(receipt["post_id"])]
            if found:
                report["status"]="INSTAGRAM_NARRATIVE_DRAFT_VERIFIED"
                report["draft_caption_length"]=len(str(found[0].get("caption") or ""))
    except Exception as e:
        report["status"]="BLOCKED_"+type(e).__name__
        report["error_category"]=str(e)[:180]
    finally:
        (OUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("ACOLAD_NOVINHUB_INSTAGRAM_NARRATIVE "+json.dumps(report,ensure_ascii=False),flush=True)
    return report
if __name__=="__main__":
    x=run()
    sys.exit(0 if x["status"] in ("INSTAGRAM_NARRATIVE_DRAFT_CREATED",
             "INSTAGRAM_NARRATIVE_DRAFT_VERIFIED","EXISTING_DRAFT_NOT_DUPLICATED") else 2)
