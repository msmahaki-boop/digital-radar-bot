#!/usr/bin/env python3
"""Genuine GapGPT GPT Image 2.5 cutout generation for Acolad compositing.

NEVER produces a procedural/stock substitute, never touches social APIs.
An HTTP 200 without a valid RGBA transparent PNG is NOT a successful AI asset.
"""
from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path

import requests
from PIL import Image

BASE_URL = "https://api.gapgpt.app/v1"
MODEL = "gpt-image-2.5-flare"
MAX_IMAGES = 10
MAX_BYTES = 25_000_000
OUT = Path("acolad_concept_assets")


def prompt_for_scene(story: dict, scene: int) -> str:
    slides = [x for x in story.get("slides", []) if int(x.get("scene_id") or 0) == scene]
    if not slides:
        raise ValueError("MISSING_SCENE")
    visual = str(slides[0].get("visual_idea") or "").strip()
    if not visual:
        raise ValueError("NO_SOURCE_GROUNDED_VISUAL_BRIEF")
    return (
        "Create one ORIGINAL amusing editorial pen-and-ink illustration asset for "
        "a Persian digital-marketing story. Visual metaphor: " + visual[:350] + "\n"
        "A whimsical old-fashioned storybook hand-drawing: sparse black expressive "
        "wobbly contour lines, quirky friendly characters, playfully exaggerated "
        "proportions, poetic visual humor, selective pen hatching. Evoke the "
        "general qualities of hand-drawn humorous children's book art, but DO NOT "
        "reproduce any named illustrator's specific compositions or characters. "
        "Make an isolated DRAWN SUBJECT only, not an Instagram poster. "
        "Fully transparent alpha background with NO paper, white rectangle, "
        "background texture, borders, shadow, gradients, checkerboard or scenery. "
        "No text, typography, letters, numbers, UI labels, brand marks or logos. "
        "Centered readable silhouette, generous transparent margin, black strokes "
        "with fine hand-drawn detail. This PNG will be composited above Persian "
        "text on Acolad's EXISTING branded 1080x1920 background."
    )


