#!/usr/bin/env python3
"""Exact V4 Telegram+Bale NovinHub Drafts; NO publication or scheduling."""
import argparse,json,os,re,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
import requests
from acolad_novinhub_bridge import API,token,headers,accounts,as_items,create_post

SRC=Path("editorial/previews/acolad_guest_checkout_v4_20261104.json")
OUT=Path("acolad_guest_checkout_novinhub_draft_receipts")
FOOTER="🌐 [acolad.ir](https://acolad.ir/)\n📢 کانال تلگرام: [@acoladagency](https://t.me/acoladagency)\nارتباط و مشاوره: [@acolad_agency](https://t.me/acolad_agency)"
ACCOUNTS={"telegram":233472,"bale":233497}

def draft_rows(key):
    res=requests.get(API+"/post/draft",headers=headers(key),timeout=35)
    if res.status_code!=200:raise RuntimeError("Cannot read drafts HTTP "+str(res.status_code))
    body=res.json()
    rows=as_items(body)
    if rows is None or len(rows)>=100:raise RuntimeError("Draft list unclear or possibly paginated")
    if isinstance(body,dict):
        for page in (body,body.get("data")):
            if isinstance(page,dict):
                paging=page.get("paging") or page.get("pagination")
                if isinstance(paging,dict) and any(paging.get(x) for x in ("next","next_page_url","next_page")):
                    raise RuntimeError("Draft list pagination not supported")
    return rows

def bale_draft(key,text):
    payload={"type":"text","caption":text,"account_ids":[233497],
             "media_ids":[],"is_draft":1,"is_scheduled":0,
             "bale_has_signature":0,
             "schedule_date":int((datetime.now(timezone.utc)+timedelta(days=1)).timestamp())}
    res=requests.post(API+"/post",headers={**headers(key),"Content-Type":"application/json"},
                      json=payload,timeout=65)
    if res.status_code not in (200,201):
        try:
            raw=res.json()
            err=(raw.get("error") or {}) if isinstance(raw,dict) else {}
            message=str(err.get("message") or "") if isinstance(err,dict) else ""
            message=re.sub(r"(?i)(?:bearer|sk-|token|api[_ -]?key)[\s:=]*[A-Za-z0-9_-]{6,}","[REDACTED]",message)
            message=re.sub(r"https?://[^\s]+","[URL]",message)
        except (ValueError,AttributeError):
            message="UNAVAILABLE"
        raise RuntimeError("Bale DRAFT HTTP "+str(res.status_code)+" validation="+message[:200])
    body=res.json()
    obj=body.get("data",body) if isinstance(body,dict) else None
    if not isinstance(obj,dict) or not obj.get("id"):raise RuntimeError("No Bale draft receipt ID")
    return obj["id"]

def run(mode):
    OUT.mkdir(parents=True,exist_ok=True)
    report={"mode":mode,"published":0,"scheduled":0,"queued":0,
        "instagram":"EXACT_9_STORY_IMAGES_NOT_IN_GITHUB; NOT_CREATED",
        "networks":[],"publication_requests":0}
    try:
        doc=json.loads(SRC.read_text(encoding="utf-8"))
        if doc.get("publication_allowed") is not False:raise RuntimeError("Preview lock missing")
        copies=doc["captions"]
        if copies["footer"]!=FOOTER:raise RuntimeError("Footer not exact")
        for network in ACCOUNTS:
            text=copies[network]
            if not text.endswith(FOOTER) or text.count(FOOTER)!=1:raise RuntimeError("Footer missing")
            if not 250<len(text)<1800 or "baymard.com" in text.lower():
                raise RuntimeError("Unexpected caption for "+network)
        k=token()
        live=accounts(k)
        if any(live[n]!=aid for n,aid in ACCOUNTS.items()):raise RuntimeError("Account mismatch")
        for network in ACCOUNTS:
            text=copies[network]
            previous=[p for p in draft_rows(k) if isinstance(p,dict) and str(p.get("caption") or "")==text]
            if len(previous)>1:raise RuntimeError("Ambiguous duplicate drafts")
            if previous:
                report["networks"].append({"network":network,"id":previous[0].get("id"),
                                            "status":"EXISTS_NOT_DUPLICATED","chars":len(text)})
                continue
            if mode=="read":
                report["networks"].append({"network":network,"status":"MISSING_READY_TO_DRAFT","chars":len(text)})
                continue
            if os.getenv("ACOLAD_GUEST_DRAFT_APPROVAL")!="APPROVED_ONLY_TWO_TEXT_DRAFTS":
                raise RuntimeError("Draft approval gate missing")
            post_id=(create_post(k,"telegram",text,[],draft=True)["post_id"]
                     if network=="telegram" else bale_draft(k,text))
            row={"network":network,"id":post_id,"status":"CREATED_READBACK_PENDING","chars":len(text)}
            report["networks"].append(row)
            (OUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            verify=[p for p in draft_rows(k) if isinstance(p,dict)
                    and str(p.get("id"))==str(post_id)
                    and str(p.get("caption") or "")==text]
            if not verify:raise RuntimeError("Draft receipt not verifiable by GET")
            if any(str(p.get("is_scheduled")).lower() not in ("none","false","0","") for p in verify):
                raise RuntimeError("Draft unexpectedly scheduled")
            row["status"]="DRAFT_READBACK_VERIFIED"
        report["status"]="READ_ONLY_READY" if mode=="read" else "TWO_TEXT_DRAFTS_VERIFIED"
    except Exception as e:
        report["status"]="BLOCKED_"+type(e).__name__
        report["error_category"]=str(e)[:145]
    finally:
        (OUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("GUEST_V4_NOVINHUB "+json.dumps(report,ensure_ascii=False),flush=True)
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("read","draft"),default="read")
    args=parser.parse_args()
    result=run(args.mode)
    sys.exit(0 if result.get("status") in ("READ_ONLY_READY","TWO_TEXT_DRAFTS_VERIFIED") else 2)
