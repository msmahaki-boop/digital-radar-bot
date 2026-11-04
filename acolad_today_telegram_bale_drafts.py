#!/usr/bin/env python3
"""Create TODAY's sourced narrative as true NovinHub Telegram/Bale DRAFTS only.
Never queue, never publish. Read back every receipt. Idempotent by unique story marker.
"""
from __future__ import annotations
import json,os,sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from acolad_novinhub_bridge import token,headers,API,as_items,create_post
from acolad_narrative_today_art_and_preview import check_story
import requests

TZ=ZoneInfo("Asia/Tehran")
MARKER="ACOLAD-NARRATIVE-20261104-FLASHPROVE"
REPORT=Path("acolad_today_omnichannel_drafts")
NETWORKS=("telegram","bale")
def narrative_text(story):
    frames=story["slides"]
    clean=lambda s:str(s).replace("**","").strip()
    body="\n\n".join(clean(s["text"]) for s in frames)
    evidence=story["sources"]
    links=[e["url"] for e in evidence if str(e.get("url","")).startswith("https://")]
    if not links:raise ValueError("Citable primary article URL missing")
    text=(clean(story.get("topic",""))+"\n\n"+body+"\n\n"
          "منبع خبر: "+links[0]+"\n"
          "توضیح: نمونه پژوهشی FlashProve هنوز یک ویژگی عمومیِ آمادهٔ فروشگاه‌ها نیست. "
          "مثال فروشگاه فرضی است و نتیجهٔ رفتار مشتری ادعا نشده.\n\n"
          "آکولاد | شریک رشد و تجربه دیجیتال\n"+MARKER)
    if not 400<=len(text)<=3500:raise ValueError("Invalid narrative message length")
    return text

def get_drafts(key):
    r=requests.get(API+"/post/draft",headers=headers(key),timeout=30)
    if r.status_code!=200:raise RuntimeError("Cannot read live NovinHub draft list")
    rows=as_items(r.json())
    if rows is None:raise RuntimeError("Cannot parse existing drafts")
    return rows

def run():
    REPORT.mkdir(parents=True,exist_ok=True)
    out={"mode":"DRAFT_ONLY","date_tehran":datetime.now(TZ).date().isoformat(),
         "published":0,"queued":0,"scheduled":0,"records":[]}
    try:
        story,status=check_story()
        k=token()
        text=narrative_text(story)
        (REPORT/"telegram_bale_preview.txt").write_text(text,encoding="utf-8")
        initial=get_drafts(k)
        if any(MARKER in str(row.get("caption","")) for row in initial if isinstance(row,dict)):
            out["status"]="EXISTING_DRAFT_DO_NOT_DUPLICATE"
            return out
        for network in NETWORKS:
            rec=create_post(k,network,text,[],draft=True)
            out["records"].append({"network":network,"post_id":rec["post_id"],
                    "provider_mode":rec["mode"],"message_characters":len(text)})
        after=get_drafts(k)
        receipt_ids={str(x.get("id")) for x in after if isinstance(x,dict) and MARKER in str(x.get("caption",""))}
        if not all(str(x["post_id"]) in receipt_ids for x in out["records"]):
            out["status"]="DRAFT_CREATED_BUT_READBACK_UNVERIFIED"
        else:
            out["status"]="TWO_NARRATIVE_DRAFTS_VERIFIED"
    except Exception as exc:
        out["status"]="ERROR_"+type(exc).__name__
        out["error_category"]=str(exc)[:145]
    finally:
        (REPORT/"status.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("ACOLAD_NOVINHUB_TELEGRAM_BALE_DRAFT "+json.dumps(out,ensure_ascii=False),flush=True)
    return out

if __name__=="__main__":sys.exit(0 if run().get("status") in ("TWO_NARRATIVE_DRAFTS_VERIFIED","EXISTING_DRAFT_DO_NOT_DUPLICATE") else 2)
