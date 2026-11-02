#!/usr/bin/env python3
"""Acolad story renderer V2 — IRANSans, immutable same-scene reveal, PREVIEW ONLY.
No API sending. No NovinHub drafts. Uses Acolad's original binary logo/background.
"""
import argparse
import json
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageFont, features
import acolad_narrative_visual_preview as legacy

BASE=Path("assets/templates/acolad_story_base.png")
FONT_DIR=Path("assets/fonts")
REG=FONT_DIR/"IRANSans-Regular.ttf"
BOLD=FONT_DIR/"IRANSans-Bold.ttf"
MEDIUM=FONT_DIR/"IRANSans-Medium.ttf"
OUT=Path("acolad_narrative_visual_v2_output")
FONT_SIZES=(74,70,66,62,58,54,50,46,42,38)
TEXT_COLOR=(29,30,43)
ACCENT=(112,46,197)
BG_TEXT_TOP=465
PHOTO_TEXT_TOP=1015
TEXT_BOTTOM=1470
TEXT_X=966
MAX_WIDTH=855

def font_integrity():
    """Fail closed on the repository's current zero-filled placeholder fonts.

    Never silently replace the actual Acolad brand font in production.
    """
    names=(REG,MEDIUM,BOLD)
    for name in names:
        if not name.is_file():return "MISSING:"+str(name)
        with name.open("rb") as f:head=f.read(64)
        if not head or head==bytes(len(head)):
            return "ZERO_FILLED:"+str(name)
        if head[:4] not in (b"\\x00\\x01\\x00\\x00",b"OTTO",b"true",b"typ1"):
            return "INVALID_FONT_HEADER:"+str(name)
    return "VALID"

def check_assets():
    if not BASE.is_file():raise FileNotFoundError("Missing Acolad brand background "+str(BASE))
    result=font_integrity()
    if result!="VALID":
        raise RuntimeError("IRANSANS_ASSETS_NOT_READY: "+result+
                           ". Upload original licensed IRANSans TTFs to assets/fonts/ before production rendering.")
    if not features.check("raqm"):raise RuntimeError("Missing RTL RAQM text layout support")
    with Image.open(BASE) as image:
        if image.size!=(1080,1920):raise ValueError("Incorrect Acolad background dimensions")

def font_set(size):
    return (ImageFont.truetype(str(REG),size,layout_engine=ImageFont.Layout.RAQM),
            ImageFont.truetype(str(BOLD),size,layout_engine=ImageFont.Layout.RAQM))

def split_text_lines(text):
    result=[]
    for line in text.split("\n"):
        if line.strip():result.append(legacy.split_markup(line))
        else:result.append([])
    return result

def word_lines(draw,raw,regular,bold):
    result=[]
    for paragraph in split_text_lines(raw):
        if not paragraph:
            result.append([])
        else:
            result.extend(legacy.wrap(paragraph,draw,regular,bold,MAX_WIDTH))
    return result

def plan_scene(segments,photo=False):
    """Plan once for entire scene, not again for each frame."""
    im=Image.new("RGB",(1080,1920))
    d=ImageDraw.Draw(im)
    top=PHOTO_TEXT_TOP if photo else BG_TEXT_TOP
    for size in FONT_SIZES:
        normal,emphasis=font_set(size)
        advance=int(size*1.7)
        gap=int(size*.35)
        planned=[];y=top+24
        for seg in segments:
            lines=word_lines(d,seg,normal,emphasis)
            height=len(lines)*advance
            planned.append({"y":y,"lines":lines,"size":size})
            y+=height+gap
        if y< TEXT_BOTTOM-10:return planned
    raise ValueError("Scene too text-heavy for frozen-layout, split into another scene")

