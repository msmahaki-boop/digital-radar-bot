#!/usr/bin/env python3
"""Original editorial concept art for DAILY story scenes via local REAL diffusion.

One open-license AI model is loaded once on GitHub CPU and refines different
scene-specific original black-ink seed sketches. No image-service API keys.
For each uncertain result, retain a named provenance and use a transparent
original conceptual fallback, NEVER silently label procedural as AI.
No social publishing or NovinHub network calls.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import time
import re

from PIL import Image, ImageOps
from acolad_concept_art_pipeline_v2 import image_scenes,image_metaphor,ink_sketch

MODEL="nota-ai/bk-sdm-tiny"
LICENSE="creativeml-openrail-m"
OUTPUT=Path("acolad_concept_assets")
CAP_SCENES=4

SEMANTIC_MOTIFS=(
  (("قفل","ثبت‌نام","عضویت","ورود","login","signup","account"),"a giant locked door and a tiny visitor holding a key"),
  (("قیمت","گرانی","تورم","هزینه","دلار","معیشت","price","cost"),"a little shopkeeper crushed under a huge price tag"),
  (("خرید","فروشگاه","سبد","سفارش","checkout","shopping"),"one tiny customer stuck between an empty shopping cart and a shop door"),
  (("هوش","ربات","ai","machine","chatbot"),"an overloaded shopkeeper being helped by a little robot"),
  (("آزمون","تست","experiment","مقایسه","a/b"),"a human choosing between two simple doors while holding a magnifying glass"),
  (("اینستاگرام","شبکه","محتوا","social","video"),"a tiny human carrying an impossibly giant smartphone with a speech bubble"),
  (("اعتماد","امنیت","هک","قانون","حریم","privacy"),"a worried person sheltering behind a giant umbrella with a shield"),
  (("برند","بازاریابی","تبلیغ","campaign","marketing"),"a little person pulling a giant paper megaphone"),
  (("پشتیبانی","خدمت","تجربه مشتری","support"),"a tired shopkeeper buried under parcels and message notes"),
)
def editorial_english_motif(visual:str,topic:str)->str:
    # Visual brief is the ACTUAL scene; the overall story title is fallback,
    # otherwise the same headline keyword leaks into every concept prompt.
    for subject in (str(visual).casefold(),str(topic).casefold()):
        for needles,english in SEMANTIC_MOTIFS:
            if any(x in subject for x in needles):return english
    return "a little person dragging a huge abstract question mark uphill"

def original_prompt(visual:str,topic:str)->str:
    motif=editorial_english_motif(visual,topic)
    return ("Simple original 2D black pen drawing on empty white paper. "
            +motif+". Witty visual metaphor, expressive cartoon character, "
            "sparse rough ink lines, quiet negative space. No letters or logos.")
NEGATIVE=("detailed buildings, signage, gibberish words, logo, frame, "
          "3d, photorealism, textures, gradients, dark background, crowd, busy")
def matte_white_to_alpha(image:Image.Image)->Image.Image:
    picture=image.convert("RGBA")
    pix=picture.load()
    # Single-frame matte removal; keep dark ink and sparse purple accents.
    for y in range(picture.height):
        for x in range(picture.width):
            r,g,b,a=pix[x,y]
            lo=min(r,g,b)
            if lo>=248:
                a=0
            elif lo>=224 and max(r,g,b)-lo<23:
                a=max(0,min(255,int((248-lo)/24*255)))
            pix[x,y]=(r,g,b,a)
    return picture

def quality_gate(picture:Image.Image)->dict:
    img=picture.convert("RGB").resize((128,128))
    pts=list(img.getdata())
    white=sum(1 for p in pts if min(p)>=231)/len(pts)
    black=sum(1 for p in pts if max(p)<112)/len(pts)
    # Reject black-panel images, invisible empty outputs or gray photograph.
    ok=(.37<=white<=.992 and .002<=black<=.27)
    return {"white_background_fraction":round(white,3),
            "ink_fraction":round(black,3),
            "basic_visual_gate":"PASS" if ok else "FAIL"}

def render_story_ai(story,output=OUTPUT):
    import torch
    from diffusers import StableDiffusionImg2ImgPipeline,EulerDiscreteScheduler
    scenes=image_scenes(story)[:CAP_SCENES]
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    report={"status":"PREVIEW_ONLY","real_model":MODEL,"license":LICENSE,
            "scenes":scenes,"records":[],"image_api_calls":0,
            "draft_count":0,"published":0}
    if not scenes:
        report["status"]="NO_SCENES"
        return report
    start=time.monotonic()
    pipe=None
    error=None
    try:
        torch.set_num_threads(min(8,os.cpu_count() or 4))
        pipe=StableDiffusionImg2ImgPipeline.from_pretrained(
            MODEL,torch_dtype=torch.float32,use_safetensors=True,
            variant="fp16",safety_checker=None,requires_safety_checker=False)
        pipe.scheduler=EulerDiscreteScheduler.from_config(pipe.scheduler.config)
        pipe=pipe.to("cpu")
        pipe.set_progress_bar_config(disable=True)
    except Exception as exc:
        error="LOCAL_MODEL_LOAD_"+type(exc).__name__
    for index,scene in enumerate(scenes):
        idea=image_metaphor(story,scene)
        path=output/f"scene_{scene:02d}.png"
        seed=output/f"seed_{scene:02d}.png"
        ink_sketch(scene,idea,seed)
        row={"scene":scene,"model_attempted":pipe is not None,
             "prompt_meaning":editorial_english_motif(idea,story.get("topic","")),
             "image_path":path.name}
        if pipe is not None:
            try:
                with Image.open(seed) as original:
                    paper=Image.new("RGB",original.size,(255,255,255))
                    paper.paste(original,mask=original.getchannel("A"))
                paper=ImageOps.fit(paper,(512,512),method=Image.Resampling.LANCZOS)
                generated=pipe(
                    original_prompt(idea,str(story.get("topic",""))),
                    negative_prompt=NEGATIVE,image=paper,
                    num_inference_steps=16,strength=0.38,
                    guidance_scale=6.5,
                    generator=torch.Generator(device="cpu").manual_seed(23100+scene*317)
                ).images[0]
                assessment=quality_gate(generated)
                row.update(assessment)
                if assessment["basic_visual_gate"]=="PASS":
                    matte_white_to_alpha(generated).save(path,optimize=True)
                    row["status"]="GENUINE_LOCAL_MODEL_ILLUSTRATION"
                    row["human_visual_review_required"]=True
                else:
                    ink_sketch(scene,idea,path)
                    row["status"]="ORIGINAL_CONCEPT_FALLBACK_REJECTED_AI_QA"
            except Exception as exc:
                ink_sketch(scene,idea,path)
                row["status"]="ORIGINAL_CONCEPT_FALLBACK_MODEL_"+type(exc).__name__
        else:
            ink_sketch(scene,idea,path)
            row["status"]="ORIGINAL_CONCEPT_FALLBACK_"+str(error)
        report["records"].append(row)
    report["ai_generated_images"]=sum(x["status"]=="GENUINE_LOCAL_MODEL_ILLUSTRATION" for x in report["records"])
    report["procedural_images"]=len(report["records"])-report["ai_generated_images"]
    report["duration_seconds"]=round(time.monotonic()-start,1)
    report["status"]="ART_IMAGES_SAVED_REQUIRE_HUMAN_REVIEW"
    (output/"daily_true_model_provenance.json").write_text(
       json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("DAILY_TRUE_MODEL_ART "+json.dumps({
      "ai_generated_images":report["ai_generated_images"],
      "procedural_images":report["procedural_images"],
      "scenes":scenes,"publication":"NEVER"},ensure_ascii=False))
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--story-json",type=Path,required=True)
    ap.add_argument("--output",type=Path,default=OUTPUT)
    args=ap.parse_args()
    story=json.loads(args.story_json.read_text(encoding="utf-8"))
    render_story_ai(story,args.output)
    return 0
if __name__=="__main__":
    raise SystemExit(main())
