#!/usr/bin/env python3
"""Acolad hourly IMMEDIATE publisher; fail closed for ambiguous provider receipts."""
from __future__ import annotations
import argparse,json,os,sys,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from PIL import Image
from acolad_novinhub_bridge import API,as_items,headers,token,upload_file
import acolad_v4_daily_autopublish as engine

TZ=ZoneInfo("Asia/Tehran")
OUT=Path("acolad_v4_daily_publication")
READY=OUT/"hourly_ready.json"
EDITORIAL_CACHE=OUT/"verified_story_checkpoint.json"
NETWORKS=("telegram","bale","instagram")
ACCOUNT={"telegram":233472,"bale":233497,"instagram":230527}
DONE={"published","sent","success","completed","complete"}
FAILED={"failed","error","rejected","cancelled"}
APPROVAL="ACOLAD_USER_APPROVED_HOURLY_IMMEDIATE_20261107"

def now():return datetime.now(TZ)
def report(status,networks=None,**extra):
    OUT.mkdir(parents=True,exist_ok=True)
    obj={"status":status,"date_tehran":now().date().isoformat(),
         "networks":networks or {},"publication_verified":False,
         "method":"IMMEDIATE_NOT_DRAFT_NOT_SCHEDULED",**extra}
    (OUT/"hourly_status.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("ACOLAD_HOURLY_PUBLICATION "+json.dumps(obj,ensure_ascii=False),flush=True)
    return obj

def provider_list(key,net,day,session=requests):
    res=session.get(API+"/post",headers=headers(key),params={
        "account_ids[]":str(ACCOUNT[net]),"order":"id","with":"post(accountPost)",
        "publish_from":day.isoformat(),"publish_to":(day+timedelta(days=1)).isoformat()},timeout=45)
    if res.status_code!=200:raise RuntimeError("PROVIDER_READ_HTTP_"+net+"_"+str(res.status_code))
    obj=res.json();rows=as_items(obj)
    if rows is None:raise RuntimeError("PROVIDER_LIST_UNRECOGNIZED_"+net)
    for node in (obj,obj.get("data") if isinstance(obj,dict) else None):
        if isinstance(node,dict):
            page=node.get("paging") or node.get("pagination") or {}
            if isinstance(page,dict) and (
                page.get("next") or page.get("next_page_url") or page.get("next_page") or
                int(page.get("totalPage") or 1)>1):
                raise RuntimeError("PROVIDER_LIST_PAGINATED_"+net)
    if len(rows)>=100:raise RuntimeError("PROVIDER_LIST_MAY_BE_TRUNCATED_"+net)
    return rows

def assess(rows,net):
    if not rows:return {"state":"ABSENT"}
    entries=[]
    for group in rows:
        if not isinstance(group,dict):raise RuntimeError("MALFORMED_POST_GROUP_"+net)
        details=group.get("post") or group.get("posts") or []
        if isinstance(details,dict):details=[details]
        if not isinstance(details,list):raise RuntimeError("MALFORMED_POST_DETAILS_"+net)
        relevant=[p for p in details if isinstance(p,dict) and str(p.get("account_id"))==str(ACCOUNT[net])]
        statuses=[]
        for p in relevant:
            state=str(p.get("status") or "").lower()
            remote=p.get("accountPost") or p.get("account_post") or {}
            remote_id=(remote.get("post_id") or remote.get("id")) if isinstance(remote,dict) else None
            statuses.append((state,bool(remote_id)))
        if not details:
            statuses=[(str(group.get("status") or "").lower(),False)]
        if statuses:entries.append({"id":group.get("id"),"statuses":statuses})
    if not entries:return {"state":"PENDING_OR_UNKNOWN"}
    if any(status in DONE and remote for g in entries for status,remote in g["statuses"]):
        return {"state":"PUBLISHED","ids":[g["id"] for g in entries][:6]}
    if len(entries)==1 and entries[0]["statuses"] and all(
            status in FAILED for status,_ in entries[0]["statuses"]):
        return {"state":"FAILED","group_id":entries[0]["id"]}
    return {"state":"PENDING_OR_UNKNOWN","ids":[g["id"] for g in entries][:6]}

def observe(key,day):
    engine.provider_accounts(key)
    return {n:assess(provider_list(key,n,day),n) for n in NETWORKS}

def existing_bundle(day):
    if not READY.exists():return None
    d=json.loads(READY.read_text(encoding="utf8"))
    if d.get("day")!=day.isoformat() or d.get("validated") is not True:
        raise RuntimeError("CACHED_BUNDLE_DAY_INVALID")
    copies=d.get("captions") or {}
    if set(copies)!=set(NETWORKS):raise RuntimeError("CACHED_COPIES_INCOMPLETE")
    if any(not isinstance(copies[n],str) or len(copies[n])<40 for n in NETWORKS):
        raise RuntimeError("CACHED_COPY_EMPTY")
    if any(not copies[n].endswith(engine.FOOTER) for n in ("telegram","bale")):
        raise RuntimeError("CACHED_BRAND_SIGNATURE_INVALID")
    images=sorted((OUT/"frames").glob("story_*.png"))
    if not 6<=len(images)<=15 or len(images)!=d.get("nframes"):
        raise RuntimeError("CACHED_FRAMES_INCOMPLETE")
    for path in images:
        with Image.open(path) as im:
            if im.size!=(1080,1920) or im.format!="PNG":raise RuntimeError("BAD_CACHED_IMAGE")
            im.verify()
    return d,images

def has_current_substantive_evidence(evidence,day):
    """Do not label an old paper as today's story; require recent dated body."""
    from datetime import date
    if not isinstance(evidence,list):
        return False
    for item in evidence:
        if not isinstance(item,dict) or item.get("evidence_depth") not in ("full_article","abstract"):
            continue
        try:
            age=(day-date.fromisoformat(str(item.get("date") or ""))).days
        except (ValueError,TypeError):
            continue
        if 0<=age<=21:
            return True
    return False


def check_verified_editorial(story,evidence):
    """Re-run ALL source, beat, numerical and voice gates on restored content."""
    import acolad_luna_research_preview as research
    from acolad_editorial_trust_gate import evaluate
    from acolad_voice_v4_guard import audience_issues
    from acolad_daily_editorial_v1 import story_is_distinct
    if not isinstance(story,dict) or not isinstance(evidence,list):
        raise RuntimeError("EDITORIAL_CACHE_BAD_SHAPE")
    if not has_current_substantive_evidence(evidence,now().date()):
        raise RuntimeError("EDITORIAL_STALE_PRIMARY_EVIDENCE_NO_TODAY_PUBLICATION")
    urls={str(x.get("url") or "") for x in evidence if isinstance(x,dict)}
    if story.get("story_link") and str(story["story_link"]) not in urls:
        raise RuntimeError("EDITORIAL_UNSUPPORTED_STORY_LINK")
    if not story_is_distinct(story):
        raise RuntimeError("EDITORIAL_CACHE_REPEATED_STORY")
    issues=research.story_quality(story,evidence)+research.cinematic_quality(story,evidence)
    if issues:
        raise RuntimeError("EDITORIAL_CACHE_QA_VETO:"+",".join(issues[:3]))
    gate=evaluate(story,evidence)
    if not gate.get("passed"):
        raise RuntimeError("EDITORIAL_CACHE_SOURCE_VETO:"+",".join(gate.get("hard_vetoes",[])[:3]))
    for frame in story.get("slides",[]):
        if audience_issues(frame.get("text","")):
            raise RuntimeError("EDITORIAL_CACHE_VOICE_VETO")
    return True

def saved_editorial(day):
    if not EDITORIAL_CACHE.exists():return None
    obj=json.loads(EDITORIAL_CACHE.read_text(encoding="utf8"))
    if obj.get("day")!=day.isoformat() or obj.get("validated") is not True:
        raise RuntimeError("EDITORIAL_CACHE_WRONG_DAY_OR_UNVALIDATED")
    story,evidence=obj.get("story"),obj.get("evidence")
    if not has_current_substantive_evidence(evidence,day):
        print("STALE_EDITORIAL_CACHE_SKIPPED_FRESH_SOURCE_REQUIRED",flush=True)
        return None
    check_verified_editorial(story,evidence)
    return story,evidence

def save_editorial(day,story,evidence):
    check_verified_editorial(story,evidence)
    OUT.mkdir(parents=True,exist_ok=True)
    obj={"day":day.isoformat(),"validated":True,"story":story,"evidence":evidence}
    EDITORIAL_CACHE.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf8")

def prepare(day):
    cached=saved_editorial(day)
    if cached is not None:
        story,evidence=cached
        print("ACOLAD_VERIFIED_EDITORIAL_CACHE_HIT",day.isoformat(),flush=True)
    else:
        story,evidence=engine.generate_editorial(day)
    if story is None:
        # Keep external API/transport failures distinct from editorial quality
        # vetoes; an unavailable model is not evidence that a story is bad.
        if engine.STATUS.is_file():
            upstream=json.loads(engine.STATUS.read_text(encoding="utf8"))
            if upstream.get("status") in ("PIPELINE_ERROR_NO_PUBLICATION",
                                          "RESEARCH_OUTPUT_MISSING"):
                raise RuntimeError("EDITORIAL_UPSTREAM_TECHNICAL_FAILURE")
        return None
    # Persist at the EARLIEST defensible checkpoint before additional
    # caption/critic/image calls. A provider HTTP429 must not waste this story.
    save_editorial(day,story,evidence)
    copies=engine.make_channel_copies(story,evidence)
    critics=engine.critics_approve(story,evidence,copies)
    if any(x["veto"] for x in critics):
        # Save rejected copy for editorial audit without treating it as READY.
        # An independent quality veto must trigger a genuinely new next-hour
        # candidate rather than endlessly re-criticizing identical cached text.
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/"critic_rejected_story.json").write_text(json.dumps({
            "day":day.isoformat(),"status":"REJECTED_NOT_PUBLISHED",
            "critics":critics,"source_urls":[s.get("url") for s in evidence]
        },ensure_ascii=False,indent=2),encoding="utf8")
        EDITORIAL_CACHE.unlink(missing_ok=True)
        print("CRITIC_QA_VETO "+json.dumps(critics,ensure_ascii=False),flush=True)
        print("CRITIC_VETO_FRESH_RESEARCH_REQUIRED_NEXT_ATTEMPT",flush=True)
        return None
    frames,art=engine.illustrate(story)
    OUT.mkdir(parents=True,exist_ok=True)
    document={"day":day.isoformat(),"validated":True,"captions":copies,"critics":critics,"nframes":len(frames)}
    (OUT/"story.json").write_text(json.dumps(story,ensure_ascii=False,indent=2),encoding="utf8")
    (OUT/"sources_private.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf8")
    READY.write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding="utf8")
    return document,frames

