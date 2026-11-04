#!/usr/bin/env python3
"""One isolated end-to-end STORY PREVIEW: retry Gemini once; if HTTP 503 use GPT Image 2 once.

NEVER sends to social networks, Buffer, NovinHub, or Cloudinary.
This script renders a complete local 8-frame Acolad story after image selection.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import requests

from acolad_gapgpt_gemini25_one_image import PROMPT, check_catalog, headers
from acolad_gapgpt_qwen_image_once import decode_image
from acolad_narrative_visual_v2 import render

GEMINI = "gemini-2.5-flash-image"
FALLBACK = "gpt-image-2"
BASE = "https://api.gapgpt.app/v1"
APPROVAL = "ACOLAD_ONE_GEMINI_THEN_GPT2_STORY_PREVIEW_APPROVED"
STORY = Path("examples/acolad_story_full_draft_20261104.json")
ART_DIR = Path("acolad_concept_assets")
OUTPUT = Path("acolad_gemini_gpt2_story_preview")
EXPECTED_FRAMES = 8
# Based on screenshot, not guaranteed final billing, subject to FX and provider fee.
ESTIMATED_GEMINI_USD = 0.04
MAX_BUDGET_USD = 0.08  # earlier rough 20,000 toman at 250,000 toman/USD

def safe_model_list(session,key):
    try:
        r=session.get(BASE+"/models",headers=headers(key),timeout=25)
        if r.status_code!=200: return None,{"status":"CATALOG_HTTP","http_status":r.status_code}
        models={x.get("id") for x in (r.json().get("data") or []) if isinstance(x,dict)}
        return models,{"status":"CATALOG_OK","model_count":len(models)}
    except (requests.RequestException,TypeError,ValueError) as e:
        return None,{"status":"CATALOG_ERROR_"+type(e).__name__}

def generate(session,key,model):
    payload={"model":model,"prompt":PROMPT,"size":"1024x1024"}
    try:
        r=session.post(BASE+"/images/generations",headers=headers(key),
                       json=payload,timeout=175)
        if r.status_code!=200:
            return None,{"model":model,"status":"HTTP_ERROR","http_status":r.status_code}
        pic,kind=decode_image(r.json(),session=session)
        return pic,{"model":model,"status":"IMAGE_VERIFIED",
                     "response_type":kind,"size":list(pic.size)}
    except (requests.RequestException,ValueError,TypeError,OSError,KeyError) as e:
        return None,{"model":model,"status":"INVALID_RESPONSE_"+type(e).__name__}

def make_story(data_path=STORY):
    story=json.loads(Path(data_path).read_text(encoding="utf-8"))
    frames=story.get("slides",[])
    if story.get("publication_permission")!="NONE_PREVIEW_ONLY" or len(frames)!=EXPECTED_FRAMES:
        raise ValueError("Must use the approved eight-slide local preview-only story")
    if any(f.get("source_ids") for f in frames):
        raise ValueError("This test story must be fully fictional and contain no research claims")
    return story

def run(session=requests,approval="",out=OUTPUT,story_path=STORY):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    story=make_story(story_path)
    report={"state":"LOCAL_DRAFT_PREVIEW_ONLY","requested_models":[GEMINI,FALLBACK],
            "image_requests":0,"published":0,"queued":0,"buffer_drafts":0,
            "cloudinary_uploads":0,"external_social_calls":0,
            "story_frames_planned":EXPECTED_FRAMES,
            "billing_verified":False,"hard_spend_cap_verified":False,
            "price_from_user_screenshot_usd_gemini":ESTIMATED_GEMINI_USD,
            "fallback_executed_only_after_gemini_http_503":False,
            "attempts":[],"human_review_required":True}
    key=os.environ.get("GAPGPT_API_KEY","").strip()
    allow=approval==APPROVAL and bool(key)
    models,cat=safe_model_list(session,key) if key else (None,{"status":"NO_GAPGPT_KEY"})
    report["preflight"]=cat
    image=None
    if not allow:
        report["image_status"]="APPROVAL_OR_SECRET_MISSING"
    elif not models or GEMINI not in models or FALLBACK not in models:
        report["image_status"]="CATALOG_MODEL_MISSING"
    else:
        # Exactly one Gemini request. Only HTTP 503 is permission to try GPT Image 2.
        image,details=generate(session,key,GEMINI)
        report["image_requests"]+=1
        report["attempts"].append(details)
        if image is None and details.get("status")=="HTTP_ERROR" and details.get("http_status")==503:
            report["fallback_executed_only_after_gemini_http_503"]=True
            image,other=generate(session,key,FALLBACK)
            report["image_requests"]+=1
            report["attempts"].append(other)
        report["image_status"]="IMAGE_VERIFIED" if image is not None else "NO_VALID_AI_IMAGE"
    if report["image_requests"]>2:
        raise RuntimeError("Maximum image requests violated")
    # Do not alter existing concept art or overwrite shared assets in any runner.
    target=ART_DIR/"scene_02.png"
    existing_bytes=target.read_bytes() if target.is_file() else None
    try:
        if image is not None:
            ART_DIR.mkdir(parents=True,exist_ok=True)
            image.save(target,format="PNG")
            image.save(out/"source_image.png",format="PNG")
            report["source_image"]="source_image.png"
            report["image_model"]=report["attempts"][-1]["model"]
        else:
            # A missing image must not be silently filled with stale artwork.
            if target.is_file():target.unlink()
        report["render"]=render(story,out/"frames",allow_stock=False)
        frames=sorted((out/"frames").glob("story_*.png"))
        if len(frames)!=EXPECTED_FRAMES:
            raise RuntimeError("Wrong frame count after rendering")
        report["rendered_frames"]=len(frames)
        report["status"]="COMPLETE_STORY_DRAFT_PREVIEW"
    finally:
        if existing_bytes is not None:
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(existing_bytes)
        elif target.is_file():
            target.unlink()
        (out/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (out/"story.json").write_text(json.dumps(story,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ACOLAD_STORY_IMAGE_QA "+json.dumps(report,ensure_ascii=False),flush=True)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--approval",default="")
    p.add_argument("--output",default=str(OUTPUT))
    a=p.parse_args()
    result=run(approval=a.approval,out=a.output)
    return 0 if result.get("status")=="COMPLETE_STORY_DRAFT_PREVIEW" else 2

if __name__=="__main__":
    raise SystemExit(main())