def render_rows(image,layout):
    """Append only fresh segment to the prior image, leaving prior pixels untouched."""
    draw=ImageDraw.Draw(image)
    size=layout["size"]
    normal,emphasis=font_set(size)
    advance=int(size*1.7)
    y=layout["y"]
    for row in layout["lines"]:
        x=TEXT_X
        for word,isbold in row:
            f=emphasis if isbold else normal
            if legacy.is_emoji_token(word):
                icon=legacy.make_emoji(word,size)
                if icon is None:raise RuntimeError("Missing emoji glyph")
                width=int(size*1.35)
                image.alpha_composite(icon,(round(x-width),round(y+size*.08)))
                draw=ImageDraw.Draw(image)
                x-=width
                continue
            word_width=draw.textlength(word,font=f,direction="rtl",language="fa")
            advance_width=draw.textlength(word+" ",font=f,direction="rtl",language="fa")
            if isbold:
                overlay=Image.new("RGBA",image.size,(0,0,0,0))
                high=ImageDraw.Draw(overlay)
                high.rounded_rectangle((round(x-word_width-10),round(y+size*.58),
                    round(x+6),round(y+size*1.19)),radius=9,fill=(201,172,255,160))
                image.alpha_composite(overlay)
                draw=ImageDraw.Draw(image)
            draw.text((x,y),word,font=f,fill=ACCENT if isbold else TEXT_COLOR,
                      direction="rtl",language="fa",anchor="ra")
            x-=advance_width
        y+=advance

def scene_chunks(story):
    frames=legacy.frames_from_story(story)
    scenes=[];group=[]
    for f in frames:
        if f["action"]=="new_scene" and group:
            scenes.append(group);group=[]
        group.append(f)
    if group:scenes.append(group)
    return scenes

def render(story,output,allow_stock=True):
    check_assets()
    output.mkdir(parents=True,exist_ok=True)
    base=Image.open(BASE).convert("RGBA")
    query=legacy.stock_query(story) if allow_stock else None
    stock=legacy.select_stock(query) if query else {"status":"DISABLED","chosen":None}
    photo=None
    if stock.get("chosen"):
        try:photo=legacy.download_stock(stock["chosen"])
        except Exception as e:
            stock["status"]="STOCK_NOT_USED_"+type(e).__name__
    scene_groups=scene_chunks(story)
    selected_photo_scene=None
    if photo is not None:
        for group in scene_groups:
            if any(f["beat"] in ("evidence","experiment","discovery") for f in group):
                selected_photo_scene=group[0]["scene"];break
    exact_checks=[]
    for group in scene_groups:
        sid=group[0]["scene"]
        use_photo=photo is not None and sid==selected_photo_scene
        layouts=plan_scene([f["added_text"] for f in group],photo=use_photo)
        current=base.copy()
        if use_photo:legacy.add_photo(current,photo)
        for i,f in enumerate(group):
            before=current.copy()
            render_rows(current,layouts[i])
            # Before additions are isolated: the already rendered scene is
            # copied, never re-centered or redrawn.
            current.convert("RGB").save(output/f"story_{f['n']:02d}.png",optimize=True)
            if i:
                # prior visible scene content has an immutable bounding region
                # above the new segment; compare actual RGBA pixel bytes.
                previous_bottom=layouts[i]["y"]-int(layouts[i]["size"]*.1)
                box=(60,0,1020,max(0,previous_bottom))
                equal=before.crop(box).tobytes()==current.crop(box).tobytes()
                if not equal:raise AssertionError(f"Prior text moved in scene {sid}, frame {f['n']}")
                exact_checks.append({"scene":sid,"frame":f["n"],"previous_pixels_identical":True})
    status={"state":"FROZEN_LAYOUT_PREVIEW_ONLY","frames":sum(len(g) for g in scene_groups),
       "scenes":len(scene_groups),"brand_font":"assets/fonts/IRANSans-Regular.ttf",
       "brand_bold":"assets/fonts/IRANSans-Bold.ttf","previous_pixels_identical":all(
          x["previous_pixels_identical"] for x in exact_checks),
       "stock_status":stock.get("status"),"stock_photo_scene":selected_photo_scene,
       "novinhub_draft_count":0,"uploads":0,"scheduled":0,"published":0,
       "manual_editorial_review_required":True}
    (output/"pixel_freeze_checks.json").write_text(json.dumps(exact_checks,ensure_ascii=False,indent=2),encoding="utf8")
    (output/"stock_license.json").write_text(json.dumps(stock,ensure_ascii=False,indent=2),encoding="utf8")
    (output/"status.json").write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(status,ensure_ascii=False))
    return status

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--story-json",type=Path,required=True)
    ap.add_argument("--output",type=Path,default=OUT)
    ap.add_argument("--stock",choices=("off","auto"),default="auto")
    args=ap.parse_args()
    story=json.loads(args.story_json.read_text(encoding="utf8"))
    render(story,args.output,allow_stock=args.stock=="auto")
