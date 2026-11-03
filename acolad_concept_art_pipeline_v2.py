#!/usr/bin/env python3
"""Acolad original editorial conceptual ink drawings.

One bounded Gemini image attempt with GITHUB GEMINI_API_KEY, then deterministic
original SVG-like Pillow illustrations (no paid calls) for EVERY designated scene.
Never stores secrets, never queues/drafts/publishes.
"""
from __future__ import annotations
import argparse
import base64
import io
import json
import os
from pathlib import Path
import random
import re
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont

MODEL="gemini-3.1-flash-lite-image"
OUT=Path("acolad_concept_assets")
MAX_TOMAN=20000
USD_TO_TOMAN=250000
ESTIMATED_SINGLE_IMAGE_USD=0.0336
MAX_IMAGE_REQUESTS=1
APPROVAL="APPROVED_ONE_GEMINI_CONCEPT_IMAGE_WITHIN_20000_TOMAN"
HOST="https://generativelanguage.googleapis.com/v1beta"
SKETCH_SIZE=(1024,1024)

def image_metaphor(story:dict, scene_id:int)->str:
    """Visual brief from meaning, not fabricated imagery."""
    frames=story.get("slides",[])
    frame=next((f for f in frames if int(f.get("scene_id",0))==scene_id),{})
    idea=str(frame.get("visual_idea","")).strip()
    if not idea:idea=str(story.get("topic","visual metaphor"))
    return re.sub(r"[\x00-\x1f]"," ",idea)[:200]

def image_scenes(story:dict)->list[int]:
    """Use scene boundaries; don't add filler slides or disrupt frozen captions."""
    ids=[]
    groups={}
    for frame in story.get("slides",[]):
        sid=frame.get("scene_id")
        if type(sid) is not int:continue
        groups.setdefault(sid,[]).append(frame)
    # Prefer 1 meaningful visual every ~2-3 frames, at major narrative
    # turns rather than inserting low-value slides or interrupting frozen text.
    for sid,group in groups.items():
        if any(f.get("beat") in ("evidence","experiment","discovery","payoff")
               for f in group):
            ids.append(sid)
    if not ids:
        ids=[sid for i,sid in enumerate(groups) if i%2==1]
    # Downsample heavily illustrated long storyboards. An image belongs to
    # an existing scene and is reused as text accumulates within that scene.
    return ids[:4]

