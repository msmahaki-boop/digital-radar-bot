#!/usr/bin/env python3
"""Actual AI Horde community diffusion image generation for Acolad.

Requires no credential by default. A submitted task can be slow and may fail.
Never label procedural graphics as AI-generated images. Always save receipts.
Images from third-party AI workers are reviewed before anything publishes.
"""
from __future__ import annotations
import argparse
import io
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
import requests
from PIL import Image

API="https://aihorde.net/api/v2"
ANON="0000000000"
TIME_LIMIT_SECONDS=225
OUT=Path("acolad_horde_real_image_output")
MAX_IMAGES=1

def prompt_for(visual,topic=""):
    visual=str(visual)[:420]
    topic=str(topic)[:200]
    return (
        "An ORIGINAL, intelligent, whimsical editorial illustration made with "
        "scratchy black ink pen on pure warm white paper. Playful sparse 2D "
        "line drawing, expressive small adult figure, exaggerated metaphorical "
        "props, surprising visual storytelling, children's-book-like but made "
        "for an adult magazine, bold dark uneven ink outlines, very simple "
        "composition, large empty areas, no gradients or glossy 3D. "
        "Illustration's exact subject: "+visual+". Context: "+topic+
        ". Do not imitate, copy or recreate any named illustrator's published "
        "work or famous characters. No words, text, logos, numbers, watermarks "
        "or borders. No violence or graphic content. "
        "### photorealistic, 3D, photography, gradients, anime, captions, "
        "lettering, signature, watermark, clutter, gore"
    )

def can_download(href):
    v=urlsplit(href)
    if v.scheme!="https" or v.username or v.password:return False
    if v.port not in (None,443):return False
    host=(v.hostname or "").lower()
    return bool(host) and not any(x in host for x in ("localhost","127.0.0.1")) and (
        host.endswith(".horde-cdn.com") or
        host.endswith(".stablehorde.net") or
        host.endswith(".aihorde.net") or
        host.endswith(".r2.dev") or
        host.endswith(".cloudflarestorage.com") or
        host.endswith(".cloudflare.com")
    )

def run(visual,topic,output=OUT,timeout_sec=TIME_LIMIT_SECONDS,session=requests):
    output.mkdir(parents=True,exist_ok=True)
    result={"provider":"AI Horde volunteer diffusion","status":"NOT_SUBMITTED",
        "generated_with_model":False,"image_file":None,
        "images_attempted":0,"fee_toman":0,"submitted_task_id":None,
        "timeout_seconds":timeout_sec,"drafts":0,"queued":0,"published":0}
    auth=os.getenv("AI_HORDE_API_KEY","").strip() or ANON
    hdr={"apikey":auth,"Client-Agent":"AcoladEditorial:1.0:github.com/msmahaki-boop/digital-radar-bot",
         "Content-Type":"application/json"}
    payload={
       "prompt":prompt_for(visual,topic),
       "params":{"width":512,"height":512,"steps":20,"n":1,
                 "sampler_name":"k_euler","cfg_scale":6.5},
       "nsfw":False,"censor_nsfw":True,"r2":True,
       "shared":False,"slow_workers":False,
       "replacement_filter":True,
    }
    start=time.monotonic()
    try:
        result["images_attempted"]=1
        resp=session.post(API+"/generate/async",json=payload,headers=hdr,timeout=20)
        result["submit_http"]=resp.status_code
        if resp.status_code not in (200,202):
            result["status"]="SUBMIT_REJECTED_"+str(resp.status_code);return result
        receipt=resp.json()
        job_id=receipt.get("id","")
        if not isinstance(job_id,str) or len(job_id)<16:
            result["status"]="INVALID_JOB_RECEIPT";return result
        result["submitted_task_id"]=job_id
        result["status"]="JOB_SUBMITTED_WAITING"
        while time.monotonic()-start<timeout_sec:
            time.sleep(8)
            check=session.get(API+"/generate/check/"+job_id,headers=hdr,timeout=15)
            if check.status_code!=200:
                result["status"]="POLL_ERROR_"+str(check.status_code);return result
            status=check.json()
            if status.get("faulted"):
                result["status"]="WORKER_FAULTED";return result
            if status.get("done"):break
        else:
            result["status"]="WAIT_TIMEOUT";return result
        final=session.get(API+"/generate/status/"+job_id,headers=hdr,timeout=20)
        if final.status_code!=200:
            result["status"]="RESULT_ERROR_"+str(final.status_code);return result
        entries=final.json().get("generations") or []
        if not entries:
            result["status"]="NO_GENERATED_IMAGES";return result
        asset=entries[0].get("img","")
        if not isinstance(asset,str) or not can_download(asset):
            result["status"]="UNEXPECTED_IMAGE_HOST";return result
        raw=session.get(asset,timeout=25)
        raw.raise_for_status()
        if len(raw.content)>16_000_000:
            result["status"]="OVERSIZED_IMAGE";return result
        with Image.open(io.BytesIO(raw.content)) as im:
            if im.width<512 or im.height<512:
                result["status"]="TOO_SMALL";return result
            rendered=im.convert("RGBA")
        dest=output/"horde_original_01.png"
        rendered.save(dest,optimize=True)
        result["image_file"]=dest.name
        result["size"]=list(rendered.size)
        result["status"]="REAL_AI_IMAGE_SAVED"
        result["generated_with_model"]=True
        result["model"]=str(entries[0].get("model",""))[:90]
        return result
    except (requests.RequestException,ValueError,KeyError,TypeError,OSError) as exc:
        result["status"]="ERROR_"+type(exc).__name__
        return result
    finally:
        result["elapsed_seconds"]=round(time.monotonic()-start,1)
        (output/"horde_status.json").write_text(
          json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print("HORDE_IMAGE_RESULT "+json.dumps(result,ensure_ascii=False))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--visual",default="a tiny shopkeeper stopped by a giant locked door, customers walk past him")
    p.add_argument("--topic",default="online shopping login friction")
    p.add_argument("--timeout",type=int,default=225)
    p.add_argument("--output",type=Path,default=OUT)
    x=p.parse_args()
    if x.timeout<60 or x.timeout>300:
        raise SystemExit("TIMEOUT_OUTSIDE_ALLOWED_RANGE")
    report=run(x.visual,x.topic,x.output,x.timeout)
    return 0 if report["generated_with_model"] else 2

if __name__=="__main__":raise SystemExit(main())
