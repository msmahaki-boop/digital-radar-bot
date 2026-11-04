#!/usr/bin/env python3
"""Acolad GapGPT Qwen image one-off QA. NO social/Buffer/NovinHub access.
Modes: preflight = GET /models only; generate = at most ONE billable POST.
Response supports GapGPT data[0].url as shown in provider's documentation and b64_json.
"""
from __future__ import annotations
import argparse
import base64
import io
import ipaddress
import json
import os
from pathlib import Path
import socket
from urllib.parse import urlparse

import requests
from PIL import Image

BASE="https://api.gapgpt.app/v1"
MODEL="gapgpt/qwen-image-2.1"
APPROVAL="GAPGPT_QWEN_ONE_IMAGE_20000_TOMAN_APPROVED"
MAX_BYTES=16_000_000
OUT=Path("acolad_gapgpt_qwen_preview")
PROMPT=(
    "Make ONE original, expressive black pen-and-ink editorial illustration "
    "for a fictional Persian small-business digital marketing story. "
    "SCENE: A tiny cheerful online shopkeeper stands next to a comically giant "
    "shopping cart with a missing wheel. Lots of customers are walking right past "
    "the cart and do not notice a small CLOSED trapdoor hiding the available payment "
    "options below the product page. The shopkeeper holds up a magnifying glass "
    "and discovers the trapdoor: an intelligent, clear visual metaphor for checkout "
    "friction and an opportunity to test how payment options are displayed. "
    "Draw a charming expressive face and witty visual storytelling, original "
    "freehand slightly wobbly black ink linework, sparse hand-hatching, light "
    "warm cream paper #F5F2EB, and a single tiny lavender accent #9D4EDD. "
    "Vary scale dramatically: one small human and one oversized physical metaphor. "
    "Simple bold silhouettes, airy negative space, not a wireframe, not photorealism. "
    "Do not copy any known existing cartoonist or illustration. "
    "No captions, letters, logos, percentages, fake interface text, watermark, "
    "screenshots, borders, photographs or gradient backgrounds. "
    "Square master image, centered, intended for a vertical Instagram story design. "
    "This is a conceptual FICTIONAL scene, not photographic documentation of news."
)