def ink_sketch(scene:int, metaphor:str, output:Path)->dict:
    """Create an ORIGINAL conceptual pen drawing; no third-party asset required.

    Scene-specific motifs are made from ink primitives; assets have true
    transparent PNG backgrounds. No synthetic logo/text or artist imitation.
    """
    rng=random.Random(8419+scene*97+sum(ord(x) for x in metaphor[:100]))
    image=Image.new("RGBA",SKETCH_SIZE,(0,0,0,0))
    draw=ImageDraw.Draw(image)
    dark=(31,30,37,255)
    soft=(98,62,173,255)
    thick=9
    # Drawing grammar: imperfect strokes, human character, metaphorical object.
    def stroke(points,width=thick,color=dark):
        adjusted=[(int(x+rng.uniform(-2.5,2.5)),int(y+rng.uniform(-2.5,2.5)))
                  for x,y in points]
        draw.line(adjusted,fill=color,width=width,joint="curve")
    def oval(box,outline=dark,width=thick):
        draw.ellipse(box,outline=outline,width=width)
    # Person, always drawn by original vector primitives.
    oval((192,260,322,392),width=8)
    stroke([(257,394),(258,555),(228,676)],10)
    stroke([(256,537),(330,680)],10)
    stroke([(256,448),(180,500),(135,477)],8)
    stroke([(255,449),(345,490),(377,469)],8)
    # Emotion/question mark doodle without any caption or typography.
    oval((223,317,231,326),width=4)
    oval((280,317,288,326),width=4)
    stroke([(239,361),(253,353),(271,361)],5)
    # Dynamic editorial metaphor selected from actual story context.
    idea=metaphor.casefold()
    if any(w in idea for w in ("ثبت","حساب","ورود","login","register","قفل","پسورد")):
        # Oversized padlock as a barrier, with an open bridge further right.
        stroke([(518,421),(518,349),(560,290),(655,291),(705,346),(705,425)],13)
        draw.rounded_rectangle((487,420,730,665),radius=31,outline=dark,width=12)
        oval((585,503,630,554),outline=soft,width=10)
        stroke([(607,544),(607,593)],12,color=soft)
        stroke([(754,426),(817,382),(865,411)],8,color=soft)
        stroke([(786,611),(883,609)],7,color=soft)
    elif any(w in idea for w in ("نظر","امتیاز","review","rating","اعتماد","fake")):
        stroke([(480,323),(832,322),(832,630),(630,629),(580,707),(578,634),(480,632),(480,323)],10)
        for x in (542,617,692):
            stroke([(x,430),(x+11,406),(x+24,432),(x+50,438),(x+28,454),(x+32,478)],7,color=soft)
        stroke([(552,537),(762,537)],8)
    elif any(w in idea for w in ("آزمون","تست","مقایسه","experiment","A/B")):
        for x in (495,690):
            draw.rounded_rectangle((x,354,x+154,640),radius=20,outline=dark,width=9)
            stroke([(x+23,419),(x+128,419)],6,color=soft)
            stroke([(x+23,476),(x+128,476)],6)
        stroke([(642,731),(699,700),(755,731)],9,color=soft)
    else:
        # Store / shopping-cart / price dilemma motif.
        draw.arc((480,326,824,683),15,170,fill=dark,width=11)
        stroke([(485,350),(730,350),(767,565),(556,565),(527,403)],10)
        oval((580,593,640,653),width=8)
        oval((689,593,749,653),width=8)
        stroke([(800,425),(858,450),(812,485)],9,color=soft)
    # Quiet tactile paper-pencil specks, always within visual art region.
    for _ in range(23):
        x=rng.randint(120,900);y=rng.randint(220,795)
        if rng.random()<.3:draw.ellipse((x,y,x+2,y+2),fill=(dark[0],dark[1],dark[2],80))
    output.parent.mkdir(parents=True,exist_ok=True)
    image.save(output,optimize=True)
    return {"status":"ORIGINAL_PROCEDURAL_PNG","path":str(output),"transparent":True,
            "license":"Original programmatic artwork for Acolad; no stock/artist source"}