def models_available(key: str, session=requests) -> bool:
    r = session.get(BASE_URL + "/models",
                    headers={"Authorization": "Bearer " + key,
                             "Accept": "application/json"}, timeout=25)
    if r.status_code != 200:
        raise RuntimeError("GAPGPT_MODELS_HTTP_" + str(r.status_code))
    obj = r.json()
    rows = obj.get("data") if isinstance(obj, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("UNRECOGNIZED_IMAGE_MODEL_CATALOG")
    return any(isinstance(row, dict) and row.get("id") == MODEL for row in rows)


def verify_png(raw: bytes) -> tuple[Image.Image, dict]:
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("AI_IMAGE_BYTES_INVALID")
    with Image.open(io.BytesIO(raw)) as src:
        if src.format != "PNG":
            raise ValueError("NOT_PNG")
        if "A" not in src.getbands() and "transparency" not in src.info:
            raise ValueError("NO_REAL_ALPHA_CHANNEL")
        if min(src.size) < 512 or max(src.size) > 4096:
            raise ValueError("BAD_DIMENSIONS")
        image = src.convert("RGBA")
        image.load()
    alpha = image.getchannel("A")
    hist = alpha.histogram()
    pixels = image.width * image.height
    transparent = sum(hist[:32]) / pixels
    opaque = sum(hist[240:]) / pixels
    # A fully opaque square, a fully transparent blank, and fake alpha
    # are all errors. Never claim a procedural silhouette is model output.
    if transparent < .12 or opaque < .005:
        raise ValueError("NOT_A_VISIBLE_TRANSPARENT_CUTOUT")
    crop = alpha.point(lambda p: 255 if p > 40 else 0).getbbox()
    if not crop:
        raise ValueError("INVISIBLE_CUTOUT")
    return image, {"width": image.width, "height": image.height,
                   "transparent_fraction": round(transparent, 4),
                   "opaque_fraction": round(opaque, 4), "visible_bbox": list(crop)}


def white_paper_to_alpha_for_real_ai_drawing(raw: bytes) -> bytes:
    """Remove near-white paper ONLY from a real returned GPT Image pen drawing.

    This is postprocessing the API's genuine art, not a procedural illustration.
    It fails closed if the source is a colored/full-scene photo or nearly blank.
    """
    from PIL import ImageOps
    with Image.open(io.BytesIO(raw)) as source:
        if source.format!="PNG":raise ValueError("IMAGE_NOT_PNG_FOR_ALPHA_KNOCKOUT")
        rgb=source.convert("RGB")
        rgb.load()
    small=rgb.resize((64,64))
    pixels=list(small.getdata())
    total=len(pixels)
    paper=sum(1 for r,g,b in pixels if min(r,g,b)>=235 and
              max(r,g,b)-min(r,g,b)<=35)/total
    ink=sum(1 for r,g,b in pixels if min(r,g,b)<125 and
            max(r,g,b)-min(r,g,b)<75)/total
    if paper<0.48 or ink<0.002 or ink>0.50:
        raise ValueError("AI_IMAGE_NOT_A_SPARSE_WHITE_PAPER_INK_DRAWING")
    # Original RGB strokes are preserved. Only neutral near-white background
    # is made transparent; all authorial details come from the GPT API.
    grayscale=ImageOps.grayscale(rgb)
    mask=grayscale.point(lambda v: max(0,min(255,(240-v)*3)) if v<240 else 0)
    rgba=rgb.convert("RGBA")
    rgba.putalpha(mask)
    out=io.BytesIO()
    rgba.save(out,format="PNG")
    return out.getvalue()


def prepare_real_ai_cutout(raw: bytes) -> tuple[Image.Image,dict,str]:
    try:
        image,stats=verify_png(raw)
        return image,stats,"native_api_alpha"
    except ValueError as original:
        if str(original) not in ("NO_REAL_ALPHA_CHANNEL","NOT_A_VISIBLE_TRANSPARENT_CUTOUT"):
            raise
        prepared=white_paper_to_alpha_for_real_ai_drawing(raw)
        image,stats=verify_png(prepared)
        return image,stats,"white_paper_knockout_on_gpt_generated_art"


def read_provider_image(row: dict, session=requests) -> tuple[bytes, str]:
    """GapGPT may respond with hosted image URL instead of OpenAI base64."""
    if isinstance(row.get("b64_json"), str):
        try:
            return base64.b64decode(row["b64_json"], validate=True), "b64_json"
        except (ValueError, base64.binascii.Error) as exc:
            raise RuntimeError("IMAGE_INVALID_BASE64") from exc
    url = row.get("url")
    if not isinstance(url, str):
        raise RuntimeError("IMAGE_PROVIDER_NEITHER_B64_NOR_URL")
    from urllib.parse import urlsplit, urljoin
    import ipaddress

    def validated_https(uri: str):
        parts=urlsplit(uri)
        host=(parts.hostname or "").lower()
        if parts.scheme!="https" or not host or parts.username or parts.password:
            raise RuntimeError("IMAGE_RETURN_URL_NOT_SAFE_HTTPS")
        if host=="localhost" or host.endswith((".localhost",".local",".internal")):
            raise RuntimeError("IMAGE_RETURN_URL_UNSAFE_HOST")
        try:
            address=ipaddress.ip_address(host.strip("[]"))
            if not address.is_global:
                raise RuntimeError("IMAGE_RETURN_URL_UNSAFE_IP")
        except ValueError:
            pass
        if len(uri)>4096:raise RuntimeError("IMAGE_RETURN_URL_TOO_LONG")
        return uri

    current=validated_https(url)
    for hop in range(4):
        reply=session.get(current,timeout=75,allow_redirects=False)
        if reply.status_code in (301,302,303,307,308):
            if hop==3:raise RuntimeError("IMAGE_RETURN_TOO_MANY_REDIRECTS")
            location=reply.headers.get("Location","")
            if not location:raise RuntimeError("IMAGE_RETURN_REDIRECT_WITHOUT_LOCATION")
            current=validated_https(urljoin(current,location))
            continue
        if reply.status_code!=200:
            raise RuntimeError("IMAGE_RETURN_DOWNLOAD_HTTP_"+str(reply.status_code))
        if len(reply.content)>MAX_BYTES:
            raise RuntimeError("IMAGE_RETURN_TOO_LARGE")
        return reply.content, "provider_url"
    raise RuntimeError("IMAGE_RETURN_REDIRECT_FAILED")


def generate(story: dict, scene: int, output: Path, session=requests, *,
             key: str | None = None) -> dict:
    key = key if key is not None else os.environ.get("GAPGPT_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GAPGPT_SECRET_MISSING")
    payload = {"model": MODEL, "prompt": prompt_for_scene(story, scene),
               "n": 1, "size": "1024x1024", "quality": "medium",
               "background": "transparent", "output_format": "png"}
    r = session.post(BASE_URL + "/images/generations",
                     headers={"Authorization": "Bearer " + key,
                              "Content-Type": "application/json",
                              "Accept": "application/json"},
                     json=payload, timeout=195)
    if r.status_code != 200:
        # Distinguish per-key quota from transient model/API transport errors.
        # Never emit provider response bodies, credential values or arbitrary messages.
        if r.status_code == 403:
            try:
                obj = r.json()
                err = obj.get("error") if isinstance(obj, dict) else None
                if isinstance(err, dict) and err.get("code") == "pre_consume_token_quota_failed":
                    raise RuntimeError("GAPGPT_IMAGE_KEY_PRECONSUME_QUOTA_BLOCKED")
            except (ValueError, TypeError, AttributeError):
                pass
        raise RuntimeError("IMAGE_PROVIDER_HTTP_" + str(r.status_code))
    body = r.json()
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise RuntimeError("IMAGE_PROVIDER_RESULT_MALFORMED")
    raw, image_source = read_provider_image(data[0], session=session)
    image, stats, transparency_method = prepare_real_ai_cutout(raw)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG", optimize=True)
    return {"model": MODEL, "provider": "GapGPT",
            "real_ai_generated": True, "background": "transparent",
            "source_scene_id": scene, "image_response": image_source,
            "transparency_method": transparency_method, "path": output.name, **stats}


def generate_scenes(story: dict, scenes: list[int], output: Path = OUT,
                    *, session=requests) -> dict:
    scenes = list(dict.fromkeys(scenes))
    if not 1 <= len(scenes) <= MAX_IMAGES:
        raise RuntimeError("IMAGE_SCENE_COUNT_OUT_OF_RANGE")
    key = os.environ.get("GAPGPT_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GAPGPT_SECRET_MISSING")
    if not models_available(key, session):
        raise RuntimeError("GAPGPT_GPT_IMAGE_2_5_NOT_IN_MODEL_CATALOG")
    records = []
    for scene in scenes:
        dest = output / ("scene_%02d.png" % scene)
        records.append(generate(story, scene, dest, session=session, key=key))
        print("ACOLAD_REAL_TRANSPARENT_AI_SCENE " + json.dumps({
            "scene": scene, "model": MODEL,
            "transparent_fraction": records[-1]["transparent_fraction"],
            "real_ai_generated": True}, ensure_ascii=False), flush=True)
    manifest = {"provider": "GapGPT", "model": MODEL,
                "image_count": len(records), "real_ai_generated": True,
                "procedural_assets": 0, "stock_assets": 0,
                "records": records, "publication": "PREVIEW_ONLY"}
    output.mkdir(parents=True, exist_ok=True)
    (output / "transparent_ai_provenance.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
