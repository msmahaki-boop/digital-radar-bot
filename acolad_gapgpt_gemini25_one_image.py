#!/usr/bin/env python3
"""Isolated GapGPT gemini-2.5-flash-image one-call comparison. NO social publish.

Uses the authorized GapGPT secret. No implicit retries. Output is for visual QA.
API price in the owner's screenshot: $0.040 per use; provider bill not verified.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import requests
from acolad_gapgpt_qwen_image_once import decode_image, _json_report

BASE = "https://api.gapgpt.app/v1"
MODEL = "gemini-2.5-flash-image"
APPROVAL = "GEMINI25_ONE_IMAGE_PREVIEW_APPROVED"
OUTPUT = Path("acolad_gemini25_image_preview")
SCREENSHOT_ESTIMATE_USD = 0.04
PRIOR_SOFT_LIMIT_USD = 0.08

# Intentionally very little imagery. No copy of a named illustrator.
PROMPT = (
    "A SINGLE original minimalist literary editorial ink drawing: "
    "a tiny expressive small-business owner stands beside one enormous "
    "shopping cart whose front wheel has fallen off; the person holds "
    "the wheel like a question mark, amused by a simple fix to a difficult "
    "customer checkout problem. One visual joke and one clear focal point. "
    "Thin yet confident imperfect freehand black pen contours, whimsical "
    "gentle humor, hand-drawn storybook character, unusually inventive scale, "
    "warm ivory plain paper. One tiny muted purple accent, maximum 5 percent "
    "of the image. At least 75 percent untouched empty background. "
    "Only the character, cart and wheel. NO phone, website UI, dashboard, "
    "computers, screens, buildings, products, crowds, writing, lettering, "
    "numbers, watermark, logos, frame, gradients, shading, hatch marks, "
    "texture, clutter, photorealism, glossy 3D or colorful decoration. "
    "An entirely original art direction; do not copy or imitate any "
    "named artist or specific published illustration. "
    "A conceptual scene from a FICTIONAL online-shop story, NOT an actual news photo."
)

def headers(key):
    return {"Authorization":"Bearer "+key,"Content-Type":"application/json",
            "Accept":"application/json"}

def check_catalog(session,key):
    if not key:
        return {"status":"MISSING_SECRET"}
    try:
        r=session.get(BASE+"/models",headers=headers(key),timeout=25)
        if r.status_code!=200:
            return {"status":"CATALOG_HTTP_ERROR","http_status":r.status_code}
        data=r.json()
        ids={row.get("id") for row in data.get("data",[])
             if isinstance(row,dict) and isinstance(row.get("id"),str)}
        return {"status":"CATALOG_OK","model_present":MODEL in ids,
                "model_count":len(ids)}
    except (requests.RequestException,ValueError,TypeError) as e:
        return {"status":"CATALOG_ERROR_"+type(e).__name__}

def generate(session,key):
    payload={"model":MODEL,"prompt":PROMPT,"size":"1024x1024"}
    try:
        r=session.post(BASE+"/images/generations",json=payload,
                       headers=headers(key),timeout=170)
        if r.status_code!=200:
            return None,{"status":"IMAGE_HTTP_ERROR","http_status":r.status_code}
        picture,kind=decode_image(r.json(),session=session)
        return picture,{"status":"IMAGE_VERIFIED","response_type":kind,"dimensions":list(picture.size)}
    except (requests.RequestException,ValueError,TypeError,OSError) as e:
        return None,{"status":"IMAGE_INVALID_"+type(e).__name__}

def run(mode,approval="",output=OUTPUT,session=requests):
    path=Path(output)
    report={"mode":mode,"provider":"GapGPT","model":MODEL,
            "state":"PREVIEW_ONLY","external_generation_requests":0,
            "published":0,"queued":0,"drafts":0,"social_uploads":0,
            "auto_retry":False,"owner_screenshot_price_usd_per_use":SCREENSHOT_ESTIMATE_USD,
            "actual_billing_verified":False,"budget_hard_cap_verified":False}
    key=os.getenv("GAPGPT_API_KEY","").strip()
    catalog=check_catalog(session,key)
    report["catalog"]=catalog
    if mode=="preflight":
        report["status"]="PREFLIGHT_DONE"
    elif mode!="generate":
        report["status"]="INVALID_MODE"
    elif approval!=APPROVAL:
        report["status"]="APPROVAL_REQUIRED"
    elif SCREENSHOT_ESTIMATE_USD>PRIOR_SOFT_LIMIT_USD:
        report["status"]="PRICE_ABOVE_PREVIOUS_ESTIMATE_LIMIT"
    elif catalog.get("status")!="CATALOG_OK" or not catalog.get("model_present"):
        report["status"]="MODEL_NOT_AVAILABLE_NO_CHARGE"
    else:
        report["external_generation_requests"]=1
        picture,details=generate(session,key)
        report["image_result"]=details
        report["status"]=details["status"]
        if picture is not None:
            path.mkdir(parents=True,exist_ok=True)
            picture.save(path/"gemini25_comparison.png",format="PNG")
            report["file"]="gemini25_comparison.png"
            report["manual_editorial_and_visual_review_required"]=True
    _json_report(path,report)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("preflight","generate"),default="preflight")
    p.add_argument("--approval",default="")
    p.add_argument("--output",default=str(OUTPUT))
    a=p.parse_args()
    result=run(a.mode,a.approval,a.output)
    print("GEMINI25_GAPGPT_REPORT "+json.dumps(result,ensure_ascii=False))
    return 0 if result["status"] in ("PREFLIGHT_DONE","IMAGE_VERIFIED") else 2

if __name__=="__main__":
    raise SystemExit(main())
