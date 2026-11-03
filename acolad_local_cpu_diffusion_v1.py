#!/usr/bin/env python3
"""One real local diffusion image on GitHub Actions CPU, independent of API quotas.

Uses a pinned third-party OpenRAIL checkpoint; downloads model bytes on runner
only; never commits weights or customer secrets. Human quality approval needed.
"""
from pathlib import Path
import argparse
import json
import os
import time
from PIL import Image, ImageOps, ImageFilter

MODEL="segmind/tiny-sd"
REVISION="67b0d28ff1c11ce1002b2ce6377f1c1eda02d779"
LICENSE="creativeml-openrail-m"
OUT=Path("acolad_local_diffusion_output")
def run(output=OUT):
    started=time.monotonic()
    output.mkdir(parents=True,exist_ok=True)
    status={"provider":"GitHub Actions CPU inference","model":MODEL,"revision":REVISION,
            "license":LICENSE,"status":"NOT_STARTED","real_model_generated":False,
            "brand_approved":False,"published":False}
    try:
        import torch
        from diffusers import StableDiffusionImg2ImgPipeline
        from acolad_concept_art_pipeline_v2 import ink_sketch
        torch.set_num_threads(2)
        status["status"]="MODEL_DOWNLOAD_ATTEMPT"
        pipe=StableDiffusionImg2ImgPipeline.from_pretrained(
            MODEL,revision=REVISION,torch_dtype=torch.float32,
            use_safetensors=True,safety_checker=None,requires_safety_checker=False)
        pipe=pipe.to("cpu")
        pipe.enable_attention_slicing()
        status["status"]="LOCAL_INFERENCE_ATTEMPT"
        # Draw the real narrative symbol first, then let the pretrained
        # diffusion model add hand-drawn irregularity without losing the plot.
        concept="a tiny shopkeeper, an oversized padlock and a hidden key"
        guide_path=output/"concept_guidance_source.png"
        ink_sketch(2,"قفل بزرگ خرید و آدم کوچک کنار در",guide_path)
        with Image.open(guide_path) as outline:
            sketch=outline.convert("RGBA")
            white=Image.new("RGBA",sketch.size,(255,254,251,255))
            white.alpha_composite(sketch)
            guide=white.convert("RGB").resize((384,384),Image.Resampling.LANCZOS)
        guide.save(output/"guidance_white.png")
        prompt=(
         "whimsical original pen-and-ink editorial cartoon on plain white paper, "
         "one small puzzled shopkeeper beside a single comically oversized padlock, "
         "a tiny key is hidden nearby, silly absurd metaphor for blocked online checkout, "
         "clean sparse hand-drawn black lines, quirky uneven pen strokes, "
         "funny expressive person, one visual idea, lots of empty space, "
         "delicate warm paper and one lilac accent. No letters or captions."
        )
        negative=(
          "photograph, realistic architecture, building, balcony, gate, fence, bars, "
          "3d, glossy, anime, manga, typography, logo, signature, watermark, "
          "text, clutter, multiple panels, shadow gradients"
        )
        g=torch.Generator(device="cpu").manual_seed(20261104)
        raw=pipe(prompt=prompt,negative_prompt=negative,image=guide,
                 strength=.51,num_inference_steps=16,guidance_scale=7,
                 generator=g).images[0]
        raw.save(output/"model_raw.png")
        # Preserve original model generation AND provide a separate editable
        # pen-line interpretation with transparent paper, no synthetic subjects.
        gray=ImageOps.grayscale(raw).filter(ImageFilter.GaussianBlur(.5))
        contour=ImageOps.invert(gray.filter(ImageFilter.FIND_EDGES))
        contour=ImageOps.autocontrast(contour,cutoff=2)
        ink=Image.new("RGBA",raw.size,(25,23,29,0))
        ink.putalpha(ImageOps.invert(contour).point(lambda x:max(0,min(255,(x-40)*3))))
        ink=ink.resize((768,768),Image.Resampling.LANCZOS)
        ink.save(output/"model_ink_on_transparent.png",optimize=True)
        status.update({"status":"REAL_LOCAL_DIFFUSION_IMAGE_GENERATED",
                       "real_model_generated":True,
                       "source_image":"model_raw.png",
                       "edited_image":"model_ink_on_transparent.png",
                       "resolution":[768,768],
                       "human_quality_review_required":True})
        return status
    except Exception as exc:
        status["status"]="LOCAL_MODEL_FAILURE_"+type(exc).__name__
        status["failure_category"]=type(exc).__name__
        return status
    finally:
        status["elapsed_seconds"]=round(time.monotonic()-started,1)
        (output/"local_model_status.json").write_text(
             json.dumps(status,ensure_ascii=False,indent=2),encoding="utf8")
        print("LOCAL_DIFFUSION_RESULT "+json.dumps(status,ensure_ascii=False))
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,default=OUT)
    x=p.parse_args()
    report=run(x.output)
    return 0 if report["real_model_generated"] else 2
if __name__=="__main__":raise SystemExit(main())
