#!/usr/bin/env python3
"""One-image GapGPT conceptual drawing PROBE. Never draft, queue or publish.
Only one POST max; spending budget is a planning gate, not a provider hard cap.
"""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import time
import requests
from PIL import Image

MODEL="gpt-image-1-mini"
BASE_URL="https://api.gapgpt.app/v1"
OUT=Path("acolad_concept_assets")
MAX_BUDGET_USD=0.08    # 20,000 toman at 250,000 toman/USD
MODEL_OUTPUT_PRICE_USD=0.006 # OpenAI official 1024x1536 low price, NOT GapGPT verified
MAX_REQUESTS=1

PROMPTS={
  2: """Original minimalist conceptual editorial ink sketch.
One small online-store owner standing by a huge transparent shopping cart,
puzzled that the store has plenty of visitors yet very few items in carts.
One bold visual metaphor: busy footsteps move past an EMPTY cart.
Playful but thoughtful black hand-drawn pen lines, deliberately imperfect,
expressive human figure, monochrome ink drawing and a single faint lavender accent.
Sparse, witty, high-contrast, lots of negative space.
NOT a copy of any known cartoonist or existing illustration.
No typography, no Persian lettering, no icons, no logos, no border, no watermark.
Transparent PNG background preferred; otherwise a completely flat
very light warm ivory (#FBF9F7) without texture or shadow.
Single clean visual, compositable on a branded vertical Instagram story.""",
  4: """Original metaphorical editorial black-ink doodle on transparency.
A confused shopper at a fork in the road with three payment choices:
one obvious door in bright daylight and other paths hidden behind a curtain.
One simple visual metaphor, a slightly funny expressive human silhouette.
Sparse authentic hand-inked line art, whimsical imperfect strokes,
little color except a hint of pastel cyan or lavender.
NOT an imitation or replication of any particular famous cartoonist.
No text, no letters, no numbers, no logo, no border, no watermark.
Transparent PNG background preferred, otherwise flat warm ivory #FBF9F7.""",
  6: """Original conceptual minimal black-ink editorial drawing on transparency.
A small business owner comparing two almost identical product-page windows,
using a magnifying glass, with a tiny growing sprout to symbolize experiment
and learning rather than guaranteed profits. Charming intelligent metaphor,
simple uneven ink strokes and lots of negative space, a single lavender accent.
Do NOT copy a specific artist or illustration. No logos, no text,
no numbers, no frame, no watermark. PNG transparent preferred,
or completely uniform warm ivory #FBF9F7 background."""
}

def model_available(session,token):
    response=session.get(BASE_URL+"/models",
        headers={"Authorization":"Bearer "+token,"Accept":"application/json"},
        timeout=18)
    response.raise_for_status()
    data=response.json()
    items=data.get("data",[]) if isinstance(data,dict) else []
    ids={x.get("id","") for x in items if isinstance(x,dict)}
    return MODEL in ids, len(ids)

def prepare_request(scene:int,budget_usd:float):
    if scene not in PROMPTS:raise ValueError("Scene not allowlisted")
    if budget_usd<=0 or budget_usd>MAX_BUDGET_USD:raise ValueError("Exceeds authorized budget")
    # Total expected spend includes one image + generous input/markup buffer.
    # Actual provider pricing is not available in the response; NO guarantee.
    estimate=MODEL_OUTPUT_PRICE_USD+0.006
    if estimate>budget_usd:raise ValueError("Expected image request exceeds local budget")
    return {"model":MODEL,"prompt":PROMPTS[scene],"n":1,
            "size":"1024x1536","quality":"low",
            "background":"transparent","output_format":"png"},estimate

def run(scene:int,budget_usd:float,output=OUT,session=requests):
    output.mkdir(parents=True,exist_ok=True)
    report={"status":"NOT_REQUESTED","model":MODEL,"scene":scene,
            "call_limit":MAX_REQUESTS,
            "budget_toman":round(budget_usd*250000),
            "estimated_price_toman":None,
            "provider_price_verified":False,
            "actual_charge_verified":False,
            "drafts":0,"queued":0,"published":0}
    try:
        payload,estimate=prepare_request(scene,budget_usd)
        report["estimated_price_toman"]=round(estimate*250000)
        token=os.getenv("GAPGPT_API_KEY","").strip()
        if not token:
            report["status"]="SECRET_MISSING";return report
        available,model_count=model_available(session,token)
        report["model_count"]=model_count
        if not available:
            report["status"]="IMAGE_MODEL_NOT_LISTED_STOPPED_BEFORE_SPENDING"
            return report
        report["status"]="SINGLE_PAID_REQUEST_STARTED"
        start=time.monotonic()
        # EXACTLY ONE billable attempt; deliberately no retries.
        response=session.post(BASE_URL+"/images/generations",
          headers={"Authorization":"Bearer "+token,"Content-Type":"application/json",
                   "Accept":"application/json"},
          json=payload,timeout=145)
        report["latency_seconds"]=round(time.monotonic()-start,1)
        report["http_status"]=response.status_code
        if response.status_code!=200:
            report["status"]="IMAGE_API_HTTP_ERROR"
            # No raw body logs: could reveal tokens or private account info.
            return report
        data=response.json()
        entries=data.get("data",[]) if isinstance(data,dict) else []
        if not entries or not isinstance(entries[0],dict):
            report["status"]="NO_IMAGE_IN_RESPONSE";return report
        value=entries[0].get("b64_json")
        if not isinstance(value,str):
            report["status"]="NO_BASE64_PNG_RESPONSE";return report
        raw=base64.b64decode(value,validate=True)
        if len(raw)>16_000_000:raise ValueError("Image too large")
        with Image.open(io.BytesIO(raw)) as im:
            if im.width<500 or im.height<500:raise ValueError("Small image")
            picture=im.convert("RGBA")
        target=output/f"scene_{scene:02d}.png"
        picture.save(target,optimize=True)
        report["status"]="IMAGE_GENERATED_PREVIEW_ONLY"
        report["image_file"]=target.name
        report["image_size"]=list(picture.size)
        report["transparent_pixels"]=bool(picture.getextrema()[3][0]<255)
        return report
    except (requests.RequestException,ValueError,KeyError,OSError) as ex:
        report["status"]="API_OR_IMAGE_ERROR_"+type(ex).__name__
        return report
    finally:
        (output/"image_api_status.json").write_text(
            json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--scene",type=int,default=2)
    parser.add_argument("--budget-usd",type=float,default=0.08)
    parser.add_argument("--approval",required=True)
    args=parser.parse_args()
    if args.approval!="USER_APPROVED_ONE_IMAGE_20000_TOMAN":
        raise SystemExit("APPROVAL_MISSING")
    result=run(args.scene,args.budget_usd)
    print("IMAGE_PROBE "+json.dumps(result,ensure_ascii=False))
    return 0 if result["status"]=="IMAGE_GENERATED_PREVIEW_ONLY" else 2

if __name__=="__main__":raise SystemExit(main())
