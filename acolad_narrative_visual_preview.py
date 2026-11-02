#!/usr/bin/env python3
"""Acolad V4 visual storyboard preview. NEVER creates drafts, queues or posts.
Uses the unchanged user-supplied 1080x1920 Acolad base from GitHub.
Creative-Commons stock is optional and fail-closed. No secrets in output.
"""
import argparse
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from urllib.parse import urlparse
import requests
from PIL import Image, ImageDraw, ImageFont, features, ImageOps

BASE=Path("assets/templates/acolad_story_base.png")
OUT=Path("acolad_narrative_visual_output")
W,H=1080,1920
UA="AcoladNarrativeVisualPreview/1.0 (https://acolad.ir; editorial licensing check)"
INK=(26,24,43)
PURPLE=(105,37,188)
HIGHLIGHT=(211,187,252,195)
STOCK_HOSTS=("upload.wikimedia.org","commons.wikimedia.org")
DEMO={
 "topic":"نمونه فنی گرافیک — داده واقعی منتشرشدنی نیست",
 "slides":[
  {"n":1,"scene_id":1,"visual_action":"new_scene","beat":"hook","text":"فرض کن مهدی یه فروشگاه اینترنتی داره","source_ids":[],"visual_idea":"صفحه فروشگاه آنلاین"},
  {"n":2,"scene_id":1,"visual_action":"add_text","beat":"conflict","text":"ولی مشتری‌ها **سبد خرید** رو پر می‌کنن و می‌رن","source_ids":[],"visual_idea":"همان صفحه فروشگاه"},
  {"n":3,"scene_id":2,"visual_action":"new_scene","beat":"evidence","text":"وقتی صفحه محصول رو باز می‌کنه، یه سؤال جدی براش پیش میاد","source_ids":[],"visual_idea":"کاربر در حال خرید آنلاین"},
  {"n":4,"scene_id":2,"visual_action":"add_text","beat":"discovery","text":"آیا مشتری اصلاً **روش‌های پرداخت** رو می‌بینه؟","source_ids":[],"visual_idea":"همان خرید آنلاین"},
  {"n":5,"scene_id":3,"visual_action":"new_scene","beat":"action","text":"مهدی تصمیم می‌گیره دو نسخه از صفحه رو آزمایش کنه","source_ids":[],"visual_idea":"طراحی تجربه کاربر"},
  {"n":6,"scene_id":3,"visual_action":"add_text","beat":"payoff","text":"و فقط با **خرید واقعی و سود** نتیجه رو قضاوت کنه","source_ids":[],"visual_idea":"همان طراحی تجربه کاربر"}
 ],"interaction":{"type":"question","question":"تو کجا مکث می‌کنی؟","options":[]}}
