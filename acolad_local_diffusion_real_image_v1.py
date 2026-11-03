#!/usr/bin/env python3
"""CPU-only REAL diffusion inference on GitHub runner, with original artwork prompt.

Uses a publicly downloadable open-weight model under CreativeML OpenRAIL-M.
No external image generation API keys, no publication.
One attempt, diagnostic report, no invented success if download/inference fails.
"""
import argparse
import json
import os
from pathlib import Path
import time

MODEL="segmind/tiny-sd"
OUTPUT=Path("acolad_local_real_diffusion_output")
LICENSE="creativeml-openrail-m"
PROMPT=(
 "single original whimsical conceptual editorial cartoon, bold rough black ink pen sketch "
 "on a blank pure white paper background, small expressive tired online shopper trying to "
 "walk through a huge locked doorway that blocks an easy purchase, giant padlock and tiny "
 "keyhole, visual metaphor for forced account registration in an online store, "
 "minimal charming sparse hand-drawn uneven linework, slightly absurd funny scene, "
 "simple clear idea, lots of negative space, no colors, two dimensional, "
 "original children's picture book illustration for grownups, no text or logos"
)
NEGATIVE=(
 "photorealistic, hyperrealistic, 3d render, gradients, shiny, glossy, busy, "
 "realistic skin, intricate background, multiple panels, infographic, writing, "
 "letters, words, captions, signature, watermark, copyrighted characters"
)

def run(output=OUTPUT, steps=10):
    output.mkdir(parents=True,exist_ok=True)
    report={"model":MODEL,"model_license":LICENSE,"status":"NOT_STARTED",
            "api_image_requests":0,"real_model_generated":False,
            "published":0,"drafted":0,"queued":0}
    start=time.monotonic()
    try:
        import torch
        from diffusers import StableDiffusionPipeline, EulerDiscreteScheduler
        torch.set_num_threads(min(8,os.cpu_count() or 4))
        report["device"]="cpu"
        report["status"]="MODEL_LOADING"
        pipeline=StableDiffusionPipeline.from_pretrained(
            MODEL,torch_dtype=torch.float32,use_safetensors=True,
            safety_checker=None,requires_safety_checker=False)
        pipeline.scheduler=EulerDiscreteScheduler.from_config(pipeline.scheduler.config)
        pipeline=pipeline.to("cpu")
        pipeline.set_progress_bar_config(disable=True)
        result=pipeline(
            PROMPT,negative_prompt=NEGATIVE,
            num_inference_steps=steps,guidance_scale=7.0,
            height=384,width=384,
            generator=torch.Generator(device="cpu").manual_seed(12485))
        picture=result.images[0]
        if picture.size!=(384,384):raise RuntimeError("Unexpected picture size")
        dest=output/"original_diffusion_01.png"
        picture.convert("RGB").save(dest,optimize=True)
        report.update({"status":"REAL_LOCAL_DIFFUSION_IMAGE_SAVED",
                       "image_file":dest.name,"size":[384,384],
                       "real_model_generated":True,"model_inference_steps":steps,
                       "no_named_artist_imitation":True,
                       "human_visual_quality_review_required":True})
    except Exception as exc:
        report.update({"status":"LOCAL_DIFFUSION_ERROR_"+type(exc).__name__,
                       "error_class":type(exc).__name__,
                       "error_note":str(exc)[:300].replace("\n"," ")})
    finally:
        report["duration_sec"]=round(time.monotonic()-start,1)
        (output/"inference_receipt.json").write_text(
            json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
        print("REAL_DIFFUSION "+json.dumps(report,ensure_ascii=False))
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=OUTPUT)
    parser.add_argument("--steps",type=int,default=10)
    args=parser.parse_args()
    if not 5<=args.steps<=20:raise SystemExit("steps out of bounds")
    status=run(args.output,args.steps)
    raise SystemExit(0 if status["real_model_generated"] else 2)
