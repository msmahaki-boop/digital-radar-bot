#!/usr/bin/env python3
"""Acolad V5 one-shot publisher: three unique natural chapters, square cover.
GitHub Actions approval marker and verified artifact are required separately.
No blind retry, no repost of old Nov8 Telegram 48..50 or Bale group 3699385.
"""
from __future__ import annotations
import hashlib,json,os,time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image
from acolad_human_story_v5 import validate,thread_parts
from acolad_gapgpt_transparent_art import verify_png
from acolad_novinhub_bridge import upload_file,token
from acolad_v4_hourly_publish import provider_list,send_now,ACCOUNT,ProviderValidationRejected
from acolad_native_story_threads import credentials,access_preflight,_call,_receipt

ROOT=Path("acolad_human_story_v5_output")
INTENTS=ROOT/"v5_publication_intents.json"
RECEIPTS=ROOT/"v5_publication_receipts.json"
CAMPAIGN="acolad-v5-baymard-returns-20261108"
DATE="2026-11-08"
EXPECTED_PREVIEW_RUN="PLACEHOLDER_MUST_BE_PINNED"

def _read(path):
    return json.loads(path.read_text(encoding="utf8"))

def _write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf8")

def _today():
    return datetime.now(ZoneInfo("Asia/Tehran")).date()

def validate_immutable_preview():
    if _today().isoformat()!=DATE:raise RuntimeError("V5_DAY_EXPIRED_NO_PUBLICATION")
    status=_read(ROOT/"preview_status.json")
    if (status.get("state")!="V5_PREVIEW_ONLY_NOT_PUBLISHED"
         or status.get("frames")!=9 or
         status.get("real_gpt25_transparent_art_assets")!=2
         or status.get("social_mutations")!=0
         or status.get("pixel_freeze_verified") is not True
         or status.get("colored_highlights") is not True):
        raise RuntimeError("V5_PREVIEW_NOT_APPROVED")
    critics=_read(ROOT/"critics.json")
    if len(critics)!=2 or any(type(c.get("score")) is not int or
         c["score"]<85 or c.get("veto") is not False for c in critics):
        raise RuntimeError("V5_INDEPENDENT_CRITIC_VETO")
    story=_read(ROOT/"story.json")
    issues=validate(story,story.get("sources") or [])
    if issues:raise RuntimeError("V5_UNVERIFIED_STORY:"+",".join(issues[:5]))
    if story.get("genre")!="مرور پژوهش + روایت فرضی، نه خبر امروز":
        raise RuntimeError("OLD_RESEARCH_MISLABELED_AS_BREAKING")
    manifest=_read(ROOT/"image_provenance.json")
    if (manifest.get("model")!="gpt-image-2.5-flare" or
        manifest.get("real_ai_generated") is not True or
        manifest.get("procedural_assets")!=0 or
        manifest.get("stock_assets")!=0 or len(manifest.get("records") or [])!=2):
        raise RuntimeError("V5_GENUINE_GPT_IMAGE_ASSETS_MISSING")
    for row in manifest["records"]:
        if row.get("real_ai_generated") is not True or row.get("background")!="transparent":
            raise RuntimeError("V5_ART_ASSET_UNVERIFIED")
        file=Path("acolad_concept_assets")/str(row.get("path") or "")
        if not file.is_file():raise RuntimeError("V5_ORIGINAL_ART_NOT_IN_ARTIFACT")
        picture,stats=verify_png(file.read_bytes())
        picture.close()
        if stats["transparent_fraction"]<.12:raise RuntimeError("V5_GPT_ALPHA_TOO_SMALL")
    cover=ROOT/"social_cover_square.png"
    with Image.open(cover) as im:
        if im.size!=(1080,1080) or im.format!="PNG":
            raise RuntimeError("V5_FIRST_IMAGE_MUST_BE_SQUARE_INDEPENDENT")
        im.verify()
    frames=sorted((ROOT/"stories").glob("story_*.png"))
    if len(frames)!=9:raise RuntimeError("V5_INSTAGRAM_NINE_FRAME_STORY_MISSING")
    for frame in frames:
        with Image.open(frame) as img:
            if img.format!="PNG" or img.size!=(1080,1920):
                raise RuntimeError("V5_INSTAGRAM_FRAME_MALFORMED")
            img.verify()
    first=thread_parts(story,"telegram")
    if len(first[0])>985:raise RuntimeError("TELEGRAM_PHOTO_CAPTION_TOO_LONG")
    return story,cover,frames

