#!/usr/bin/env python3
"""Create Acolad's three channel-specific NovinHub review-only DRAFTS from a verified artifact.
No schedule or public publishing. Never put source links or metadata in audience copy.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
import requests
from PIL import Image
from acolad_editorial_trust_gate import check_public_copy
from acolad_novinhub_bridge import token,headers,API,as_items,accounts,upload_file,create_post

SOURCE=Path("acolad_expert_story_preview")
OUT=Path("acolad_expert_novinhub_draft_receipts")
NETWORKS=("telegram","bale","instagram")
NETWORK_IDS={"telegram":233472,"bale":233497,"instagram":230527}

def drafts(key):
    r=requests.get(API+"/post/draft",headers=headers(key),timeout=35)
    if r.status_code!=200:raise RuntimeError("Draft list HTTP "+str(r.status_code))
    obj=r.json(); rows=as_items(obj)
    if not isinstance(rows,list):raise RuntimeError("Unexpected draft list structure")
    pagination=obj.get("pagination") if isinstance(obj,dict) else None
    if isinstance(pagination,dict) and (pagination.get("next_page_url") or pagination.get("next")):
        raise RuntimeError("Draft list paginated; cannot guarantee idempotency")
    return rows

def validate():
    status=json.loads((SOURCE/"status.json").read_text(encoding="utf8"))
    copies=json.loads((SOURCE/"audience_copies.json").read_text(encoding="utf8"))
    if status.get("status")!="NINE_FRAME_VISUAL_PREVIEW_FOR_OWNER_REVIEW":
        raise ValueError("Preview status not approved for draft creation")
    if not status["editorial_gate"]["hard_pass"]:
        raise ValueError("Hard editorial gate did not pass")
    if status["editorial_gate"]["human_release_approved"]:
        raise ValueError("This workflow must remain manual-review only")
    if status.get("network_post_requests")!=0 or status.get("published")!=0:
        raise ValueError("Source preview must have zero social mutations")
    frames=sorted((SOURCE/"frames").glob("story_*.png"))
    if len(frames)!=9:raise ValueError("Expected nine frames")
    for f in frames:
        with Image.open(f) as im:
            if im.format!="PNG" or im.size!=(1080,1920):
                raise ValueError("Unsupported story image")
            im.verify()
    for key in ("telegram","bale","instagram_caption"):
        text=str(copies[key])
        state=check_public_copy(text)
        if not state["clean"]:raise ValueError("Public text leak: "+key)
        if "https://" in text or "ACOLAD-" in text:raise ValueError("Hidden citation or marker in audience text")
    if len(copies["bale"])>960:raise ValueError("Bale text length")
    return frames,copies

def bale_draft(key,message):
    payload={"type":"text","caption":message,"account_ids":[NETWORK_IDS["bale"]],
             "media_ids":[],"is_draft":1,"is_scheduled":0,"bale_has_signature":0,
             "schedule_date":int((datetime.now(timezone.utc)+timedelta(days=1)).timestamp())}
    r=requests.post(API+"/post",headers={**headers(key),"Content-Type":"application/json"},
                    json=payload,timeout=65)
    if r.status_code not in (200,201):
        # The provider's validation details are diagnostic. Never expose token,
        # network URLs, or the submitted full audience text in public CI logs.
        try:
            error=r.json().get("error") or {}
            raw=str(error.get("message") or "") if isinstance(error,dict) else ""
            import re
            safe=re.sub(r"(?i)(?:bearer|sk-|token|api[_ -]?key)[\\s:=]*[A-Za-z0-9_-]{6,}","[REDACTED]",raw)
            safe=re.sub(r"https?://\\S+","[URL]",safe)[:200]
        except (ValueError,TypeError,AttributeError):
            safe=""
        raise RuntimeError("Bale draft HTTP "+str(r.status_code)+" provider_validation="+safe)
    obj=r.json();data=obj.get("data",obj) if isinstance(obj,dict) else {}
    if not isinstance(data,dict) or not data.get("id"):
        raise RuntimeError("Bale draft receipt ID missing")
    return data["id"]

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"state":"NOVINHUB_REVIEW_DRAFTS_ONLY","scheduled":0,"published":0,
            "queued":0,"requests_for_actual_publication":0,
            "created":0,"networks":[]}
    try:
        frames,copies=validate()
        k=token()
        acc=accounts(k)
        if set(acc)!=set(NETWORK_IDS):raise RuntimeError("Unexpected NovinHub connected target accounts")
        planned=[("telegram",copies["telegram"]),("bale",copies["bale"]),
                 ("instagram",copies["instagram_caption"])]
        # The same text on the same target network means it's already a draft.
        for net,text in planned:
            existing=drafts(k)
            matches=[x for x in existing if isinstance(x,dict) and
                     str(x.get("caption") or "")==text]
            if matches:
                report["networks"].append({"network":net,"status":"EXISTING_DRAFT","id":matches[0].get("id"),
                                           "caption_chars":len(text)})
                continue
            if net=="telegram":
                receipt=create_post(k,net,text,[],draft=True)
                id_=receipt["post_id"]
            elif net=="bale":
                id_=bale_draft(k,text)
            else:
                ids=[upload_file(k,f) for f in frames]
                if len(ids)!=9:raise ValueError("Media upload incomplete")
                receipt=create_post(k,net,text,ids,draft=True)
                id_=receipt["post_id"]
            report["created"]+=1
            # Retained even if provider's read-back is temporarily eventually consistent.
            record={"network":net,"status":"DRAFT_CREATED_UNVERIFIED","id":id_,
                    "caption_chars":len(text),"uploaded_frames":9 if net=="instagram" else 0}
            report["networks"].append(record)
            (OUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
            after=drafts(k)
            found=[x for x in after if str(x.get("id"))==str(id_)]
            if found and str(found[0].get("caption") or "")==text:
                record["status"]="DRAFT_READBACK_VERIFIED"
                record["observed_caption_chars"]=len(text)
                (OUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
        report["status"]="ALL_CHANNEL_DRAFTS_VERIFIED" if all(x["status"] in
          ("DRAFT_READBACK_VERIFIED","EXISTING_DRAFT") for x in report["networks"]) and len(report["networks"])==3 else "PARTIAL_DRAFTS_REQUIRE_MANUAL_CHECK"
    except Exception as e:
        report["status"]="BLOCKED_"+type(e).__name__
        report["failure_category"]=str(e)[:140]
    finally:
        (OUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        print("ACOLAD_EXPERT_NOVINHUB_DRAFTS "+json.dumps(report,ensure_ascii=False),flush=True)
    return report

if __name__=="__main__":
    report=run()
    sys.exit(0 if report.get("status")=="ALL_CHANNEL_DRAFTS_VERIFIED" else 2)
