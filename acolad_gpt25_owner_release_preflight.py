#!/usr/bin/env python3
"""Owner-approved Nov 8 release guard, from authentic model-art preview ZIP only.

This file never publishes. It verifies artifact day, two critic scores,
source/caption integrity, actual RGBA art, final story, and nonduplicating
provider-ready footer conversion from pre-PR25 previews.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image

from acolad_gapgpt_transparent_art import verify_png
import acolad_v4_hourly_publish as publisher
import acolad_v4_daily_autopublish as engine

ART = Path("acolad_concept_assets")
PUB = Path("acolad_v4_daily_publication")
DAY = "2026-11-08"
OLD_FOOTER = (
 "🌐 [acolad.ir](https://acolad.ir/)\n"
 "📢 کانال تلگرام: [@acoladagency](https://t.me/acoladagency)\n"
 "ارتباط و مشاوره: [@acolad_agency](https://t.me/acolad_agency)"
)


def normalize_reviewed_channel_footer(text: str, network: str) -> str:
    if network not in ("bale", "telegram"):raise ValueError("NATIVE_FOOTER_REQUIRED")
    current=engine.footer_for(network)
    if text.endswith(current):
        return engine.clean_old_markup(text)
    if not text.endswith(OLD_FOOTER):
        raise RuntimeError("CANNOT_VALIDATE_ORIGINAL_REVIEWED_SOCIAL_FOOTER")
    reviewed_text=text[:-len(OLD_FOOTER)].rstrip()
    reviewed_text=engine.clean_old_markup(reviewed_text)
    if not reviewed_text.strip() or len(reviewed_text)>2000:
        raise RuntimeError("ORIGINAL_REVIEWED_BODY_INVALID")
    return reviewed_text+"\n\n"+current


def verify_owner_release_artifact(today=None):
    today = today or datetime.now(ZoneInfo("Asia/Tehran")).date()
    if today.isoformat() != DAY:
        raise RuntimeError("OWNER_RELEASE_ARTIFACT_DATE_EXPIRED")
    ready=json.loads((PUB/"hourly_ready.json").read_text(encoding="utf8"))
    story=json.loads((PUB/"story.json").read_text(encoding="utf8"))
    evidence=json.loads((PUB/"sources_private.json").read_text(encoding="utf8"))
    manifest=json.loads((PUB/"image_provenance.json").read_text(encoding="utf8"))
    if ready.get("day")!=DAY or ready.get("validated") is not True:
        raise RuntimeError("EDITORIAL_ARTIFACT_NOT_APPROVED_FOR_TODAY")
    critics=ready.get("critics") or []
    if len(critics)!=2 or any(x.get("veto") is not False or
            type(x.get("score")) is not int or x["score"]<85 for x in critics):
        raise RuntimeError("INDEPENDENT_EDITORIAL_CRITIC_VETO")
    if not isinstance(evidence,list) or not evidence:
        raise RuntimeError("PRIMARY_EVIDENCE_MISSING")
    publisher.check_verified_editorial(story,evidence)
    if (manifest.get("model")!="gpt-image-2.5-flare"
            or manifest.get("real_ai_generated") is not True
            or manifest.get("procedural_assets")!=0
            or manifest.get("stock_assets")!=0):
        raise RuntimeError("ORIGINAL_GPT_IMAGE_25_REQUIRED")
    records=manifest.get("records") or []
    if not 2<=len(records)<=10 or len(records)!=manifest.get("image_count"):
        raise RuntimeError("AI_ART_ASSET_COUNT_INVALID")
    seen=set()
    for row in records:
        if row.get("real_ai_generated") is not True or row.get("background")!="transparent":
            raise RuntimeError("ART_NOT_REAL_TRANSPARENT")
        name=row.get("path")
        if (not isinstance(name,str) or not name.startswith("scene_") or
            not name.endswith(".png") or "/" in name or name in seen):
            raise RuntimeError("ART_ASSET_PATH_INVALID")
        seen.add(name)
        path=ART/name
        image,stats=verify_png(path.read_bytes())
        image.close()
        if stats["transparent_fraction"]<0.12:
            raise RuntimeError("ART_ALPHA_AREA_INVALID")
    images=sorted((PUB/"frames").glob("story_*.png"))
    if len(images)!=len(story.get("slides") or []) or len(images)!=ready.get("nframes"):
        raise RuntimeError("FINAL_STORY_FRAMES_INCOMPLETE")
    for image in images:
        with Image.open(image) as im:
            if im.format!="PNG" or im.size!=(1080,1920):
                raise RuntimeError("BRANDED_FRAME_INVALID")
            im.verify()
    captions=ready.get("captions") or {}
    if set(captions)!=set(publisher.NETWORKS):
        raise RuntimeError("NATIVE_AND_INSTAGRAM_CAPTIONS_MISSING")
    for network in ("telegram","bale"):
        captions[network]=normalize_reviewed_channel_footer(captions[network],network)
    if len(captions["instagram"])<60:
        raise RuntimeError("INSTAGRAM_CAPTION_TOO_SHORT")
    ready["captions"]=captions
    publisher.READY.write_text(json.dumps(ready,ensure_ascii=False,indent=2),encoding="utf8")
    checked,_=publisher.existing_bundle(today)
    if checked["day"]!=DAY:raise RuntimeError("SAME_DAY_VERIFICATION_FAILED")
    result={"status":"PREVIEW_SOURCE_AND_REAL_AI_PASSED",
            "date_tehran":DAY,
            "model":manifest["model"],
            "original_rgba_assets":len(records),
            "frames":len(images),
            "critics":[x["score"] for x in critics],
            "network_captions":sorted(captions),
            "publication_requested":False,
            "social_posts_created":0}
    (PUB/"owner_release_preflight.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    print("ACOLAD_OWNER_APPROVED_ARTIFACT_PREFLIGHT "+
        json.dumps(result,ensure_ascii=False),flush=True)
    return result


if __name__=="__main__":
    verify_owner_release_artifact()
