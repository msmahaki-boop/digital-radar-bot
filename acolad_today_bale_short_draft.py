#!/usr/bin/env python3
"""Full evidence-backed narrative in a concise Bale DRAFT, never scheduled."""
import json,re,requests
from datetime import datetime,timedelta,timezone
from pathlib import Path
from acolad_narrative_today_art_and_preview import check_story
from acolad_novinhub_bridge import API,token,headers,as_items
OUTPUT=Path("acolad_bale_narrative_draft")
MARK="ACOLAD-BALE-NARRATIVE-20261104"
def cleaned(s):return re.sub(r"\*+","",str(s or "")).strip()
def concise(story):
    frames=story["slides"]
    choices=[0,1,2,3,6,8]
    paras=[cleaned(frames[x]["text"]) for x in choices if x<len(frames)]
    links=[s.get("url") for s in story["sources"] if str(s.get("url","")).startswith("https://")]
    msg=(cleaned(story.get("topic"))+"\n\n"+"\n\n".join(paras)+"\n\n"+
         "FlashProve نمونهٔ پژوهشی منتشرشده است، نه محصول آمادهٔ فروشگاه‌ها.\n"+
         "منبع: "+str(links[0])+"\n"+"آکولاد | "+MARK)
    if not 300<=len(msg)<=960:raise ValueError("Bale text exceeds bounded concise limit")
    return msg
def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    report={"mode":"BALE_CONCISE_NARRATIVE_DRAFT","published":0,"scheduled":0}
    try:
        story,_=check_story()
        message=concise(story)
        (OUTPUT/"bale_message.txt").write_text(message,encoding="utf-8")
        k=token()
        r=requests.get(API+"/post/draft",headers=headers(k),timeout=30)
        if r.status_code!=200:raise RuntimeError("Cannot read draft list")
        rows=as_items(r.json())
        if rows is None:raise RuntimeError("Unrecognized draft list")
        if any(MARK in str(row.get("caption") or "") for row in rows if isinstance(row,dict)):
            report["status"]="EXISTS_NO_DUPLICATE"
        else:
            payload={"type":"text","caption":message,"account_ids":[233497],
               "media_ids":[],"is_draft":1,"is_scheduled":0,"bale_has_signature":0,
               "schedule_date":int((datetime.now(timezone.utc)+timedelta(days=1)).timestamp())}
            res=requests.post(API+"/post",headers={**headers(k),"Content-Type":"application/json"},
                              json=payload,timeout=60)
            report["http_status"]=res.status_code
            if res.status_code not in (200,201):
                try:report["validation_message"]=str((res.json().get("error") or {}).get("message") or "")[:160]
                except Exception:pass
                report["status"]="PROVIDER_REJECTED"
            else:
                obj=res.json();data=obj.get("data",obj)
                report["post_id"]=data.get("id") if isinstance(data,dict) else None
                report["status"]="BALE_DRAFT_CREATED" if report["post_id"] else "NO_RECEIPT_ID"
        report["text_length"]=len(message)
    except Exception as exc:
        report["status"]="ERROR_"+type(exc).__name__
        report["reason"]=str(exc)[:140]
    (OUTPUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ACOLAD_BALE_NARRATIVE_RESULT "+json.dumps(report,ensure_ascii=False))
    return report
if __name__=="__main__":
    x=main()
    raise SystemExit(0 if x["status"] in ("BALE_DRAFT_CREATED","EXISTS_NO_DUPLICATE") else 2)