def _json_report(out, report):
    out.mkdir(parents=True,exist_ok=True)
    (out/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def _headers(key):
    return {"Authorization":"Bearer "+key,"Accept":"application/json"}

def _safe_status(resp):
    return int(getattr(resp,"status_code",0))

def preflight(key, session=requests):
    if not key:
        return {"status":"MISSING_GAPGPT_API_KEY","catalog_checked":False}
    try:
        r=session.get(BASE+"/models",headers=_headers(key),timeout=25)
        if r.status_code != 200:
            return {"status":"MODEL_LIST_HTTP_ERROR","http_status":_safe_status(r)}
        obj=r.json()
        names={x.get("id") for x in obj.get("data",[]) if isinstance(x,dict)} if isinstance(obj,dict) else set()
        return {"status":"MODEL_LIST_OK","model_present":MODEL in names,
                "listed_image_models":sorted(x for x in names if isinstance(x,str) and ("image" in x or "flux" in x))[:30],
                "model_count":len(names)}
    except (requests.RequestException,ValueError,TypeError) as exc:
        return {"status":"PREFLIGHT_ERROR_"+type(exc).__name__}

def _image_from_bytes(raw):
    if len(raw)>MAX_BYTES:raise ValueError("image exceeds max size")
    with Image.open(io.BytesIO(raw)) as image:
        if image.format not in ("PNG","JPEG","WEBP"):raise ValueError("unexpected image format")
        image.verify()
    with Image.open(io.BytesIO(raw)) as image:
        if min(image.size)<512 or max(image.size)>4096:raise ValueError("unexpected image dimensions")
        return image.convert("RGBA").copy()

def _safe_image_url(url):
    p=urlparse(url)
    if p.scheme!="https" or not p.hostname or p.username or p.password:raise ValueError("invalid image URL")
    name=p.hostname.lower().rstrip(".")
    if name in ("localhost","metadata.google.internal") or name.endswith((".localhost",".local",".internal")):
        raise ValueError("forbidden image URL")
    try:
        addr=ipaddress.ip_address(name)
        if not addr.is_global:raise ValueError("private image URL")
    except ValueError as e:
        if str(e)=="private image URL":raise
    return url

def decode_image(obj,session=requests):
    data=obj.get("data") if isinstance(obj,dict) else None
    if not isinstance(data,list) or not data or not isinstance(data[0],dict):
        raise ValueError("missing data[0]")
    image=data[0]
    b64=image.get("b64_json")
    if isinstance(b64,str) and b64:
        return _image_from_bytes(base64.b64decode(b64,validate=True)),"b64_json"
    url=image.get("url")
    if not isinstance(url,str):raise ValueError("missing image url/base64")
    _safe_image_url(url)
    response=session.get(url,timeout=65,allow_redirects=False)
    if response.status_code!=200:raise ValueError("image download HTTP error")
    raw=response.content
    return _image_from_bytes(raw),"url"

def generate_once(key, session=requests):
    payload={"model":MODEL,"prompt":PROMPT,"size":"1024x1024"}
    r=session.post(BASE+"/images/generations",headers={**_headers(key),"Content-Type":"application/json"},
        json=payload,timeout=160)
    if r.status_code!=200:
        return None,{"status":"GENERATE_HTTP_ERROR","http_status":_safe_status(r)}
    try:
        image,kind=decode_image(r.json(),session)
    except (ValueError,requests.RequestException,OSError,KeyError,TypeError) as exc:
        return None,{"status":"RESPONSE_IMAGE_INVALID_"+type(exc).__name__}
    return image,{"status":"IMAGE_VERIFIED","response_type":kind,"size":list(image.size)}

def run(mode,approval="",output=OUT,session=requests):
    out=Path(output)
    report={"mode":mode,"model":MODEL,"state":"PREVIEW_ONLY",
            "provider":"GapGPT","posted_requests":0,"published":0,
            "drafts":0,"queued":0,"uploaded":0,
            "estimated_provider_price_usd_per_use_from_user_screenshot":0.005,
            "actual_price_and_fx_not_verified":True,
            "budget_toman_authorized":20000,
            "no_auto_retry":True}
    key=os.environ.get("GAPGPT_API_KEY","").strip()
    probe=preflight(key,session)
    report["preflight"]=probe
    if mode=="preflight":
        report["status"]="PREFLIGHT_DONE"
    elif mode!="generate":
        report["status"]="INVALID_MODE"
    elif approval!=APPROVAL:
        report["status"]="APPROVAL_REQUIRED"
    elif probe.get("status")!="MODEL_LIST_OK" or not probe.get("model_present"):
        report["status"]="MODEL_NOT_VERIFIED_STOP_BEFORE_SPEND"
    else:
        report["posted_requests"]=1
        try:
            image,status=generate_once(key,session)
            report["image"]=status
            report["status"]=status["status"]
            if image is not None:
                out.mkdir(parents=True,exist_ok=True)
                image.save(out/"one_original_concept.png")
                report["image_file"]="one_original_concept.png"
                report["human_art_review_required"]=True
        except (requests.RequestException,ValueError,OSError) as exc:
            report["status"]="PROVIDER_ERROR_"+type(exc).__name__
    _json_report(out,report)
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=("preflight","generate"),default="preflight")
    ap.add_argument("--approval",default="")
    ap.add_argument("--output",default=str(OUT))
    a=ap.parse_args()
    result=run(a.mode,a.approval,a.output)
    print("GAPGPT_IMAGE_REPORT "+json.dumps(result,ensure_ascii=False))
    return 0 if result["status"] in ("PREFLIGHT_DONE","IMAGE_VERIFIED") else 2

if __name__=="__main__":raise SystemExit(main())
