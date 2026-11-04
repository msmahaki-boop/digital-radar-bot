#!/usr/bin/env python3
"""Guarded Acolad V4 daily narrative + NovinHub scheduling. Scheduled != Published."""
from __future__ import annotations
import argparse,json,os,re,sys,time
from datetime import datetime,timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import requests
from PIL import Image
from acolad_novinhub_bridge import API,headers,token,as_items,create_post,upload_file
from acolad_editorial_trust_gate import evaluate
from acolad_voice_v4_guard import audience_issues
from acolad_story_image_ladder import MODELS,attempt,safe_stock,commons_stock
from acolad_narrative_visual_v2 import render,scene_chunks,CONCEPT_DIR

TZ=ZoneInfo("Asia/Tehran")
OUT=Path("acolad_v4_daily_publication")
SOURCE=Path("acolad_luna_research_preview/selected_evidence.json")
STORY=Path("acolad_daily_editorial_output/current_story.json")
STATUS=Path("acolad_daily_editorial_output/preview_status.json")
ACCOUNTS={"telegram":233472,"bale":233497,"instagram":230527}
CLOCK={"telegram":(17,30),"bale":(17,35),"instagram":(18,0)}
FOOTER=("🌐 [acolad.ir](https://acolad.ir/)\n"
 "📢 کانال تلگرام: [@acoladagency](https://t.me/acoladagency)\n"
 "ارتباط و مشاوره: [@acolad_agency](https://t.me/acolad_agency)")
APPROVAL="APPROVED_AUTO_PUBLISH_ALL_THREE_20261104"
MAX_IMAGE_CALLS=8

def due(day,net):
    h,m=CLOCK[net]
    return datetime(day.year,day.month,day.day,h,m,tzinfo=TZ)
def tehran_now():return datetime.now(TZ)
def report(state,**data):
    OUT.mkdir(parents=True,exist_ok=True)
    obj={"status":state,"published_confirmed":False,
         "notes":"provider scheduled receipts are not proof of platform publication",
         "date_tehran":tehran_now().date().isoformat(),**data}
    (OUT/"status.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ACOLAD_V4_PRODUCTION "+json.dumps(obj,ensure_ascii=False),flush=True)
    return obj

def check_time():
    now=tehran_now();day=now.date()
    if due(day,"telegram")-now<timedelta(minutes=90):
        raise RuntimeError("SAFE_SCHEDULING_WINDOW_MISSED")
    return day

def provider_accounts(key,session=requests):
    res=session.get(API+"/account",headers=headers(key),timeout=35)
    if res.status_code!=200:raise RuntimeError("NOVINHUB_ACCOUNT_UNAVAILABLE")
    rows=as_items(res.json())
    if rows is None:raise RuntimeError("INVALID_NOVINHUB_ACCOUNTS")
    for net,num in ACCOUNTS.items():
        found=[x for x in rows if isinstance(x,dict) and str(x.get("id"))==str(num)]
        if len(found)!=1 or net not in str(found[0].get("type","")).lower() or found[0].get("login_required"):
            raise RuntimeError("NOVINHUB_ACCOUNT_UNVERIFIED_"+net)

def posted_for_day(key,net,day,session=requests):
    res=session.get(API+"/post",headers=headers(key),timeout=40,
      params={"account_ids[]":str(ACCOUNTS[net]),"order":"id",
              "publish_from":day.isoformat(),"publish_to":day.isoformat()})
    if res.status_code!=200:raise RuntimeError("NOVINHUB_POST_LIST_FAILED_"+net)
    body=res.json();rows=as_items(body)
    if rows is None:raise RuntimeError("NOVINHUB_POST_LIST_INVALID_"+net)
    if isinstance(body,dict):
        page=body.get("paging") or ((body.get("data") or {}).get("paging")
            if isinstance(body.get("data"),dict) else {})
        if isinstance(page,dict) and (page.get("next") or
             int(page.get("totalPage") or 1)>1):
            raise RuntimeError("NOVINHUB_POST_LIST_PAGINATED")
    # If server does not return an explicit schedule_date, block rather than
    # risk a duplicate; if it does, restrict to same Tehran calendar date.
    matches=[]
    for p in rows:
        if not isinstance(p,dict):continue
        when=p.get("schedule_date") or p.get("publish_date")
        if when is None:matches.append(p);continue
        try:
            if str(when).isdigit():date_here=datetime.fromtimestamp(int(when),TZ).date()
            else:date_here=datetime.fromisoformat(str(when).replace("Z","+00:00")).astimezone(TZ).date()
            if date_here==day:matches.append(p)
        except (TypeError,ValueError,OverflowError):matches.append(p)
    return matches