def _fresh_intents():
    if INTENTS.exists():
        raw=_read(INTENTS)
        if raw.get("campaign")!=CAMPAIGN:
            raise RuntimeError("V5_PUBLICATION_INTENT_MISMATCH")
        return raw
    return {"campaign":CAMPAIGN,"network":{}}

def _save_intent(network,step,**data):
    raw=_fresh_intents()
    raw["network"][network]={"step":step,**data}
    _write(INTENTS,raw)

def _attempted(network):
    return network in _fresh_intents()["network"]

def _save_receipt(network,status,**data):
    raw=_read(RECEIPTS) if RECEIPTS.exists() else {"campaign":CAMPAIGN,"network":{}}
    raw["network"][network]={"status":status,**data}
    _write(RECEIPTS,raw)
    print("ACOLAD_V5_NETWORK_RECEIPT "+json.dumps({
        "network":network,"status":status,
        "message_ids":data.get("message_ids"),"provider_ids":data.get("provider_ids"),
        "publication_verified":data.get("publication_verified",False),
    },ensure_ascii=False),flush=True)

def _provider_seen_story(key,network):
    """Visible same-story captions block repeats; old Nov8 different topic allowed."""
    rows=provider_list(key,network,_today())
    for group in rows:
        if not isinstance(group,dict):raise RuntimeError("UNSAFE_PROVIDER_POST_SHAPE")
        elements=[group]
        posts=group.get("post") or group.get("posts") or []
        if isinstance(posts,dict):posts=[posts]
        elements.extend(x for x in posts if isinstance(x,dict))
        for row in elements:
            caption=str(row.get("caption") or row.get("text") or "")
            if "مرجوعی" in caption and "محمد" in caption and "بایمرد" in caption:
                return True
    return False

def _native_three_parts(network,story,cover):
    secret="BALE_BOT_TOKEN" if network=="bale" else "BOT_TOKEN"
    if not os.getenv(secret,"").strip():
        raise RuntimeError("NATIVE_BOT_SECRET_MISSING_"+network)
    bot,channel=credentials(network)
    access_preflight(network,bot,channel)
    pieces=thread_parts(story,network)
    _save_intent(network,"SEND_PHOTO_UNKNOWN")
    message_ids=[]
    try:
        root=_call(network,bot,"sendPhoto",data={"chat_id":channel,"caption":pieces[0]},
                   media=cover)
        mid=_receipt(root);message_ids.append(mid)
        _save_intent(network,"ROOT_SENT_PARTIAL",message_ids=message_ids)
        _save_receipt(network,"PARTIAL_NATIVE_ROOT",message_ids=message_ids)
        for part in pieces[1:]:
            result=_call(network,bot,"sendMessage",data={
                "chat_id":channel,"text":part,"reply_to_message_id":mid,
                "disable_web_page_preview":True})
            new_id=_receipt(result)
            reply=result.get("reply_to_message") or {}
            if isinstance(reply,dict) and reply.get("message_id") is not None:
                if int(reply["message_id"])!=mid:
                    raise RuntimeError("V5_REPLY_ROOT_INCORRECT")
            message_ids.append(new_id)
            _save_intent(network,"PARTIAL",message_ids=message_ids)
            _save_receipt(network,"PARTIAL_NATIVE_THREAD",message_ids=message_ids)
        _save_intent(network,"PUBLISHED",message_ids=message_ids)
        _save_receipt(network,"PUBLISHED",message_ids=message_ids,
                      publication_verified=True,root_message_id=mid)
    except Exception as error:
        _save_receipt(network,"AMBIGUOUS_OR_PARTIAL_NO_BLIND_RETRY",
                      message_ids=message_ids,reason=type(error).__name__)
        raise

def _bale_via_novinhub(key,story,cover):
    """Fallback when no Bale native token: 3 sequential posts, NOT replies."""
    parts=thread_parts(story,"bale")
    # Strictly distinguish provider acceptance from native message publication.
    _save_intent("bale","SEND_COVER_UNKNOWN")
    ids=[]
    try:
        media_id=upload_file(key,cover)
        for i,part in enumerate(parts):
            if i:time.sleep(7)
            group=send_now(key,"bale",part,[media_id] if i==0 else [])
            ids.append(group)
            _save_intent("bale","PARTIAL_PROVIDER_SUBMISSIONS",provider_ids=ids)
            _save_receipt("bale","SUBMITTED_NOT_PROVEN_PUBLISHED",
                          provider_ids=ids,publication_verified=False,
                          native_reply_to_first=False)
        _save_intent("bale","THREE_PROVIDER_GROUPS_ACCEPTED",provider_ids=ids)
    except ProviderValidationRejected:
        _save_intent("bale","REJECTED_400",provider_ids=ids)
        _save_receipt("bale","PROVIDER_REJECTED_NO_PUBLISHED_CLAIM",provider_ids=ids)
    except Exception as error:
        _save_receipt("bale","AMBIGUOUS_OR_PARTIAL_NO_BLIND_RETRY",
                      provider_ids=ids,reason=type(error).__name__)
        raise

