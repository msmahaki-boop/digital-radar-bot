#!/usr/bin/env python3
"""Read-only Acolad cross-channel preflight; never sends, uploads, drafts or publishes."""
from __future__ import annotations
import json
import os
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

BASE="https://api.novinhub.com/token/v2"
OUTPUT=Path("acolad_crosschannel_health")
TEHRAN=ZoneInfo("Asia/Tehran")
def today():
    return datetime.now(TEHRAN).date().isoformat()

def novin_token():
    candidates=[os.getenv(n,"").strip() for n in ("NOVINHUB_API_TOKEN","NOVINHUB_TOKEN","NOVINHUB_ACCESS_TOKEN")]
    present=[s for s in candidates if s]
    return (present[0] if len(present)==1 else None),len(present)

def novinhub_status(session=requests):
    token,count=novin_token()
    if count>1:return {"status":"MULTIPLE_TOKEN_VARIABLES_SET_ABORT"}
    if not token:return {"status":"SECRET_NOT_SET","matched_accounts":0}
    try:
        r=session.get(BASE+"/account",headers={"Authorization":"Bearer "+token,
                      "Accept":"application/json"},timeout=25)
        if r.status_code!=200:return {"status":"ACCOUNT_HTTP_ERROR","http_status":r.status_code}
        parsed=r.json()
        if isinstance(parsed,list): accounts=parsed
        elif isinstance(parsed,dict):
            raw=parsed.get("data",parsed.get("accounts",[]))
            accounts=raw if isinstance(raw,list) else raw.get("data",[]) if isinstance(raw,dict) else []
        else:accounts=[]
        if not isinstance(accounts,list): accounts=[]
        matches=[]
        for acct in accounts:
            if not isinstance(acct,dict):continue
            hay=" ".join(str(acct.get(k) or "") for k in ("identifier","name","profile_url")).lower()
            if "acolad.agency" in hay or "acoladagency" in hay:
                matches.append({"id":acct.get("id"),"network":acct.get("type"),
                                "relogin_required":bool(acct.get("login_required"))})
        return {"status":"ACCOUNT_READ_OK","total_accounts":len(accounts),
                "matched_accounts":len(matches),"matches":matches}
    except (requests.RequestException,ValueError,TypeError) as e:
        return {"status":"ACCOUNT_ERROR_"+type(e).__name__}

def telegram_state(date=None):
    date=date or today()
    p=Path("telegram_public_state.json")
    if not p.is_file():return {"status":"STATE_NOT_FOUND"}
    try:
        data=json.loads(p.read_text(encoding="utf-8"))
        rows=[{"slot":r.get("slot"),"message_id":r.get("message_id"),"status":r.get("status")}
              for r in data.get("slots",[]) if r.get("slot","").startswith(date) and r.get("status")=="sent"]
        return {"status":"RECEIPT_HISTORY_READ","date_tehran":date,"published_receipts":rows}
    except (ValueError,OSError) as e:return {"status":"STATE_READ_ERROR_"+type(e).__name__}

def buffer_today():
    if not os.getenv("BUFFER_API_KEY"):
        return {"status":"BUFFER_SECRET_MISSING"}
    try:
        from daily_story_pipeline import buffer_identity,recent_buffer_posts,DAILY_MARKER
        org,channel=buffer_identity()
        posts=recent_buffer_posts(org,channel)
        rows=[]
        for post in posts:
            value=str(post.get("text") or "")
            if (DAILY_MARKER+today()) in value:
                rows.append({"id":post.get("id"),"status":post.get("status"),
                             "dueAt":post.get("dueAt"),"sentAt":post.get("sentAt")})
        return {"status":"BUFFER_READ_OK","found_today":len(rows),"posts":rows}
    except Exception as e:
        return {"status":"BUFFER_READ_ERROR_"+type(e).__name__}

def run(session=requests,read_buffer=True):
    report={"mode":"READ_ONLY","date_tehran":today(),"novinhub":novinhub_status(session),
            "telegram":telegram_state(),
            "buffer":buffer_today() if read_buffer else {"status":"NOT_CHECKED"},
            "publish_calls":0,"post_calls":0,"queue_calls":0,"draft_calls":0}
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ACOLAD_NETWORK_HEALTH "+json.dumps(report,ensure_ascii=False))
    return report

if __name__=="__main__":run()