def preflight(key,day):
    provider_accounts(key)
    dup={net:len(posted_for_day(key,net,day)) for net in ACCOUNTS}
    if any(dup.values()):raise RuntimeError("DAILY_PROVIDER_POST_EXISTS_"+str(dup))

def generate_editorial(day):
    import acolad_daily_editorial_v1 as daily
    if not daily.run_preview(day=day,budget_usd=0.018):
        return None,None
    meta=json.loads(STATUS.read_text(encoding="utf-8"))
    story=json.loads(STORY.read_text(encoding="utf-8"))
    evidence=json.loads(SOURCE.read_text(encoding="utf-8"))
    if (meta.get("day_tehran")!=day.isoformat() or
        not meta.get("dynamic_story_ready_for_design") or
        not (meta.get("voice_v4_gate") or {}).get("passed")):
        raise RuntimeError("V4_EDITORIAL_STATUS_REJECTED")
    verdict=evaluate(story,evidence)
    if not verdict["passed"]:raise RuntimeError("PRIMARY_EVIDENCE_VETO")
    if not 6<=len(story.get("slides",[]))<=15:
        raise RuntimeError("STORY_WRONG_FRAME_COUNT")
    if any(audience_issues(s.get("text","")) for s in story["slides"]):
        raise RuntimeError("V4_STYLE_VETO")
    story["sources"]=evidence
    return story,evidence

def model_json(system,data):
    key=os.getenv("GAPGPT_API_KEY","").strip()
    if not key:raise RuntimeError("GAPGPT_KEY_MISSING")
    res=requests.post("https://api.gapgpt.app/v1/chat/completions",
      headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},
      json={"model":"gpt-6-luna","messages":[
        {"role":"system","content":system},
        {"role":"user","content":json.dumps(data,ensure_ascii=False)}],
        "max_tokens":2500},timeout=170)
    if res.status_code!=200:raise RuntimeError("EDITORIAL_API_HTTP_"+str(res.status_code))
    obj=res.json()
    text=str((obj.get("choices") or [{}])[0].get("message",{}).get("content") or "").strip()
    if not text:raise RuntimeError("EDITORIAL_API_EMPTY")
    if not text.startswith("{"):
        text=text[text.find("{"):text.rfind("}")+1]
    result=json.loads(text)
    if not isinstance(result,dict):raise RuntimeError("EDITORIAL_MODEL_JSON_INVALID")
    return result

def make_channel_copies(story,evidence):
    rubric=("تو نویسنده آکولاد هستی. با زبان یکدست و محاوره‌ایِ ایرانی "
      "دو متن مستقل تلگرام و بله و یک کپشن اینستاگرام تولید کن. "
      "به ترتیب ماجرا، گره، کشف و راهکار قابل آزمون وفادار باش؛ "
      "قهرمان فرضی را به عنوان آدم واقعی پژوهش معرفی نکن. "
      "هیچ آمار یا پیامد قطعی بی‌سند نساز. 📌، URL، نام رسانه واسطه، "
      "منبع در پایان و شناسه فنی ممنوع؛ امضای برند را بعداً سیستم اضافه می‌کند. "
      "خروجی فقط JSON با کلیدهای telegram,bale,instagram است.")
    evidence_safe=[{k:s.get(k) for k in ("title","publisher","excerpt","date","url")}
                   for s in evidence[:3]]
    result=model_json(rubric,{"story":story,"evidence":evidence_safe})
    captions={}
    for net,minimum,maximum in (("telegram",400,1800),("bale",180,700),("instagram",60,500)):
        message=result.get(net)
        if not isinstance(message,str):raise RuntimeError("MISSING_COPY_"+net)
        message=message.strip()
        if not minimum<=len(message)<=maximum or audience_issues(message):
            raise RuntimeError("LOW_QUALITY_OR_INVALID_COPY_"+net)
        if re.search(r"https?://|www[.]|ACOLAD[-_]|(?:منبع|source)\s*[:：]",message,re.I):
            raise RuntimeError("SOURCE_LEAK_IN_COPY_"+net)
        captions[net]=message+("\n\n"+FOOTER if net in ("telegram","bale") else "")
    return captions