def _instagram(key,story,frames):
    if _attempted("instagram"):return
    if _provider_seen_story(key,"instagram"):
        _save_receipt("instagram","SAME_STORY_EXISTS_BLOCK_DUPLICATE")
        return
    _save_intent("instagram","MEDIA_UPLOAD_NOT_POST")
    media=[upload_file(key,x) for x in frames]
    if len(media)!=9:raise RuntimeError("V5_INSTAGRAM_UPLOAD_INCOMPLETE")
    caption=("محمد توی این داستان یه شخصیت فرضیه، ولی سردرگمیِ مسیر مرجوعی "
       "در پژوهش تجربه کاربری بایمرد بررسی شده (۲۰۱۹). این ۹ اسلاید رو ورق بزن؛ "
       "بعد چهار راهکار رو روی فروشگاه خودت امتحان کن. ❤️‍🔥 🌱")
    _save_intent("instagram","SEND_STORY_UNKNOWN",media_count=len(media))
    try:
        group=send_now(key,"instagram",caption,media)
    except ProviderValidationRejected:
        _save_intent("instagram","REJECTED_CREATOR_OR_PROVIDER_400")
        _save_receipt("instagram","HTTP_400_NOT_PUBLISHED",
                      publication_verified=False)
        return
    _save_intent("instagram","ACCEPTED_UNVERIFIED",provider_ids=[group])
    _save_receipt("instagram","SUBMITTED_NOT_YET_VERIFIED",
                  provider_ids=[group],publication_verified=False)
    # Real GET may lag; never label queued/accepted as Published.
    time.sleep(10)
    rows=provider_list(key,"instagram",_today())
    for item in rows:
        if str(item.get("id"))!=str(group):continue
        ps=item.get("post") or []
        if isinstance(ps,dict):ps=[ps]
        for p in ps:
            if str(p.get("account_id"))!=str(ACCOUNT["instagram"]):continue
            remote=p.get("accountPost") or p.get("account_post") or {}
            if (str(p.get("status")).lower()=="published" and isinstance(remote,dict)
                  and remote.get("post_id")):
                _save_intent("instagram","PUBLISHED",provider_ids=[group],
                             remote_post_id=remote["post_id"])
                _save_receipt("instagram","PUBLISHED",provider_ids=[group],
                         remote_post_id=remote["post_id"],publication_verified=True)
                return

def release():
    story,cover,frames=validate_immutable_preview()
    key=token()
    # This campaign must never be sent twice even if the CI job is re-run.
    for network in ("instagram","telegram","bale"):
        if _attempted(network):
            print("V5_ALREADY_ATTEMPTED_SKIP_"+network,flush=True)
            continue
        if network=="instagram":
            try:_instagram(key,story,frames)
            except Exception as error:
                _save_receipt(network,"AMBIGUOUS_NO_BLIND_RETRY",
                              reason=type(error).__name__)
        elif _provider_seen_story(key,network):
            _save_receipt(network,"SAME_STORY_EXISTS_BLOCK_DUPLICATE")
        elif network=="telegram":
            try:_native_three_parts(network,story,cover)
            except Exception as error:
                print("V5_TELEGRAM_PUBLICATION_EXCEPTION",type(error).__name__,flush=True)
        else:
            try:
                if os.getenv("BALE_BOT_TOKEN","").strip():
                    _native_three_parts(network,story,cover)
                else:
                    _bale_via_novinhub(key,story,cover)
            except Exception as error:
                print("V5_BALE_PUBLICATION_EXCEPTION",type(error).__name__,flush=True)
    print("ACOLAD_V5_RELEASE_FINISHED_WITH_RECEIPTS_NOT_GREEN_CHECK",flush=True)
    return _read(RECEIPTS)

if __name__=="__main__":
    print(json.dumps(release(),ensure_ascii=False),flush=True)