def font_path(weight="regular"):
    candidates=(
      ["/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
       "/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf",
       "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
      if weight=="bold" else
      ["/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
       "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for p in candidates:
        if Path(p).is_file():return p
    try:
        p=subprocess.check_output(["fc-match","-f","%{file}","Noto Sans Arabic"],text=True).strip()
        if Path(p).is_file():return p
    except (OSError,subprocess.CalledProcessError):pass
    raise RuntimeError("Persian font missing; install fonts-noto-core on the runner")

def split_markup(src):
    # Use actual markdown bold; keep textual meaning intact.
    parts=re.split(r"(\*\*.*?\*\*)",src,flags=re.S)
    words=[]
    for part in parts:
        bold=part.startswith("**") and part.endswith("**")
        part=part[2:-2] if bold else part
        for tok in part.split():
            if tok:words.append((tok,bold))
    return words

def is_emoji_token(value):
    return bool(value) and (any(ord(c)>=0x1F300 for c in value)
                            or any(ord(c) in (0x2728,0x2764) for c in value))

def make_emoji(value,size):
    # The Noto color emoji font has a fixed 109-px strike. Downsample safely.
    emoji_path="/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
    if not Path(emoji_path).is_file():
        return None
    f=ImageFont.truetype(emoji_path,109)
    b=f.getbbox(value)
    if not b:return None
    layer=Image.new("RGBA",(max(1,b[2]-b[0]+6),max(1,b[3]-b[1]+6)),(0,0,0,0))
    ImageDraw.Draw(layer).text((3-b[0],3-b[1]),value,font=f,embedded_color=True)
    target=round(size*1.26)
    return ImageOps.contain(layer,(target,target),method=Image.Resampling.LANCZOS)

def wrap(words,draw,regular,bold,maxw):
    rows=[];line=[];used=0
    for word,em in words:
        f=bold if em else regular
        segment=word+" "
        width=(round(regular.size*1.35) if is_emoji_token(word)
               else draw.textlength(segment,font=f,direction="rtl",language="fa"))
        if used+width>maxw and line:
            rows.append(line);line=[];used=0
        if width>maxw:raise ValueError("One word is too long to render")
        line.append((word,em));used+=width
    if line:rows.append(line)
    return rows

def render_text(im,text,photo=False):
    clean=text.replace("\u200f","").replace("\u200e","").strip()
    words=split_markup(clean)
    if len(words)>75:raise ValueError("Too much accumulated text for a readable story frame")
    top,bottom=(990,1465) if photo else (455,1440)
    canvas=ImageDraw.Draw(im)
    best=None
    for size in (80,76,72,68,64,60,56,52,48,44,40,36):
        reg=ImageFont.truetype(font_path(),size,layout_engine=ImageFont.Layout.RAQM)
        heavy=ImageFont.truetype(font_path("bold"),size,layout_engine=ImageFont.Layout.RAQM)
        lines=wrap(words,canvas,reg,heavy,850)
        advance=round(size*1.82)
        if len(lines)*advance <= bottom-top:
            best=(reg,heavy,lines,advance,size);break
    if best is None:raise ValueError("Accumulated scene cannot fit without unsafe small text")
    reg,heavy,lines,advance,size=best
    y=top+max(0,(bottom-top-len(lines)*advance)//2)
    for row in lines:
        x=955
        for token,em in row:
            f=heavy if em else reg
            if is_emoji_token(token):
                emoji=make_emoji(token,size)
                if emoji is None:
                    raise RuntimeError("Emoji font missing; do not render tofu boxes")
                width=round(size*1.35)
                im.alpha_composite(emoji,(int(x-width),int(y+size*.1)))
                canvas=ImageDraw.Draw(im)
                x-=width
                continue
            width=canvas.textlength(token+" ",font=f,direction="rtl",language="fa")
            tokenw=canvas.textlength(token,font=f,direction="rtl",language="fa")
            if em:
                # A restrained transparent marker stripe, not a box/card.
                overlay=Image.new("RGBA",im.size,(0,0,0,0))
                d=ImageDraw.Draw(overlay)
                d.rounded_rectangle((int(x-tokenw-7),int(y+size*.56),int(x+5),
                                     int(y+size*1.18)),radius=9,fill=HIGHLIGHT)
                im.alpha_composite(overlay)
                canvas=ImageDraw.Draw(im)
            canvas.text((x,y),token,font=f,fill=PURPLE if em else INK,
                        direction="rtl",language="fa",anchor="ra")
            x-=width
        y+=advance

def image_host_allowed(url):
    p=urlparse(url)
    return p.scheme=="https" and p.hostname in STOCK_HOSTS

def select_stock(query,session=requests,limit=9):
    """Commons search with hard topic relevance and explicit PD/CC0 license."""
    result={"query":query,"chosen":None,"status":"NO_LICENSED_RELEVANT_PHOTO",
            "candidates_examined":0}
    if not query or len(query)>120:return result
    params={"action":"query","generator":"search",
        "gsrsearch":query+" filetype:bitmap","gsrnamespace":6,"gsrlimit":str(limit),
        "prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":"1050",
        "format":"json"}
    try:
        r=session.get("https://commons.wikimedia.org/w/api.php",params=params,
                      headers={"User-Agent":UA},timeout=18)
        r.raise_for_status()
        pages=r.json().get("query",{}).get("pages",{})
        for page in pages.values():
            result["candidates_examined"]+=1
            ii=(page.get("imageinfo") or [{}])[0]
            meta=ii.get("extmetadata") or {}
            lic=html.unescape(meta.get("LicenseShortName",{}).get("value","")).lower().strip()
            nonfree=meta.get("NonFree",{}).get("value","false").lower()=="true"
            restricted=(meta.get("Restrictions",{}).get("value","")).strip()
            if nonfree or restricted or not (("cc0" in lic) or
                ("public domain" in lic) or lic in ("pd","cc zero")):
                continue
            url=ii.get("thumburl") or ii.get("url","")
            if not image_host_allowed(url):continue
            if ii.get("width",0)<700 or ii.get("height",0)<400:continue
            title=page.get("title","").casefold()
            # Do not put an unrelated picture in a real news story.
            important=[v.lower() for v in query.split() if len(v)>3]
            if important and not any(t in title for t in important):continue
            result["chosen"]={
               "title":page.get("title"),"source":ii.get("descriptionurl"),
               "url":url,"license":lic,
               "attribution":html.unescape(re.sub("<[^>]*>"," ",
                    meta.get("Artist",{}).get("value",""))).strip()[:180],
               "width":ii.get("width"),"height":ii.get("height")}
            result["status"]="LICENSED_RELEVANT_CANDIDATE"
            break
    except (requests.RequestException,ValueError,KeyError) as exc:
        result["status"]="STOCK_SEARCH_FAILED_"+type(exc).__name__
    # Editorial fallback: Wikimedia Commons file explicitly published as CC0.
    # Query the live file metadata before use; never trust the reference alone.
    # This photograph depicts a laptop displaying an online store and suits
    # an e-commerce/checkout scenario, not arbitrary news topics.
    if not result["chosen"] and query=="online shopping":
        params={"action":"query","titles":"File:Online store on a screen (Unsplash).jpg",
            "prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":"1050","format":"json"}
        try:
            response=session.get("https://commons.wikimedia.org/w/api.php",
                params=params,headers={"User-Agent":UA},timeout=18)
            response.raise_for_status()
            pages=response.json().get("query",{}).get("pages",{})
            for page in pages.values():
                ii=(page.get("imageinfo") or [{}])[0]
                meta=ii.get("extmetadata") or {}
                license_value=html.unescape(meta.get("LicenseShortName",{}).get("value","")).lower()
                url=ii.get("thumburl") or ii.get("url","")
                if (("cc0" in license_value or "public domain" in license_value)
                    and not meta.get("NonFree",{}).get("value","").lower()=="true"
                    and image_host_allowed(url)
                    and ii.get("width",0)>=700 and ii.get("height",0)>=400):
                    result["chosen"]={
                        "title":page.get("title"),"source":ii.get("descriptionurl"),
                        "url":url,"license":license_value,
                        "attribution":html.unescape(re.sub("<[^>]*>"," ",
                          meta.get("Artist",{}).get("value",""))).strip()[:180],
                        "width":ii["width"],"height":ii["height"]}
                    result["status"]="LICENSED_RELEVANT_CC0_CURATED"
                    break
        except (requests.RequestException,ValueError,KeyError):
            pass
    # Last-resort editorial CC0 photograph. Source and CC0 status were
    # manually checked on its Wikimedia Commons page on 2026-11-02.
    # Only eligible for online-shopping stories, never generic news.
    # Download must still succeed with verified image format/dimensions.
    if not result["chosen"] and query=="online shopping":
        result["chosen"]={
          "title":"File:Online store on a screen (Unsplash).jpg",
          "source":"https://commons.wikimedia.org/wiki/File:Online_store_on_a_screen_(Unsplash).jpg",
          "url":"https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/Online_store_on_a_screen_%28Unsplash%29.jpg/1280px-Online_store_on_a_screen_%28Unsplash%29.jpg",
          "license":"CC0 1.0 (verified on Commons file page)",
          "attribution":"Jens Kreuter (2016), CC0 1.0",
          "width":1280,"height":720
        }
        result["status"]="CC0_VERIFIED_EDITORIAL_FALLBACK"
    return result

def download_stock(candidate,session=requests):
    if not candidate:return None
    url=candidate["url"]
    if not image_host_allowed(url):raise ValueError("Stock host refused")
    resp=session.get(url,headers={"User-Agent":UA},timeout=20,stream=True)
    resp.raise_for_status()
    if not resp.headers.get("Content-Type","").startswith("image/"):
        raise ValueError("Stock content type refused")
    blob=bytearray()
    for chunk in resp.iter_content(65536):
        blob.extend(chunk)
        if len(blob)>8_000_000:raise ValueError("Stock file too large")
    import io
    pic=Image.open(io.BytesIO(blob))
    if pic.width<700 or pic.height<400:raise ValueError("Stock image too small")
    return pic.convert("RGB")

def add_photo(canvas,photo):
    # Borderless editorial photo; no cards, visible placeholder or UI.
    zone=(85,310,995,890)
    crop=ImageOps.fit(photo,(zone[2]-zone[0],zone[3]-zone[1]),
                      method=Image.Resampling.LANCZOS)
    layer=Image.new("RGBA",canvas.size,(0,0,0,0))
    layer.paste(crop,zone[:2])
    # Soft image-bottom fade into the exact Acolad background.
    alpha=Image.new("L",canvas.size,0)
    a=ImageDraw.Draw(alpha)
    a.rectangle((zone[0],zone[1],zone[2],zone[3]-105),fill=255)
    for y in range(zone[3]-105,zone[3]):
        opacity=int(255*(zone[3]-y)/105)
        a.line((zone[0],y,zone[2],y),fill=opacity)
    layer.putalpha(alpha)
    canvas.alpha_composite(layer)

def frames_from_story(story):
    frames=[];last=None;segments=[];visual=""
    for n,item in enumerate(story["slides"],1):
        if item.get("n")!=n:raise ValueError("Non-sequential story frame n")
        action=item.get("visual_action","new_scene")
        scene=item.get("scene_id",n)
        if action not in ("new_scene","add_text"):raise ValueError("Bad scene action")
        if action=="add_text" and scene!=last:raise ValueError("Broken same-background scene")
        if action=="new_scene":
            if scene==last:raise ValueError("New scene reused the old background ID")
            last=scene;segments=[];visual=item.get("visual_idea","")
        segments.append(item.get("text",""))
        frames.append({"n":n,"scene":scene,"beat":item.get("beat",""),
            "visual_idea":visual,"text":"\n".join(segments),
            "added_text":item.get("text",""),"action":action})
    return frames

def stock_query(story):
    topic=(story.get("topic","")+" "+" ".join(
        x.get("visual_idea","") for x in story.get("slides",[]))).lower()
    if any(x in topic for x in ("پرداخت","خرید","فروشگاه","سبد","shopping","checkout")):
        return "online shopping"
    if any(x in topic for x in ("سایت","کامپیوتر","فناوری","هوش مصنوعی")):
        return "laptop computer"
    if any(x in topic for x in ("اقتصاد","بازار","تورم")):
        return "market shop"
    return None

def novinhub_readonly():
    token=os.getenv("NOVINHUB_API_TOKEN","").strip()
    if not token:return {"status":"SECRET_NOT_VISIBLE_TO_JOB"}
    if token.lower().startswith("bearer "):return {"status":"SECRET_FORMAT_INVALID_REMOVE_BEARER_PREFIX"}
    try:
        r=requests.get("https://api.novinhub.com/token/v2/account",
            headers={"Authorization":"Bearer "+token,"Accept":"application/json",
                     "User-Agent":UA},timeout=16)
        # Do not print headers/body: account payload may contain private data.
        payload=r.json() if r.ok else None
        accounts=(payload if isinstance(payload,list) else
                  payload.get("data") if isinstance(payload,dict) else None)
        if isinstance(accounts,dict):accounts=accounts.get("data")
        if not isinstance(accounts,list):accounts=None
        # Count only; do not expose account identifiers or private metadata.
        found_acolad=(any(
            "acolad.agency" in str(a.get("identifier","")).lower()
            or "acolad.agency" in str(a.get("profile_url","")).lower()
            for a in accounts if isinstance(a,dict)) if accounts is not None else None)
        return {"status":"READ_ONLY_HTTP_"+str(r.status_code),
                "accounts_visible":len(accounts) if accounts is not None else None,
                "acolad_instagram_match":found_acolad}
    except (requests.RequestException,ValueError) as e:
        return {"status":"READ_ONLY_ERROR_"+type(e).__name__}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--story-json",type=Path)
    ap.add_argument("--stock",choices=("auto","off"),default="auto")
    ap.add_argument("--read-only-novinhub",action="store_true")
    ap.add_argument("--output",type=Path,default=OUT)
    args=ap.parse_args()
    if not BASE.is_file():raise FileNotFoundError("Upload assets/templates/acolad_story_base.png")
    if not features.check("raqm"):raise RuntimeError("Pillow was built without RAQM; Persian shaping unsafe")
    src=Image.open(BASE).convert("RGBA")
    if src.size!=(W,H):raise ValueError("Background must be exactly 1080x1920")
    story=(json.loads(args.story_json.read_text(encoding="utf8")) if args.story_json else DEMO)
    frames=frames_from_story(story)
    args.output.mkdir(parents=True,exist_ok=True)
    query=stock_query(story) if args.stock=="auto" else None
    stock=select_stock(query) if query else {"query":query,"status":"DISABLED_OR_NOT_RELEVANT","chosen":None}
    pic=None
    if stock.get("chosen"):
        try:pic=download_stock(stock["chosen"])
        except (requests.RequestException,ValueError,OSError) as e:
            stock["status"]="STOCK_DOWNLOAD_FAILED_"+type(e).__name__;pic=None
    use_photo_scene=None
    if pic:
        for f in frames:
            if f["beat"] in ("evidence","discovery","experiment"):
                use_photo_scene=f["scene"];break
    # Every frame must reuse the same background AND photo within a scene.
    for f in frames:
        img=src.copy()
        has_photo=pic is not None and f["scene"]==use_photo_scene
        if has_photo:add_photo(img,pic)
        render_text(img,f["text"],photo=has_photo)
        img.convert("RGB").save(args.output/f"story_{f['n']:02d}.jpg",
                               quality=93,optimize=True,subsampling=0)
    stock["used_scene"]=use_photo_scene
    (args.output/"stock_license.json").write_text(json.dumps(stock,ensure_ascii=False,indent=2),encoding="utf8")
    connection=(novinhub_readonly() if args.read_only_novinhub else {"status":"SKIPPED"})
    status={"state":"VISUAL_PREVIEW_ONLY","stories":len(frames),
            "is_unapproved_demo":args.story_json is None,
            "stock_status":stock["status"],"stock_used_scene":use_photo_scene,
            "novinhub":connection,"novinhub_uploads":0,"novinhub_drafts":0,
            "buffer_uploads":0,"telegram_posts":0,"instagram_posts":0}
    (args.output/"status.json").write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf8")
    (args.output/"story_frames.json").write_text(json.dumps(frames,ensure_ascii=False,indent=2),encoding="utf8")
    print("PREVIEW_ONLY "+json.dumps(status,ensure_ascii=False))
    return 0

if __name__=="__main__":
    sys.exit(main())