def critics_approve(story,evidence,captions):
    reviews=[]
    evidence_short=[{k:s.get(k) for k in ("title","excerpt","date")} for s in evidence[:3]]
    for i in (1,2):
        prompt=("تو منتقد سختگیر شماره "+str(i)+" هستی، مستقل از پاسخ منتقد دیگر. "
            "صداقت و سند ۲۵، بینش کسب‌وکار ۲۰، بافت ایران و فهم‌پذیری ۲۰، "
            "یکدستی لحن محاوره ۱۵، ریتم روایت ۱۰ و نتیجه مفید ۱۰ = ۱۰۰. "
            "یک ادعای بی‌سند یا نثر گیج‌کننده باید رد شود. "
            "فقط JSON با score عدد صحیح 0..100، veto بولی و reason متن کوتاه.")
        result=model_json(prompt,{"slides":[s.get("text") for s in story["slides"]],
           "evidence":evidence_short,"captions":captions})
        score=result.get("score")
        if type(score)is not int or not 0<=score<=100 or type(result.get("veto"))is not bool:
            raise RuntimeError("CRITIC_RESULT_INVALID")
        review={"score":score,"veto":result["veto"] or score<85,
                "reason_short":str(result.get("reason") or "")[:90]}
        reviews.append(review)
    return reviews

def illustrate(story):
    CONCEPT_DIR.mkdir(parents=True,exist_ok=True)
    for old in CONCEPT_DIR.glob("scene_[0-9][0-9].png"):old.unlink()
    groups=scene_chunks(story)
    if len(groups)<2:raise RuntimeError("NO_DISTINCT_VISUAL_SCENES")
    n=min(4,len(groups),max(2,round(len(story["slides"])/2.8)))
    indexes={round(i*(len(groups)-1)/(n-1)) for i in range(n)}
    selected=[int(groups[i][0]["scene"]) for i in sorted(indexes)]
    attempted=0;records=[]
    for sid in selected:
        batch=[s for s in story["slides"] if int(s.get("scene_id",0))==sid]
        primary=(story.get("sources") or [{}])[0]
        brief=SimpleNamespace(title_fa=str(story.get("topic") or "")[:130],
            original_title=str(primary.get("title") or story.get("topic") or "")[:190],
            summary_fa=("SCENE: "+str(batch[0].get("visual_idea") or "")[:180]+
                        " ACTION: "+" ".join(str(x.get("text") or "") for x in batch)[:300]),
            topic=story.get("topic") or "")
        image=None;tried=[]
        for model in MODELS:
            if attempted>=8:break
            image,result=attempt(brief,model)
            tried.append({"provider":model,"status":result.get("status")})
            if result.get("status")!="GAPGPT_KEY_MISSING":attempted+=1
            if image is not None:break
        if image is None:
            image,res=safe_stock(brief)
            tried.append({"provider":"Pexels","status":res.get("status")})
        if image is None:
            image,res=commons_stock(brief)
            tried.append({"provider":"Commons","status":res.get("status")})
        if image is not None:image.save(CONCEPT_DIR/f"scene_{sid:02d}.png","PNG")
        records.append({"scene":sid,"has_image":image is not None,"attempts":tried})
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"image_provenance.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
    frames_folder=OUT/"frames"
    layout=render(story,frames_folder,allow_stock=False)
    frames=sorted(frames_folder.glob("story_*.png"))
    if len(frames)!=len(story["slides"]):raise RuntimeError("RENDER_INCOMPLETE")
    for file in frames:
        with Image.open(file) as im:
            if im.format!="PNG" or im.size!=(1080,1920):raise RuntimeError("FRAME_INVALID")
            im.verify()
    return frames,records

def schedule_bale(key,body,when):
    payload={"type":"text","account_ids":[ACCOUNTS["bale"]],
        "caption":body,"media_ids":[],"is_draft":0,"is_scheduled":1,
        "bale_has_signature":0,"schedule_date":when}
    r=requests.post(API+"/post",headers={**headers(key),"Content-Type":"application/json"},
                    json=payload,timeout=75)
    if r.status_code not in (200,201):raise RuntimeError("BALE_SCHEDULE_HTTP_"+str(r.status_code))
    obj=r.json();d=obj.get("data",obj) if isinstance(obj,dict) else None
    if not isinstance(d,dict) or not d.get("id"):raise RuntimeError("BALE_SCHEDULE_ID_MISSING")
    return d["id"]

