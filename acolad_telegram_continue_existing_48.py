#!/usr/bin/env python3
"""Add owner-authorized source-locked replies to existing Nov8 Telegram image #48.

No new root photo, no new NovinHub post, and no Bale/Instagram mutations.
Fail closed on any ambiguous send; preserve each real Telegram Bot API receipt.
"""
from __future__ import annotations
import json, os, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from acolad_native_story_threads import credentials, access_preflight, _call, _receipt, segments
from acolad_gpt25_owner_release_preflight import verify_owner_release_artifact
from acolad_v4_hourly_publish import provider_list, ACCOUNT
from acolad_novinhub_bridge import token

DATE = "2026-11-08"
ROOT_ID = 48
POST_GROUP = 3699384
OUT = Path("acolad_v4_daily_publication")
RECEIPT = OUT/"telegram_replies_to_48.json"


def verify_root_from_provider(key: str,day):
    rows=provider_list(key,"telegram",day)
    for group in rows:
        if str(group.get("id"))!=str(POST_GROUP):continue
        details=group.get("post") or []
        if isinstance(details,dict):details=[details]
        for p in details:
            if str(p.get("account_id"))!=str(ACCOUNT["telegram"]):continue
            remote=p.get("accountPost") or p.get("account_post") or {}
            if not isinstance(remote,dict):continue
            if (str(p.get("status")).lower()=="published" and
                str(remote.get("post_id"))==str(ROOT_ID) and
                remote.get("permalink")=="https://t.me/acoladagency/48"):
                return True
    raise RuntimeError("TELEGRAM_ROOT_48_NOT_PROVIDER_VERIFIED")


def continue_verified_telegram():
    now=datetime.now(ZoneInfo("Asia/Tehran")).date()
    if now.isoformat()!=DATE:raise RuntimeError("TELEGRAM_NOV8_THREAD_DATE_EXPIRED")
    if RECEIPT.exists():
        raise RuntimeError("TELEGRAM_THREAD_SEND_ALREADY_ATTEMPTED_NEVER_BLIND_RETRY")
    verify_owner_release_artifact(now)
    story=json.loads((OUT/"story.json").read_text(encoding="utf8"))
    pieces=segments(story,"telegram")
    if len(pieces)!=3:raise RuntimeError("EXPECTED_THREE_EDITORIAL_SEGMENTS")
    if not verify_root_from_provider(token(),now):
        raise RuntimeError("TELEGRAM_FIRST_PHOTO_NOT_PUBLISHED")
    bot,channel=credentials("telegram")
    access_preflight("telegram",bot,channel)
    OUT.mkdir(parents=True,exist_ok=True)
    status={"day":DATE,"network":"telegram","root_message_id":ROOT_ID,
            "verified_root_link":"https://t.me/acoladagency/48",
            "message_ids":[],"state":"SENDING_UNKNOWN","published":False}
    def save():
        RECEIPT.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",
                           encoding="utf8")
    save()
    for part in pieces[1:]:
        result=_call("telegram",bot,"sendMessage",data={
            "chat_id":channel, "text":part,
            "reply_to_message_id":ROOT_ID,
            "disable_web_page_preview":True})
        mid=_receipt(result)
        returned_reply=result.get("reply_to_message") or {}
        if isinstance(returned_reply,dict) and returned_reply.get("message_id") is not None:
            if str(returned_reply.get("message_id"))!=str(ROOT_ID):
                raise RuntimeError("REMOTE_REPLY_REFERENCES_WRONG_ROOT")
        status["message_ids"].append(mid)
        status["state"]="PARTIAL_PUBLISHED" if len(status["message_ids"])==1 else "PUBLISHED"
        save()
        if len(status["message_ids"])==1:
            time.sleep(2)
    status["published"]=True
    status["state"]="PUBLISHED"
    save()
    print("ACOLAD_TELEGRAM_REPLY_THREAD_REAL "+json.dumps({
        "day":DATE,"root_message_id":ROOT_ID,"root_link":status["verified_root_link"],
        "reply_message_ids":status["message_ids"],"status":"PUBLISHED",
        "procedural_art":0,"new_root_posts":0},ensure_ascii=False),flush=True)
    return status

if __name__=="__main__":
    continue_verified_telegram()
