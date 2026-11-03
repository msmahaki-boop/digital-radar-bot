#!/usr/bin/env python3
"""Best-effort REAL IMAGE generation on legacy Pollinations anonymous endpoint.

Not guaranteed; official new API requires a secret key. One request maximum,
validate bytes and copyright/watermark visually before using any final art.
"""
from pathlib import Path
import io
import json
import time
import requests
from PIL import Image
from urllib.parse import quote
from acolad_horde_real_image_v1 import prompt_for

OUT=Path("acolad_pollinations_real_image_output")
HOST="https://image.pollinations.ai"
def run(visual,topic,output=OUT,session=requests):
    output.mkdir(parents=True,exist_ok=True)
    result={"provider":"Pollinations legacy anonymous image",
            "status":"NOT_REQUESTED","real_ai_image":False,
            "requests_sent":0,"cost_toman":0,"published":0,
            "note":"Legacy endpoint may require auth/charge; do not retry failures."}
    start=time.monotonic()
    try:
        text=prompt_for(visual,topic).split("###")[0].strip()
        # One 768 image only, no accidental repeat or escalation.
        url=HOST+"/prompt/"+quote(text[:580],safe="")
        result["requests_sent"]=1
        response=session.get(url,params={
           "width":"768","height":"768","seed":"541108",
           "nologo":"true"},timeout=65,allow_redirects=False)
        result["http_status"]=response.status_code
        if response.status_code!=200:
            result["status"]="HTTP_"+str(response.status_code)
            return result
        mime=response.headers.get("Content-Type","").split(";")[0].lower()
        if mime not in ("image/png","image/jpeg","image/webp"):
            result["status"]="NOT_IMAGE_CONTENT_TYPE";return result
        raw=response.content
        if len(raw)>16_000_000:raise ValueError("max 16MB")
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            if im.width<512 or im.height<512:raise ValueError("image too small")
            bitmap=im.convert("RGBA")
        dest=output/"pollinations_original_01.png"
        bitmap.save(dest,optimize=True)
        result.update({"status":"REAL_AI_IMAGE_SAVED","real_ai_image":True,
                       "image_file":dest.name,"size":list(bitmap.size),
                       "human_review_required":True})
        return result
    except (requests.RequestException,ValueError,OSError) as e:
        result["status"]="ERROR_"+type(e).__name__
        return result
    finally:
        result["duration_seconds"]=round(time.monotonic()-start,2)
        (output/"pollinations_receipt.json").write_text(
            json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
        print("POLLINATIONS_RESULT "+json.dumps(result,ensure_ascii=False))
