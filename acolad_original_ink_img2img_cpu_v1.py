#!/usr/bin/env python3
"""CPU real image-to-image model conditioned on simple original line-art sketch.
Source: Acolad's own procedural concept, enhanced by a real diffusion checkpoint.
No copyrighted artist replication, no image API costs, no publish.
"""
import argparse,json,os,time
from pathlib import Path
from PIL import Image,ImageOps
from acolad_concept_art_pipeline_v2 import ink_sketch

MODEL="nota-ai/bk-sdm-tiny"
OUTPUT=Path("acolad_original_ink_img2img_output")
PROMPT=("Original minimalist black ink sketch cartoon. One confused customer "
        "standing beside a huge padlock and a locked door to an online store. "
        "Clever amusing visual metaphor, handdrawn with sparse uneven ink strokes "
        "on clean white paper, simple expressive person, no text, little detail.")
NEGATIVE=("interior scene, elaborate buildings, clutter, shop signage, letters, "
          "numbers, typography, watermarks, gradients, photorealism, 3D, black background")
def go(output=OUTPUT):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    state={"status":"NOT_STARTED","model":MODEL,"model_license":"creativeml-openrail-m",
           "genuine_model_image":False,"image_api_requests":0,"published":0,"drafted":0}
    start=time.monotonic()
    try:
        import torch
        from diffusers import StableDiffusionImg2ImgPipeline,EulerDiscreteScheduler
        torch.set_num_threads(min(8,os.cpu_count() or 4))
        seed=out/"original_seed.png"
        ink_sketch(3,"کلید بزرگ پشت پرده و در قفل‌شده فروشگاه",seed)
        with Image.open(seed) as alpha:
            original=Image.new("RGB",alpha.size,(255,255,255))
            original.paste(alpha,mask=alpha.getchannel("A"))
        original=ImageOps.fit(original,(512,512),method=Image.Resampling.LANCZOS)
        state["status"]="LOADING_REAL_CPU_DIFFUSION"
        pipe=StableDiffusionImg2ImgPipeline.from_pretrained(
           MODEL,torch_dtype=torch.float32,use_safetensors=True,variant="fp16",
           safety_checker=None,requires_safety_checker=False)
        pipe.scheduler=EulerDiscreteScheduler.from_config(pipe.scheduler.config)
        pipe=pipe.to("cpu")
        pipe.set_progress_bar_config(disable=True)
        image=pipe(PROMPT,negative_prompt=NEGATIVE,image=original,
           num_inference_steps=16,strength=0.38,guidance_scale=6.5,
           generator=torch.Generator(device="cpu").manual_seed(25671)).images[0]
        if image.width<512:raise RuntimeError("Too low resolution")
        result=out/"original_ink_diffusion_01.png"
        image.save(result,optimize=True)
        state.update({"status":"GENUINE_IMG2IMG_MODEL_SAVED","genuine_model_image":True,
                      "image_file":result.name,"size":[image.width,image.height],
                      "source":"original procedural Acolad drawing",
                      "human_editorial_review_required":True})
    except Exception as exc:
        state.update({"status":"IMG2IMG_ERROR_"+type(exc).__name__,
                      "error_type":type(exc).__name__,
                      "error_summary":str(exc).split("\n")[0][:220]})
    finally:
        state["seconds"]=round(time.monotonic()-start,1)
        (out/"receipt.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf8")
        print("TRUE_IMG2IMG "+json.dumps(state,ensure_ascii=False))
    return state

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=OUTPUT)
    args=parser.parse_args()
    r=go(args.output)
    raise SystemExit(0 if r["genuine_model_image"] else 2)
