#!/usr/bin/env python3
"""Date-locked Instagram-only NovinHub retry; never resends Telegram/Bale.

This requires an existing vetted story with real GPT Image 2.5 transparent
cutouts. Provider HTTP 400 Creator is an explicit refusal, so one repeat per
scheduled hour is safe. Any HTTP timeout or accepted group is NOT retried
blindly. Per-run intent cache is restored by the GitHub Actions workflow.
"""
from __future__ import annotations
import json,time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from acolad_gpt25_owner_release_preflight import verify_owner_release_artifact
from acolad_v4_hourly_publish import (provider_list,assess,send_now,ACCOUNT,
                                      ProviderValidationRejected)
from acolad_novinhub_bridge import upload_file, token

ROOT=Path("acolad_v4_daily_publication")
INTENT=ROOT/"instagram_nov8_retry_intent.json"
STATUS=ROOT/"instagram_nov8_retry_status.json"
DAY="2026-11-08"


def report(state,**detail):
    ROOT.mkdir(parents=True,exist_ok=True)
    obj={"day":DAY,"network":"instagram","status":state,"publication_verified":False,
         "other_social_networks_mutated":0,**detail}
    STATUS.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("ACOLAD_NOV8_INSTAGRAM_RECOVERY "+json.dumps(obj,ensure_ascii=False),flush=True)
    return obj


def run():
    today=datetime.now(ZoneInfo("Asia/Tehran")).date()
    if today.isoformat()!=DAY:
        return report("DATE_EXPIRED_NO_REQUEST")
    verify_owner_release_artifact(today)
    key=token()
    posts=provider_list(key,"instagram",today)
    current=assess(posts,"instagram")
    if current["state"]=="PUBLISHED":
        return report("INSTAGRAM_PUBLISHED_VERIFIED",provider_state=current,
                      publication_verified=True)
    if current["state"]!="ABSENT":
        return report("WAITING_UNAMBIGUOUS_PROVIDER_RECEIPT_NO_DUPLICATE",
                      provider_state=current)
    if INTENT.exists():
        previous=json.loads(INTENT.read_text(encoding="utf8"))
        if previous.get("day")==DAY and previous.get("state") in (
            "SENDING_WITH_UNKNOWN_PROVIDER_RECEIPT","ACCEPTED"):
            return report("AMBIGUOUS_OR_ACCEPTED_PREVIOUS_SEND_NO_BLIND_RETRY")
    frames=sorted((ROOT/"frames").glob("story_*.png"))
    ready=json.loads((ROOT/"hourly_ready.json").read_text(encoding="utf8"))
    if len(frames)!=ready.get("nframes") or len(frames)<6:
        raise RuntimeError("REAL_STORY_FRAMES_MISSING")
    # Uploading media alone does not create a social story. Capture intent
    # before irreversible POST; never repeat a possibly accepted mutation.
    media=[upload_file(key,path) for path in frames]
    if len(media)!=len(frames):raise RuntimeError("NOVINHUB_MEDIA_UPLOAD_INCOMPLETE")
    ROOT.mkdir(parents=True,exist_ok=True)
    def save(state,group_id=None):
        payload={"day":DAY,"state":state,"account_id":ACCOUNT["instagram"],
                 "group_id":group_id,"media_count":len(media)}
        INTENT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",
                          encoding="utf8")
    save("SENDING_WITH_UNKNOWN_PROVIDER_RECEIPT")
    try:
        group_id=send_now(key,"instagram",ready["captions"]["instagram"],media)
    except ProviderValidationRejected:
        # Documented NovinHub HTTP400 creates NO post group. Safe to retry
        # next hourly check once the account reconnects as Business.
        save("REJECTED_VALIDATION_400")
        return report("CREATOR_ACCOUNT_REJECTED_CONNECT_INSTAGRAM_BUSINESS",
                      http=400,provider_group_created=False)
    save("ACCEPTED",group_id)
    time.sleep(10)
    state=assess(provider_list(key,"instagram",today),"instagram")
    if state["state"]=="PUBLISHED":
        save("PUBLISHED",group_id)
        return report("INSTAGRAM_PUBLISHED_VERIFIED",provider_state=state,
                      group_id=group_id,publication_verified=True)
    return report("INSTAGRAM_SUBMITTED_NOT_YET_PROVEN_PUBLISHED",
                  group_id=group_id,provider_state=state)


if __name__=="__main__":
    r=run()
    raise SystemExit(0 if r.get("publication_verified") or r["status"] in (
        "DATE_EXPIRED_NO_REQUEST","WAITING_UNAMBIGUOUS_PROVIDER_RECEIPT_NO_DUPLICATE",
        "AMBIGUOUS_OR_ACCEPTED_PREVIOUS_SEND_NO_BLIND_RETRY") else 2)
