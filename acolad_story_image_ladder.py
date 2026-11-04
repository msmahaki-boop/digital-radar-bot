#!/usr/bin/env python3
"""Acolad editorial visual ladder. GPT Image 2 -> Gemini 2.5 -> Qwen -> licensed stock -> no image.
Only two illustrations for five-slide daily sequence. No publishing or posting APIs.
"""
from __future__ import annotations
import base64,io,json,os,re
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image,ImageOps,ImageStat,UnidentifiedImageError

BASE="https://api.gapgpt.app/v1"
MODELS=("gpt-image-2","gemini-2.5-flash-image","gapgpt/qwen-image-2.1")
PHOTO_POSITIONS=(0,2)  # 1 intro + 4 stories => visual on slides 2 and 4 only.
OUTPUT=Path("acolad_visual_provenance")
BLOCKED=("127.","10.","192.168.","169.254.","localhost","0.0.0.0")

def prompt(story):
    title=str(story.title_fa or "")[:130]
    article=str(story.original_title or "")[:190]
    summary=str(story.summary_fa or "")[:430]
    if len(title)<12 or len(article)<12:raise ValueError("Unverified article title")
    return ("Create ONE independent, ORIGINAL editorial pen-and-ink drawing for a Persian "
            "digital-growth news story, conceptual rather than documentary. "
            "Actual verified topic: "+article+". Persian newsroom headline: "+title+
            ". Context (do not invent claims): "+summary+". "
            "A witty unexpected visual metaphor that clearly reflects THIS topic, "
            "one expressive small figure and one oversized metaphorical everyday object. "
            "Restrained charming literary line drawing, confidently uneven black ink, "
            "minimal hatching, one tiny lavender accent, warm paper-white background, "
            "at least 75% uncluttered space, recognizable objects, clean visual hierarchy. "
            "No lettering, fake charts, screens, UI, text, numbers, watermarks, logos, "
            "busy backgrounds, photorealism, or copying any named illustrator. "
            "Avoid implying that the drawing depicts an actual reported event.")

def check_image(raw):
    if not raw or len(raw)>18_000_000:raise ValueError("invalid file bytes")
    with Image.open(io.BytesIO(raw)) as im:
        if im.format not in ("PNG","JPEG","WEBP"):raise ValueError("invalid image format")
        im.verify()
    with Image.open(io.BytesIO(raw)) as im:
        if min(im.size)<512 or max(im.size)>4096:raise ValueError("image dimensions")
        img=ImageOps.exif_transpose(im).convert("RGB").copy()
    extrema=ImageStat.Stat(img.resize((64,64))).stddev
    if max(extrema)<4:raise ValueError("blank image")
    return img

def read_image_json(obj,session=requests):
    arr=obj.get("data") if isinstance(obj,dict) else None
    if not isinstance(arr,list) or not arr or not isinstance(arr[0],dict):
        raise ValueError("missing image data")
    row=arr[0]
    if isinstance(row.get("b64_json"),str):
        return check_image(base64.b64decode(row["b64_json"],validate=True)),"b64_json"
    uri=row.get("url")
    if not isinstance(uri,str):raise ValueError("no valid media URL")
    p=urlparse(uri)
    if p.scheme!="https" or not p.hostname or p.username or p.password:raise ValueError("unsafe media URL")
    host=p.hostname.lower()
    if any(host.startswith(s) for s in BLOCKED) or host.endswith((".local",".internal")):
        raise ValueError("private network URL")
    r=session.get(uri,timeout=65,allow_redirects=False)
    if r.status_code!=200:raise ValueError("media download error")
    return check_image(r.content),"url"

def attempt(story,model,session=requests):
    key=os.getenv("GAPGPT_API_KEY","").strip()
    if not key:return None,{"model":model,"status":"GAPGPT_KEY_MISSING"}
    try:
        body={"model":model,"prompt":prompt(story),"size":"1024x1024"}
        r=session.post(BASE+"/images/generations",
            headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},
            json=body,timeout=170)
        if r.status_code!=200:return None,{"model":model,"status":"API_HTTP_ERROR","http_status":r.status_code}
        image,kind=read_image_json(r.json(),session)
        return image,{"model":model,"status":"VALID_IMAGE","response_format":kind,"dimensions":list(image.size)}
    except (ValueError,OSError,requests.RequestException,UnidentifiedImageError,TypeError) as exc:
        return None,{"model":model,"status":"INVALID_IMAGE_"+type(exc).__name__}