def send_now(key,net,caption,media,session=requests):
    if net not in NETWORKS:raise ValueError("Invalid target")
    if not caption or (net=="instagram" and len(media)<6):raise ValueError("Incomplete story")
    payload={"type":"story" if net=="instagram" else "text",
        "account_ids":[ACCOUNT[net]],"caption":caption,
        "media_ids":media if net=="instagram" else [],
        "is_draft":0,"is_scheduled":0,
        "schedule_date":int(datetime.now().timestamp())}
    if net=="bale":payload["bale_has_signature"]=0
    r=session.post(API+"/post",headers={**headers(key),"Content-Type":"application/json"},
                   json=payload,timeout=80)
    if r.status_code not in (200,201):
        detail=""
        if r.status_code==400:
            try:
                obj=r.json()
                error=obj.get("error") if isinstance(obj,dict) else None
                if isinstance(error,dict):
                    fields=error.get("errors") or error.get("validation") or {}
                    if isinstance(fields,dict):
                        detail="_FIELDS_"+",".join(sorted(str(x)[:30] for x in fields)[:6])
                    trace=error.get("trace_id") or obj.get("trace_id")
                    if isinstance(trace,(str,int)) and str(trace).replace("-","").isalnum():
                        detail+="_TRACE_"+str(trace)[:50]
            except (ValueError,TypeError,AttributeError):
                pass
        raise RuntimeError("IMMEDIATE_POST_HTTP_"+net+"_"+str(r.status_code)+detail)
    obj=r.json();row=obj.get("data",obj) if isinstance(obj,dict) else {}
    group_id=row.get("id") if isinstance(row,dict) else None
    if not group_id:raise RuntimeError("POST_RECEIPT_AMBIGUOUS_"+net)
    return group_id

