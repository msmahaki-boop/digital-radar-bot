#!/usr/bin/env python3
"""Daily sourced Acolad narrative: every 2–3 slides fresh original ink concept image.

Input MUST be TODAY's live editorial-approved story; output is PREVIEW ONLY.
GPT Image 2 -> Gemini Image -> Qwen -> relevant Pexels/Wikimedia -> text only.
The full story starts from actual hook, NEVER adds the old "hot news" intro.
"""
from __future__ import annotations
import argparse,copy,json,math,os,re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from PIL import Image
from acolad_story_image_ladder import MODELS,attempt,safe_stock,commons_stock
from acolad_narrative_visual_v2 import scene_chunks,render,CONCEPT_DIR

TEHRAN=ZoneInfo("Asia/Tehran")
STORY=Path("acolad_daily_editorial_output/current_story.json")
STATUS=Path("acolad_daily_editorial_output/preview_status.json")
OUT=Path("acolad_today_narrative_draft")
MAX_SCENES=4
MAX_REQUESTS=10

def check_story(story_path=STORY,status_path=STATUS):
    status=json.loads(Path(status_path).read_text(encoding="utf-8"))
    story=json.loads(Path(story_path).read_text(encoding="utf-8"))
    if not status.get("dynamic_story_ready_for_design"):
        raise ValueError("Fresh editor did not pass source and narrative review")
    if status.get("day_tehran")!=datetime.now(TEHRAN).date().isoformat():
        raise ValueError("Research not from today in Tehran")
    slides=story.get("slides") or []
    if not 6<=len(slides)<=16:raise ValueError("Narrative should have 6–16 validated frames")
    if [x.get("n") for x in slides]!=list(range(1,len(slides)+1)):
        raise ValueError("Slide sequence is not continuous")
    if any(not str(s.get("text") or "").strip() for s in slides):
        raise ValueError("Empty slide text")
    if story.get("topic","").strip().casefold() in ("خبرهای داغ امروز","اخبار داغ امروز"):
        raise ValueError("Generic hot-news intro is forbidden")
    # Never pad an unfinished news story or silently replace it with a demo.
    sources=story.get("sources") or []
    if not sources:raise ValueError("No verified source records")
    return story,status

def selected_scene_ids(story):
    groups=scene_chunks(story)
    # Up to four distinct images in total, spaced through narrative.
    count=min(MAX_SCENES,max(2,round(len(story["slides"])/2.8)),len(groups))
    if count==len(groups):return [int(g[0]["scene"]) for g in groups]
    selected=[]
    for i in range(count):
        index=round(i*(len(groups)-1)/(count-1))
        selected.append(int(groups[index][0]["scene"]))
    return list(dict.fromkeys(selected))

def concise_brief(story,sid):
    slides=[s for s in story["slides"] if int(s.get("scene_id",0))==sid]
    if not slides:raise ValueError("Missing scene")
    first=slides[0]
    # Every paid visual must match a concrete story beat, NOT one repeated generic prompt.
    headline=re.sub(r"[*_#]","",first.get("text","")).strip()[:140]
    scene_idea=first.get("visual_idea","")
    claim=" ".join(re.sub(r"[*_#]","",s.get("text","")) for s in slides)[:350]
    sources=story.get("sources") or []
    source_title="; ".join(str(x.get("title") or x.get("publisher") or "")
                         for x in sources[:2])[:230]
    return SimpleNamespace(
        title_fa=headline or story.get("topic",""),
        original_title=(source_title+" | "+str(story.get("topic") or ""))[:290],
        summary_fa=("SCENE-SPECIFIC ACTION: "+str(scene_idea)[:160]+
                    ". Scene narrative: "+claim+
                    ". Illustrate the central metaphor exactly. Leave 75% clean ivory space. "
                    "No text, captions, interfaces or logos."),
        topic=str(story.get("topic") or ""),
    )

def build(story_path=STORY,status_path=STATUS,out=OUT,paid=True):
    story,editor=check_story(story_path,status_path)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    CONCEPT_DIR.mkdir(parents=True,exist_ok=True)
    # Prevent stale scenes from earlier stories entering this day's preview.
    for old in CONCEPT_DIR.glob("scene_[0-9][0-9].png"):
        old.unlink()
    chosen=selected_scene_ids(story)
    records=[]
    requests=0
    for sid in chosen:
        brief=concise_brief(story,sid)
        image=None
        attempts=[]
        if paid:
            for model in MODELS:
                if requests>=MAX_REQUESTS:
                    attempts.append({"status":"PAID_REQUEST_CAP"})
                    break
                image,result=attempt(brief,model)
                attempts.append(result)
                if result["status"]!="GAPGPT_KEY_MISSING":requests+=1
                if image is not None:break
        if image is None:
            image,p=safe_stock(brief)
            attempts.append(p)
        if image is None:
            image,c=commons_stock(brief)
            attempts.append(c)
        status="NO_MATCHING_IMAGE"
        if image is not None:
            path=CONCEPT_DIR/f"scene_{sid:02d}.png"
            image.save(path,"PNG")
            status="AI_IMAGE_NEEDS_ART_REVIEW" if any(x.get("status")=="VALID_IMAGE" for x in attempts) else "LICENSED_STOCK_NEEDS_REVIEW"
        records.append({"scene_id":sid,"first_frame":next(s["n"] for s in story["slides"] if int(s["scene_id"])==sid),
                        "status":status,"attempts":attempts})
    output=out/"frames"
    report=render(story,output,allow_stock=False)
    frames=sorted(output.glob("story_*.png"))
    if len(frames)!=len(story["slides"]):
        raise RuntimeError("Missing frame; do not publish")
    for f in frames:
        with Image.open(f) as image:
            if image.size!=(1080,1920):raise RuntimeError("Wrong frame dimensions")
    qa={"status":"PREVIEW_HUMAN_REVIEW_REQUIRED","date":editor.get("day_tehran"),
        "topic":story.get("topic"),"frames":len(frames),
        "image_slots_planned":len(chosen),
        "image_scenes_added":sum("NEEDS_" in r["status"] for r in records),
        "actual_image_generation_attempts_max":requests,
        "provider_invoice_verified":False,
        "model_preference":list(MODELS),
        "text_starts_with_real_hook":True,"old_hot_news_intro_removed":True,
        "network_drafts_created":0,"queued":0,"published":0,
        "source_records":story.get("sources"),"image_provenance":records,
        "renderer_status":report,"manual_editorial_and_art_approval_required":True}
    (out/"story.json").write_text(json.dumps(story,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"narrative_qa.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding="utf-8")
    print("ACOLAD_NARRATIVE_TODAY_VISUAL "+json.dumps({k:v for k,v in qa.items() if k not in ("source_records","renderer_status","image_provenance")},
        ensure_ascii=False),flush=True)
    print("ACOLAD_NARRATIVE_VISUAL_ATTEMPTS "+json.dumps(records,ensure_ascii=False),flush=True)
    return qa

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--paid",choices=("no","yes"),default="no")
    p.add_argument("--output",default=str(OUT))
    args=p.parse_args()
    build(out=args.output,paid=args.paid=="yes")
