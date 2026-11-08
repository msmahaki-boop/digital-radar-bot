#!/usr/bin/env python3
"""Acolad Telegram / Bale multi-message first-photo + replies publisher.

Never uses the NovinHub /post endpoint for fake threading: native Bot APIs
are required for a verifiable first message ID and reply_to_message_id.
Call only after source, critic, original AI artwork and same-day preflight.
"""
from __future__ import annotations
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import requests
from PIL import Image
from acolad_v4_daily_autopublish import clean_old_markup, footer_for

ENDPOINTS={"telegram":"https://api.telegram.org/bot",
           "bale":"https://tapi.bale.ai/bot"}
CREDENTIALS={"telegram":("BOT_TOKEN","TELEGRAM_CHANNEL_ID"),
             "bale":("BALE_BOT_TOKEN","BALE_CHANNEL_ID")}
DEFAULT_CHANNEL={"bale":"@acoladagency"}
ROOT=Path("acolad_v4_daily_publication")


def credentials(network:str, environ=os.environ):
    if network not in ENDPOINTS:
        raise ValueError("UNKNOWN_NATIVE_NETWORK")
    secret,variable=CREDENTIALS[network]
    bot=environ.get(secret,"").strip()
    channel=environ.get(variable,"").strip() or DEFAULT_CHANNEL.get(network,"")
    if not bot or not channel:
        raise RuntimeError("NATIVE_BOT_SECRET_OR_CHANNEL_MISSING_"+network)
    return bot,channel


def segments(story:dict,network:str)->list[str]:
    slides=story.get("slides")
    if not isinstance(slides,list) or not 6<=len(slides)<=15:
        raise RuntimeError("NATIVE_THREAD_SLIDES_INCOMPLETE")
    if any(x.get("n")!=i+1 or not isinstance(x.get("text"),str)
           or not x["text"].strip() for i,x in enumerate(slides)):
        raise RuntimeError("NATIVE_THREAD_NON_VERIFIED_SLIDE")
    n=len(slides)
    boundaries=(0,n//3,(2*n)//3,n)
    outputs=[]
    for part in range(3):
        texts=[clean_old_markup(x["text"]).strip() for x in slides[boundaries[part]:boundaries[part+1]]]
        content="\n\n".join(texts)
        title=f"روایت آکولاد | {part+1} از ۳\n"
        if part==2:
            content+="\n\n"+footer_for(network)
        result=title+content
        limit=1000 if part==0 else 3900
        if len(result)>limit:raise RuntimeError("NATIVE_THREAD_PART_TOO_LONG")
        outputs.append(result)
    return outputs


def _call(network:str,bot:str,method:str,*,data:dict,media:Path|None=None,
          session=requests)->dict:
    if network not in ENDPOINTS:raise ValueError("UNRECOGNIZED_NETWORK")
    endpoint=ENDPOINTS[network]+bot+"/"+method
    if media is not None:
        with media.open("rb") as stream:
            response=session.post(endpoint,data=data,
                                  files={"photo":(media.name,stream,"image/png")},timeout=100)
    else:
        response=session.post(endpoint,json=data,timeout=65)
    if response.status_code != 200:
        raise RuntimeError("NATIVE_"+network+"_"+method+"_HTTP_"+str(response.status_code))
    try:payload=response.json()
    except ValueError as e:raise RuntimeError("NATIVE_API_INVALID_JSON") from e
    if payload.get("ok") is not True or not isinstance(payload.get("result"),dict):
        raise RuntimeError("NATIVE_API_UNVERIFIED_RESPONSE_"+network)
    return payload["result"]


def _receipt(result:dict)->int:
    mid=result.get("message_id")
    if not isinstance(mid,int) or mid<=0:
        raise RuntimeError("NATIVE_API_MESSAGE_ID_MISSING")
    return mid


def validate_cover(path:Path):
    if not path.exists():raise RuntimeError("COVER_IMAGE_MISSING")
    with Image.open(path) as image:
        if image.format!="PNG" or image.size!=(1080,1920):
            raise RuntimeError("COVER_NOT_VERIFIED_BRANDED_STORY")
        image.verify()


def access_preflight(network:str,bot:str,channel:str,session=requests):
    me=_call(network,bot,"getMe",data={},session=session)
    bot_id=me.get("id")
    if not isinstance(bot_id,int) or bot_id<=0:raise RuntimeError("NATIVE_BOT_ID_UNKNOWN")
    info=_call(network,bot,"getChat",data={"chat_id":channel},session=session)
    if info.get("type")!="channel":
        raise RuntimeError("NOT_A_PUBLISHING_CHANNEL_"+network)
    permissions=_call(network,bot,"getChatMember",
        data={"chat_id":channel,"user_id":bot_id},session=session)
    if permissions.get("status") not in ("administrator","creator"):
        raise RuntimeError("NATIVE_BOT_NOT_CHANNEL_ADMIN_"+network)
    if permissions.get("can_post_messages") is False:
        raise RuntimeError("NATIVE_BOT_CANNOT_POST_"+network)
    return True


def publish_thread(network:str,story:dict,cover:Path,day:date,
                   *, state_dir:Path=ROOT,session=requests)->dict:
    """No automatic retries after an ambiguous send; preserve every receipt locally."""
    if os.getenv("ACOLAD_TEST_CLOCK")!="1":
        # Compare against Tehran date, not runner's potentially different UTC date.
        from datetime import datetime
        from zoneinfo import ZoneInfo
        if day != datetime.now(ZoneInfo("Asia/Tehran")).date():
            raise RuntimeError("NATIVE_STORY_DAY_IS_STALE")
    validate_cover(cover)
    parts=segments(story,network)
    bot,channel=credentials(network)
    state_dir.mkdir(parents=True,exist_ok=True)
    record=state_dir/("native_"+network+"_receipt.json")
    if record.exists():
        raise RuntimeError("NATIVE_PUBLISH_ALREADY_ATTEMPTED_CHECK_RECEIPT")
    access_preflight(network,bot,channel,session=session)
    state={"network":network,"day":day.isoformat(),"state":"SENDING_UNKNOWN",
           "message_ids":[],"publication_verified":False}
    def save():
        record.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf8")
    save()
    first=_call(network,bot,"sendPhoto",data={"chat_id":channel,"caption":parts[0]},
                media=cover,session=session)
    first_id=_receipt(first)
    state["message_ids"].append(first_id)
    state["state"]="FIRST_PHOTO_PUBLISHED_CONTINUATIONS_PENDING"
    save()
    for text in parts[1:]:
        message=_call(network,bot,"sendMessage",data={
            "chat_id":channel,"text":text,"reply_to_message_id":first_id},
            session=session)
        state["message_ids"].append(_receipt(message))
        save()
    state["state"]="PUBLISHED"
    state["publication_verified"]=True
    state["root_message_id"]=first_id
    save()
    return state