def retry_failed(key,net,post_id,session=requests):
    if not post_id or not str(post_id).isdigit():
        raise RuntimeError("RETRY_REQUIRES_UNAMBIGUOUS_ID")
    r=session.put(API+"/post/"+str(post_id)+"/retry",headers=headers(key),timeout=65)
    if r.status_code not in (200,201):
        raise RuntimeError("PROVIDER_RETRY_HTTP_"+net+"_"+str(r.status_code))

def execute(mode):
    time_here=now();day=time_here.date()
    if mode=="hourly" and not 9<=time_here.hour<=23:
        return report("OUTSIDE_DAILY_09_23_WINDOW")
    if os.getenv("ACOLAD_HOURLY_PUBLISH_APPROVAL")!=APPROVAL:
        return report("BLOCKED_APPROVAL_GATE")
    key=token()
    states=observe(key,day)
    if all(s["state"]=="PUBLISHED" for s in states.values()):
        return report("ALL_THREE_PUBLISHED_VERIFIED",states,publication_verified=True)
    for net in NETWORKS:
        if states[net]["state"]=="FAILED":
            retry_failed(key,net,states[net]["group_id"])
            states[net]["state"]="RETRY_REQUESTED"
    if any(s["state"] in ("PENDING_OR_UNKNOWN","RETRY_REQUESTED") for s in states.values()):
        return report("WAIT_PROVIDER_DO_NOT_DUPLICATE",states)
    # A previous run may have got an HTTP timeout after NovinHub accepted
    # an irreversible write. Cross-run cached intent blocks blind resending.
    intent_file=OUT/"send_intents.json"
    intents=json.loads(intent_file.read_text(encoding="utf8")) if intent_file.exists() else {}
    if intents.get("day")==day.isoformat():
        for n in NETWORKS:
            if n in intents.get("sent_or_unknown",{}) and states[n]["state"]=="ABSENT":
                states[n]={"state":"PENDING_OR_UNKNOWN","intent":"REMOTE_RECEIPT_NOT_VISIBLE"}
    if any(s["state"]=="PENDING_OR_UNKNOWN" for s in states.values()):
        return report("WAIT_PROVIDER_OR_UNKNOWN_DELIVERY_NO_DUPLICATES",states)
    missing=[n for n in NETWORKS if states[n]["state"]=="ABSENT"]
    missing.sort(key={"instagram":0,"bale":1,"telegram":2}.get)
    if not missing:return report("NOTHING_SAFE_TO_SEND",states)
    bundle=existing_bundle(day)
    if not bundle and any(s["state"]=="PUBLISHED" for s in states.values()):
        return report("BLOCKED_PARTIAL_PUBLISH_WITHOUT_ORIGINAL_BUNDLE",states)
    if not bundle:
        bundle=prepare(day)
        if not bundle:return report("EDITORIAL_VETO_TRY_AGAIN_NEXT_HOUR",states)
    d,frames=bundle
    media=[]
    if "instagram" in missing:
        media=[upload_file(key,path) for path in frames]
        if len(media)!=len(frames):raise RuntimeError("INCOMPLETE_MEDIA_UPLOAD")
    submitted=[]
    for net in missing:
        fresh=assess(provider_list(key,net,day),net)
        if fresh["state"]!="ABSENT":
            states[net]=fresh
            continue
        # Record the network intent BEFORE the mutation. If the request
        # times out, the next run must inspect the provider rather than re-send.
        if intents.get("day")!=day.isoformat():
            intents={"day":day.isoformat(),"sent_or_unknown":{}}
        intents["sent_or_unknown"][net]={"state":"SENDING_NO_CONFIRMED_RECEIPT"}
        intent_file.write_text(json.dumps(intents,ensure_ascii=False,indent=2),encoding="utf8")
        group_id=send_now(key,net,d["captions"][net],media)
        intents["sent_or_unknown"][net]={"state":"ACCEPTED","group_id":group_id}
        intent_file.write_text(json.dumps(intents,ensure_ascii=False,indent=2),encoding="utf8")
        submitted.append({"network":net,"group_id":group_id,
                          "state":"SUBMITTED_NOT_YET_PROVEN_PUBLISHED"})
        (OUT/"submission_receipts.json").write_text(
            json.dumps(submitted,ensure_ascii=False,indent=2),encoding="utf8")
    if submitted:time.sleep(10)
    states=observe(key,day)
    complete=all(s["state"]=="PUBLISHED" for s in states.values())
    return report("ALL_THREE_PUBLISHED_VERIFIED" if complete else
                  "SUBMITTED_WAITING_EXTERNAL_PUBLICATION",states,
                  publication_verified=complete,submissions=submitted)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("hourly","immediate"),default="hourly")
    a=p.parse_args()
    try:r=execute(a.mode)
    except Exception as e:r=report("BLOCKED_"+type(e).__name__,reason=str(e)[:170])
    sys.exit(0 if r["publication_verified"] else 2)
