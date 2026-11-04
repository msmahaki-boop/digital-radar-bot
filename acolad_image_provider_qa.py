#!/usr/bin/env python3
"""Isolated image-provider QA for Acolad. NEVER drafts, queues or publishes."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import re
import requests
from PIL import Image

MAX_BYTES = 20_000_000
OPENAI_URL = "https://api.openai.com/v1/images/generations"
PEXELS_URL = "https://api.pexels.com/v1/search"
MODEL = "gpt-image-1-mini"

def scene_prompt(brief):
    """Generate a unique visual brief from evidence-backed scene content."""
    scene = str(brief.get("scene_idea") or "").strip()
    article = str(brief.get("article_fact") or "").strip()
    if len(scene) < 20 or len(article) < 20:
        raise ValueError("Scene and sourced article fact required: no generic art")
    return (
        "Original witty, restrained editorial illustration: " + scene[:600] +
        "\nGrounding (do not depict invented facts): " + article[:450] +
        "\nHuman, hand-drawn uneven black pen lines, expressive visual metaphor, "
        "warm ivory paper, very sparse lilac accent and generous negative space. "
        "Simple organic line art; do not imitate any named artist or existing cartoon. "
        "No text, logos, letters, screenshots, branding, numbers or watermarks."
    )

def validated_png(payload):
    raw = base64.b64decode(payload, validate=True)
    if len(raw) > MAX_BYTES:
        raise ValueError("Image too large")
    with Image.open(io.BytesIO(raw)) as im:
        im.verify()
    with Image.open(io.BytesIO(raw)) as im:
        if im.width < 512 or im.height < 512:
            raise ValueError("Image too small")
        return im.convert("RGBA").copy()

def generate_openai(brief, session=requests):
    token = os.getenv("OPENAI_API_KEY", "").strip()
    if not token:
        return None, {"provider": "openai", "status": "NO_KEY"}
    payload = {"model": MODEL, "prompt": scene_prompt(brief),
               "size": "1024x1536", "quality": "medium", "n": 1}
    try:
        r = session.post(OPENAI_URL, json=payload,
                         headers={"Authorization": "Bearer " + token}, timeout=180)
        if r.status_code != 200:
            reason = {401:"AUTH",403:"FORBIDDEN",429:"LIMIT_OR_CREDIT"}.get(r.status_code, "HTTP_ERROR")
            return None, {"provider":"openai","status":reason,"http_status":r.status_code}
        entries = r.json().get("data", [])
        b64 = entries[0].get("b64_json") if entries else None
        if not isinstance(b64, str):
            return None, {"provider":"openai","status":"NO_IMAGE_PAYLOAD"}
        return validated_png(b64), {"provider":"openai","status":"IMAGE_VERIFIED","model":MODEL}
    except (requests.RequestException, ValueError, KeyError, IndexError, OSError) as ex:
        return None, {"provider":"openai","status":"ERROR_" + type(ex).__name__}

def stock_candidate(brief, session=requests):
    """Pexels fallback: return ONLY a licensed candidate, never claim news photo."""
    token = os.getenv("PEXELS_API_KEY", "").strip()
    query = str(brief.get("stock_query") or "").strip()
    if not token or not 3 <= len(query) <= 100:
        return {"status":"STOCK_UNAVAILABLE"}
    try:
        r = session.get(PEXELS_URL,
            params={"query":query,"per_page":5,"orientation":"portrait"},
            headers={"Authorization":token},timeout=25)
        if r.status_code != 200:
            return {"status":"STOCK_HTTP_ERROR","http_status":r.status_code}
        photos = r.json().get("photos") or []
        for p in photos:
            src = p.get("src") or {}
            if p.get("id") and p.get("url") and src.get("large2x"):
                return {"status":"STOCK_CANDIDATE_REQUIRES_HUMAN_REVIEW",
                        "provider":"Pexels","photo_id":p["id"],
                        "page_url":p["url"],"image_url":src["large2x"],
                        "photographer":p.get("photographer"),
                        "attribution":"Photo via Pexels; credit photographer when possible",
                        "license_url":"https://www.pexels.com/license/",
                        "editorial_warning":"Conceptual stock illustration only; not a photograph of the reported event"}
        return {"status":"NO_STOCK_MATCH"}
    except (requests.RequestException, ValueError, KeyError, TypeError) as ex:
        return {"status":"STOCK_ERROR_" + type(ex).__name__}

def run(brief, output, approval=False, session=requests):
    output = Path(output)
    output.mkdir(parents=True,exist_ok=True)
    report = {"state":"PREVIEW_ONLY","drafts":0,"queued":0,"published":0,
              "stock_auto_selected":False}
    try:
        scene_prompt(brief)
        if not approval:
            report["image"]={"status":"PAID_GENERATION_NOT_APPROVED"}
        else:
            image, detail = generate_openai(brief, session)
            report["image"]=detail
            if image is not None:
                target=output/"concept_preview.png"
                image.save(target,format="PNG")
                report["image_file"]=target.name
        if "image_file" not in report:
            report["stock"]=stock_candidate(brief,session)
        report["human_visual_review_required"]=True
    except ValueError as ex:
        report["image"]={"status":"INVALID_BRIEF","reason":str(ex)}
    (output/"provider_status.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--brief",required=True)
    ap.add_argument("--output",default="acolad_image_provider_qa")
    ap.add_argument("--approval",default="")
    args=ap.parse_args()
    data=json.loads(Path(args.brief).read_text(encoding="utf-8"))
    result=run(data,args.output,args.approval=="ONE_IMAGE_API_TEST_APPROVED")
    print(json.dumps(result,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
