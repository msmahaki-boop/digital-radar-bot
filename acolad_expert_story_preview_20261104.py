#!/usr/bin/env python3
"""Acolad expert-sourced candidate with independently edited public captions.
PREVIEW ONLY. No queue, social uploads, or public publish. Deliberately not generic Luna text.
"""
from __future__ import annotations
import json,re,sys
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
from acolad_editorial_trust_gate import evaluate,check_public_copy
from acolad_luna_research_preview import story_quality,cinematic_quality
from acolad_story_image_ladder import attempt,safe_stock,commons_stock
from acolad_narrative_visual_v2 import render,CONCEPT_DIR

STEM="2026-11-04-return-missing-button"
ROOT=Path("editorial/candidates")
OUT=Path("acolad_expert_story_preview")
SCENES=(1,2,3)
MODELS=("gpt-image-2","gemini-2.5-flash-image","gapgpt/qwen-image-2.1")
MAX_BILLABLE_ATTEMPTS=5

def load():
    story=json.loads((ROOT/(STEM+".story.json")).read_text(encoding="utf8"))
    evidence=json.loads((ROOT/(STEM+".evidence.json")).read_text(encoding="utf8"))
    copies=json.loads((ROOT/(STEM+".channel_copies.json")).read_text(encoding="utf8"))
    return story,evidence,copies

def quality(story,evidence,copies):
    gate=evaluate(story,evidence)
    bad=story_quality(story,evidence)+cinematic_quality(story,evidence)
    if not gate["passed"]:bad+=gate["hard_vetoes"]
    if story.get("publication_permission")!="PREVIEW_ONLY":bad.append("Public permission must remain preview-only")
    if copies.get("editorial_release")!="PENDING_USER_REVIEW":bad.append("Must require user review")
    for k in ("instagram_caption","telegram","bale"):
        clean=check_public_copy(copies.get(k,""))
        if not clean["clean"]:bad.append("Audience copy has private/source leakage: "+k+" "+str(clean["violations"]))
    if not (350<=len(copies["telegram"])<=2500):bad.append("Telegram length unacceptable")
    if not (150<=len(copies["bale"])<=960):bad.append("Bale length unacceptable")
    if any("https://" in str(copies[k]) or "http://" in str(copies[k]) for k in ("telegram","bale","instagram_caption")):
        bad.append("Raw URL leaked to public text")
    return {"hard_pass":not bad,"errors":bad,"source_first_party":True,
        "human_quality_score":"UNASSESSED","human_release_approved":False,
        "evidence":[{"id":s["id"],"publisher":s["publisher"],"date":s["date"],"url":s["url"],"claim_scope":s["scope"]} for s in evidence]}

def brief_for(story,scene):
    frames=[s for s in story["slides"] if s["scene_id"]==scene]
    idea=frames[0]["visual_idea"]
    source="Baymard's firsthand UX usability observation: a return option was hidden after return eligibility expired."
    return SimpleNamespace(topic=story["topic"],title_fa=story["topic"],
        original_title=source,
        summary_fa=(idea+". "+" ".join(s["text"].replace("**","") for s in frames)+
          " Ensure a single clean original black ink metaphor, 75% airy space. No wording."))

def run(paid=True):
    OUT.mkdir(parents=True,exist_ok=True)
    report={"mode":"PREVIEW_ONLY","network_post_requests":0,"network_drafts":0,"published":0,
            "scheduled":0,"not_a_breaking_news_claim":True,
            "public_source_urls":False,"human_editorial_approval":False,
            "image_provider_attempt_limit":MAX_BILLABLE_ATTEMPTS,
            "image_provider_requests":0,"images":[]}
    story,evidence,copies=load()
    qa=quality(story,evidence,copies)
    report["editorial_gate"]=qa
    if not qa["hard_pass"]:
        report["status"]="BLOCKED_EDITORIAL"
        (OUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
        print("ACOLAD_EXPERT_PREVIEW "+json.dumps(report,ensure_ascii=False),flush=True)
        return report
    CONCEPT_DIR.mkdir(parents=True,exist_ok=True)
    for old in CONCEPT_DIR.glob("scene_[0-9][0-9].png"):
        old.unlink()
    for scene in SCENES:
        item=brief_for(story,scene)
        image=None; attempts=[]
        if paid:
            for model in MODELS:
                if report["image_provider_requests"]>=MAX_BILLABLE_ATTEMPTS:break
                image,status=attempt(item,model)
                if status.get("status")!="GAPGPT_KEY_MISSING":
                    report["image_provider_requests"]+=1
                attempts.append(status)
                if image is not None:break
        if image is None:
            image,stock=safe_stock(item)
            attempts.append(stock)
        if image is None:
            image,commons=commons_stock(item)
            attempts.append(commons)
        result="TEXT_ONLY"
        if image is not None:
            image.save(CONCEPT_DIR/f"scene_{scene:02d}.png","PNG")
            result="VISUAL_CANDIDATE_REVIEW_REQUIRED"
        report["images"].append({"scene_id":scene,"result":result,"attempts":attempts})
    frames=OUT/"frames"
    layout=render(story,frames,allow_stock=False)
    outputs=sorted(frames.glob("story_*.png"))
    if len(outputs)!=len(story["slides"]):raise ValueError("Frame count wrong")
    for file in outputs:
        with Image.open(file) as im:
            if im.size!=(1080,1920):raise ValueError("Frame dimensions wrong")
    report["frames"]=len(outputs)
    report["layout_status"]=layout.get("state")
    report["status"]="NINE_FRAME_VISUAL_PREVIEW_FOR_OWNER_REVIEW"
    (OUT/"story.json").write_text(json.dumps(story,ensure_ascii=False,indent=2),encoding="utf8")
    (OUT/"evidence_INTERNAL_ONLY.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf8")
    (OUT/"audience_copies.json").write_text(json.dumps(copies,ensure_ascii=False,indent=2),encoding="utf8")
    for name in ("telegram","bale","instagram_caption"):
        (OUT/(name+".txt")).write_text(copies[name]+"\n",encoding="utf8")
    (OUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print("ACOLAD_EXPERT_PREVIEW "+json.dumps(report,ensure_ascii=False),flush=True)
    return report

if __name__=="__main__":
    r=run(paid="--no-paid-images" not in sys.argv)
    raise SystemExit(0 if r["status"]=="NINE_FRAME_VISUAL_PREVIEW_FOR_OWNER_REVIEW" else 2)