def submit(key,day,captions,frames):
    preflight(key,day)
    receipts=[]
    for net in ("telegram","bale","instagram"):
        # A retry after any partial write must not send a second same-day post.
        if posted_for_day(key,net,day):
            receipts.append({"network":net,"status":"BLOCKED_ALREADY_HAS_POST"})
            continue
        publish_at=due(day,net)
        if publish_at-tehran_now()<timedelta(minutes=35):
            raise RuntimeError("PUBLISH_WINDOW_TOO_CLOSE_"+net)
        epoch=int(publish_at.timestamp())
        if net=="bale":ident=schedule_bale(key,captions[net],epoch)
        elif net=="telegram":
            ident=create_post(key,net,captions[net],[],draft=False,schedule_epoch=epoch)["post_id"]
        else:
            media=[upload_file(key,p) for p in frames]
            ident=create_post(key,net,captions[net],media,draft=False,schedule_epoch=epoch)["post_id"]
        item={"network":net,"post_id":ident,"target_local":publish_at.isoformat(),
              "status":"SCHEDULE_REQUEST_ACCEPTED_NOT_PUBLISHED"}
        receipts.append(item)
        (OUT/"partial_receipts.json").write_text(json.dumps(receipts,ensure_ascii=False,indent=2),encoding="utf-8")
        for n in range(3):
            try:
                rows=posted_for_day(key,net,day)
                if any(str(p.get("id"))==str(ident) for p in rows):
                    item["status"]="SCHEDULE_VISIBLE_NOT_PUBLISHED";break
            except RuntimeError:pass
            if n<2:time.sleep(3)
        if item["status"]!="SCHEDULE_VISIBLE_NOT_PUBLISHED":
            raise RuntimeError("SCHEDULE_NOT_READBACK_VERIFIED_"+net)
    return receipts

def run(mode):
    try:
        day=check_time() if mode=="auto" else tehran_now().date()
        key=token()
        if mode=="auto":preflight(key,day)
        else:provider_accounts(key)
        story,evidence=generate_editorial(day)
        if not story:return report("SKIPPED_EDITORIAL_QA_NO_GOOD_STORY",scheduled_count=0)
        copies=make_channel_copies(story,evidence)
        reviews=critics_approve(story,evidence,copies)
        if any(x["veto"] for x in reviews):
            return report("SKIPPED_CRITIC_SCORE_BELOW_85",critics=reviews,scheduled_count=0)
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/"story.json").write_text(json.dumps(story,ensure_ascii=False,indent=2),encoding="utf-8")
        (OUT/"sources_private.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
        (OUT/"captions.json").write_text(json.dumps(copies,ensure_ascii=False,indent=2),encoding="utf-8")
        frames,art=illustrate(story)
        if mode=="preview":
            return report("PREVIEW_VALIDATED_NO_WRITES",frames=len(frames),art=art,critics=reviews,
                          scheduled_count=0)
        if mode!="auto" or os.getenv("ACOLAD_AUTOPUBLISH_APPROVAL")!=APPROVAL:
            raise RuntimeError("MISSING_EXPLICIT_AUTOPUBLISH_APPROVAL")
        receipts=submit(key,day,copies,frames)
        return report("SCHEDULED_PROVIDER_CONFIRMATION_NOT_PUBLISHED",
                      receipts=receipts,scheduled_count=sum(x["status"]=="SCHEDULE_VISIBLE_NOT_PUBLISHED" for x in receipts),
                      critics=reviews,frames=len(frames))
    except Exception as exc:return report("BLOCKED_"+type(exc).__name__,reason=str(exc)[:190])

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--mode",choices=("preview","auto"),default="preview")
    output=run(p.parse_args().mode)
    sys.exit(0 if output["status"] in ("PREVIEW_VALIDATED_NO_WRITES","SKIPPED_EDITORIAL_QA_NO_GOOD_STORY",
      "SKIPPED_CRITIC_SCORE_BELOW_85","SCHEDULED_PROVIDER_CONFIRMATION_NOT_PUBLISHED") else 2)