def safe_stock(story,session=requests):
    """Pexels search only when secret exists. No misleading 'photo of event' claims."""
    key=os.getenv("PEXELS_API_KEY","").strip()
    if not key:return None,{"status":"NO_LICENSED_STOCK_CREDENTIAL"}
    # Search terms from actual source title, not generic 'business art'.
    tokens=re.findall(r"[A-Za-z][a-zA-Z-]{3,}",str(story.original_title))
    terms=[t for t in tokens if t.lower() not in {"that","from","with","this","after","about","their","today","could","more","will","have"}][:5]
    if len(terms)<2:return None,{"status":"STOCK_QUERY_INSUFFICIENT"}
    query=" ".join(terms)
    try:
        r=session.get("https://api.pexels.com/v1/search",params={"query":query,"per_page":5},
            headers={"Authorization":key},timeout=25)
        if r.status_code!=200:return None,{"status":"STOCK_SEARCH_HTTP_ERROR","http_status":r.status_code}
        for item in (r.json().get("photos") or [])[:5]:
            alt=str(item.get("alt") or "").lower()
            # Require at least two semantic terms in the source-supplied metadata.
            hits=sum(bool(re.search(r"\b"+re.escape(t.lower())+r"\b",alt)) for t in terms)
            if hits<2:continue
            url=(item.get("src") or {}).get("large2x","")
            if not isinstance(url,str) or not url.startswith("https://images.pexels.com/"):continue
            res=session.get(url,timeout=50,allow_redirects=False)
            if res.status_code!=200:continue
            return check_image(res.content),{"status":"LICENSED_STOCK_CANDIDATE",
                   "provider":"Pexels","source_url":item.get("url"),"photo_id":item.get("id"),
                   "photographer":item.get("photographer"),"alt":item.get("alt"),
                   "license_url":"https://www.pexels.com/license/",
                   "note":"Conceptual stock only, not actual news-event evidence"}
        return None,{"status":"NO_SEMANTIC_STOCK_MATCH"}
    except (ValueError,OSError,requests.RequestException,TypeError) as exc:
        return None,{"status":"STOCK_ERROR_"+type(exc).__name__}

def commons_stock(story,session=requests):
    """Open-license Wikimedia stock fallback; only semantic and CC0/public domain matches."""
    words=re.findall(r"[A-Za-z][a-zA-Z-]{3,}",str(story.original_title))
    skip={"that","from","with","this","after","about","their","today","could","more","will","have"}
    terms=[w.lower() for w in words if w.lower() not in skip][:5]
    if len(terms)<2:return None,{"status":"COMMONS_NO_QUERY"}
    try:
        r=session.get("https://commons.wikimedia.org/w/api.php",
            params={"action":"query","generator":"search",
                    "gsrsearch":"filetype:bitmap "+" ".join(terms),
                    "gsrnamespace":6,"gsrlimit":6,"prop":"imageinfo",
                    "iiprop":"url|extmetadata","iiurlwidth":1200,"format":"json"},
            headers={"User-Agent":"AcoladNewsEditorial/1.0 (https://acolad.ir)"},
            timeout=30)
        if r.status_code!=200:return None,{"status":"COMMONS_SEARCH_HTTP","http_status":r.status_code}
        pages=(r.json().get("query") or {}).get("pages") or {}
        for page in pages.values():
            title=str(page.get("title") or "").lower()
            ii=(page.get("imageinfo") or [])
            if not ii:continue
            info=ii[0];meta=info.get("extmetadata") or {}
            license_name=str((meta.get("LicenseShortName") or {}).get("value") or "").lower()
            if not ("cc0" in license_name or "public domain" in license_name or "pd-" in license_name):
                continue
            description=re.sub(r"<[^>]+>"," ",str((meta.get("ImageDescription") or {}).get("value") or "")).lower()
            hay=title+" "+description
            if sum(1 for t in terms if t in hay)<2:continue
            url=info.get("thumburl") or info.get("url")
            if not isinstance(url,str) or not url.startswith("https://upload.wikimedia.org/"):continue
            photo=session.get(url,headers={"User-Agent":"AcoladNewsEditorial/1.0"},
                              timeout=45,allow_redirects=False)
            if photo.status_code!=200:continue
            return check_image(photo.content),{"status":"PUBLIC_DOMAIN_STOCK_CANDIDATE",
                    "provider":"Wikimedia Commons","title":page.get("title"),
                    "source_url":info.get("descriptionurl"),
                    "license":license_name,
                    "note":"Illustrative stock, not evidence of this news event"}
        return None,{"status":"COMMONS_NO_RELEVANT_PD_MATCH"}
    except (ValueError,OSError,requests.RequestException,TypeError,AttributeError) as exc:
        return None,{"status":"COMMONS_ERROR_"+type(exc).__name__}

def enrich_images(stories,session=requests,allow_billable=True):
    """Only images for stories 0 and 2; other two are text-only. Never publish."""
    OUTPUT.mkdir(parents=True,exist_ok=True)
    records=[]
    for i,story in enumerate(stories):
        story.image=None
        story.image_status="TEXT_ONLY_POSITION"
        if i not in PHOTO_POSITIONS:
            records.append({"slide":i+2,"status":"TEXT_ONLY_CADENCE"});continue
        attempts=[]
        image=None
        if allow_billable:
            for model in MODELS:
                image,res=attempt(story,model,session)
                attempts.append(res)
                if image is not None:break
        if image is None:
            image,stock=safe_stock(story,session)
            attempts.append(stock)
        if image is None:
            image,commons=commons_stock(story,session)
            attempts.append(commons)
        if image is None:
            story.image_status="TEXT_ONLY_NO_RELEVANT_IMAGE"
            status="TEXT_ONLY"
        else:
            story.image=image
            story.image_status="AI_GENERATED" if any(x.get("status")=="VALID_IMAGE" for x in attempts) else "LICENSED_STOCK"
            status=story.image_status
        records.append({"slide":i+2,"topic":story.topic,"image_status":status,"attempts":attempts})
    report={"state":"IMAGE_PREVIEW_NEEDS_HUMAN_REVIEW","publication":"NEVER","max_photo_slides":2,
            "images_used":sum(x.image is not None for x in stories),"records":records}
    (OUTPUT/"provenance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ACOLAD_IMAGE_LADDER "+json.dumps(report,ensure_ascii=False),flush=True)
    return report