def gemini_one_image(scene:int,metaphor:str,output:Path, budget_toman:int,
                     session=requests)->dict:
    report={"status":"NOT_ATTEMPTED","model":MODEL,"api_calls":0,
            "estimate_toman":round(ESTIMATED_SINGLE_IMAGE_USD*USD_TO_TOMAN),
            "budget_toman":budget_toman,"actual_charge_verified":False}
    if budget_toman>MAX_TOMAN or budget_toman<10000:
        report["status"]="BUDGET_INVALID";return report
    if report["estimate_toman"]+1500>budget_toman:
        report["status"]="BUDGET_TOO_LOW";return report
    key=os.environ.get("GEMINI_API_KEY","").strip()
    if not key:
        report["status"]="GEMINI_SECRET_NOT_SET";return report
    prompt=(
        "Create an ORIGINAL high-quality conceptual editorial illustration: "+metaphor+
        ". Witty, emotionally expressive single visual metaphor. Hand-drawn rough black "
        "ink lines, playful imperfect pencil marks, intelligent visual storytelling, "
        "simple character and one symbolic object, wide negative space. "
        "DO NOT reproduce any named artist's distinctive drawing or character. "
        "No text, letters, captions, digits, logo, brand, watermark or panels. "
        "True transparent image background if supported, otherwise pure uniform "
        "warm near-white #FBF9F7. Strong clear linework suitable for Instagram story."
    )
    payload={"contents":[{"parts":[{"text":prompt}]}],
             "generationConfig":{"responseModalities":["IMAGE"],
                                 "imageConfig":{"aspectRatio":"1:1","imageSize":"1K"}}}
    try:
        report["api_calls"]=1
        resp=session.post(f"{HOST}/models/{MODEL}:generateContent",
            headers={"x-goog-api-key":key,"Content-Type":"application/json"},
            json=payload,timeout=130)
        report["http_status"]=resp.status_code
        if resp.status_code!=200:
            report["status"]="GEMINI_HTTP_"+str(resp.status_code);return report
        data=resp.json()
        choices=data.get("candidates") or []
        parts=(choices[0].get("content",{}).get("parts",[]) if choices else [])
        for part in parts:
            inline=part.get("inlineData") or part.get("inline_data") or {}
            encoded=inline.get("data")
            if not encoded:continue
            raw=base64.b64decode(encoded,validate=True)
            if len(raw)>18_000_000:raise ValueError("image bytes too large")
            with Image.open(io.BytesIO(raw)) as im:
                im.load()
                if im.width<512 or im.height<512:raise ValueError("resolution too low")
                png=im.convert("RGBA")
            output.parent.mkdir(parents=True,exist_ok=True)
            png.save(output,optimize=True)
            report.update({"status":"GENERATED_GEMINI_IMAGE","image_path":str(output),
                           "size":list(png.size),
                           "is_transparent":png.getextrema()[3][0]<255})
            return report
        report["status"]="NO_IMAGE_IN_RESPONSE";return report
    except (requests.RequestException,ValueError,KeyError,OSError) as ex:
        report["status"]="GEMINI_"+type(ex).__name__
        return report

def create_art(story:dict,output=OUT,allow_paid=False,budget_toman=20000):
    scenes=image_scenes(story)
    output.mkdir(parents=True,exist_ok=True)
    status={"status":"PREVIEW_ONLY","scene_ids":scenes,"image_api_calls":0,
            "providers":[],"drafts":0,"queued":0,"published":0,
            "budget_toman":budget_toman,
            "paid_provider_quote_is_estimate_not_wallet_receipt":True}
    for n,sid in enumerate(scenes):
        visual=image_metaphor(story,sid)
        dest=output/f"scene_{sid:02d}.png"
        if n==0 and allow_paid:
            ai=gemini_one_image(sid,visual,dest,budget_toman)
            status["image_api_calls"]=ai["api_calls"]
            status["providers"].append(ai)
            if ai.get("status")=="GENERATED_GEMINI_IMAGE":
                continue
        status["providers"].append(ink_sketch(sid,visual,dest))
    (output/"concept_provenance.json").write_text(
        json.dumps(status,ensure_ascii=False,indent=2),encoding="utf-8")
    print("CONCEPT_ART "+json.dumps(
        {"scene_ids":scenes,"statuses":[r["status"] for r in status["providers"]],
         "image_api_calls":status["image_api_calls"],"publication":"NEVER"},
         ensure_ascii=False))
    return status

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--story-json",type=Path,required=True)
    parser.add_argument("--allow-paid",action="store_true")
    parser.add_argument("--approval",default="")
    parser.add_argument("--budget-toman",type=int,default=20000)
    args=parser.parse_args()
    if args.allow_paid and args.approval!=APPROVAL:
        raise SystemExit("PAID_IMAGE_APPROVAL_REQUIRED")
    if args.budget_toman>MAX_TOMAN:
        raise SystemExit("BUDGET_TOO_HIGH")
    data=json.loads(args.story_json.read_text(encoding="utf-8"))
    create_art(data,allow_paid=args.allow_paid,budget_toman=args.budget_toman)
    return 0
if __name__=="__main__":
    raise SystemExit(main())
