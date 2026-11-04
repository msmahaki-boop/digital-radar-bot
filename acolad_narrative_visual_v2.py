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
FONT_SIZES=(66,62,58,54,50,46,42,38)
TEXT_COLOR=(29,30,43)
ACCENT=(112,46,197)
BG_TEXT_TOP=485
PHOTO_TEXT_TOP=1015
TEXT_BOTTOM=1470
TEXT_X=540
MAX_WIDTH=830
CONCEPT_DIR=Path("acolad_concept_assets")
HIGHLIGHT_INKS=(
    ((99,43,184),(205,179,250,162)),     # lavender
    ((9,111,161),(143,223,249,164)),     # cyan
    ((121,69,15),(250,219,143,166)),     # warm yellow
    ((137,40,108),(249,186,216,154)),    # blush
    ((23,111,87),(161,231,209,156)),     # mint
)

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
        if head[:4] not in (b"\x00\x01\x00\x00",b"OTTO",b"true",b"typ1"):
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

def _row_runs(row):
    """Group consecutive bold words so highlights cover PHRASES, not word tiles."""
    runs=[]
    for word,bold in row:
        if legacy.is_emoji_token(word):
            runs.append((word,False,True))
        elif runs and runs[-1][1]==bold and not runs[-1][2]:
            prev,_,_=runs.pop()
            runs.append((prev+" "+word,bold,False))
        else:
            runs.append((word,bold,False))
    return runs

def _highlight_brush(image,box,variant):
    """Transparent painterly underline with organic wavy edges; never a box."""
    x0,y0,x1,y1=[round(x) for x in box]
    if x1<=x0:return
    salt=(x0*17+y0*7+variant*31)%13
    layer=Image.new("RGBA",image.size,(0,0,0,0))
    ink=ImageDraw.Draw(layer)
    color=HIGHLIGHT_INKS[variant%len(HIGHLIGHT_INKS)][1]
    w=x1-x0
    # One broad imperfect swipe with a small pencil-fiber extension.
    points=[
       (x0-6,y0+7+salt%3),
       (x0+w*.17,y0+2),
       (x0+w*.43,y0+6),
       (x0+w*.72,y0+1+salt%4),
       (x1+5,y0+4),
       (x1+9,y1-3),
       (x0+w*.75,y1+3),
       (x0+w*.45,y1),
       (x0+w*.20,y1+2),
       (x0-8,y1-2),
    ]
    ink.polygon(points,fill=color)
    # Uneven second pass gives a marker/brush texture, not flat rectangle.
    ink.line([(x0,y1-3),(x0+w*.28,y1-5),(x0+w*.60,y1-4),(x1,y1-7)],
             fill=(color[0],color[1],color[2],53),width=4)
    image.alpha_composite(layer)

def _run_width(draw,run,regular,emphasis,size):
    text,bold,emoji=run
    if emoji:return size*1.35
    f=emphasis if bold else regular
    return draw.textlength(text,font=f,direction="rtl",language="fa")

def render_rows(image,layout):
    """Render only new text; previous scene pixels remain perfectly frozen."""
    draw=ImageDraw.Draw(image)
    size=layout["size"]
    normal,emphasis=font_set(size)
    advance=int(size*1.68)
    y=layout["y"]
    for row in layout["lines"]:
        runs=_row_runs(row)
        gap=draw.textlength(" ",font=normal,direction="rtl",language="fa")
        widths=[_run_width(draw,run,normal,emphasis,size) for run in runs]
        total=sum(widths)+gap*max(0,len(runs)-1)
        if total>MAX_WIDTH+2:raise ValueError("Line longer than centered text safe zone")
        x=TEXT_X+total/2
        for i,(run,width) in enumerate(zip(runs,widths)):
            text,isbold,isemoji=run
            if isemoji:
                icon=legacy.make_emoji(text,size)
                if icon is None:raise RuntimeError("Missing Noto color emoji glyph")
                image.alpha_composite(icon,(round(x-width),round(y+size*.11)))
                draw=ImageDraw.Draw(image)
            else:
                font=emphasis if isbold else normal
                if isbold:
                    index=(layout.get("highlight_seed",0)+i+y//100)
                    color=HIGHLIGHT_INKS[index%len(HIGHLIGHT_INKS)][0]
                    _highlight_brush(image,(x-width-5,y+size*.63,
                                           x+5,y+size*1.21),index)
                    draw=ImageDraw.Draw(image)
                else:
                    color=TEXT_COLOR
                draw.text((x,y),text,font=font,fill=color,
                          direction="rtl",language="fa",anchor="ra")
            x-=width+gap
        y+=advance

def add_concept_illustration(background,illustration):
    """Paste original line art safely on Acolad's background without the paper rectangle.

    Trim image-model ivory paper (not the ink), then contain the actual drawing in
    the upper art area. Keep the lower text zone and original logo completely clear.
    """
    from PIL import ImageOps, ImageFilter
    if illustration.width<256 or illustration.height<256:
        raise ValueError("Generated concept artwork resolution too small")
    # Deliberately smaller than the old (125,295,955,900) box.
    # The editorial text starts at y=1015 for illustration scenes.
    zone=(205,295,875,800)
    source=illustration.convert("RGBA")
    ink=Image.new("RGBA",source.size,(0,0,0,0))
    src=source.load()
    dst=ink.load()
    for y in range(source.height):
        for x in range(source.width):
            red,green,blue,a=src[x,y]
            low=min(red,green,blue)
            chroma=max(red,green,blue)-low
            # Remove neutral light cream/white backgrounds, NOT colored ink.
            if chroma<=36 and low>=232:
                alpha=0
            elif chroma<=36 and low>=198:
                alpha=round(a * (232-low)/34)
            else:
                alpha=a
            dst[x,y]=(red,green,blue,alpha)
    mask=ink.getchannel("A")
    bbox=mask.point(lambda a: 255 if a>35 else 0).getbbox()
    if not bbox:
        raise ValueError("AI artwork contains no visible ink")
    # Bound crop to visible drawing + 7% padding; never crop actual linework.
    padding=max(12,round(min(source.size)*.065))
    left=max(0,bbox[0]-padding)
    top=max(0,bbox[1]-padding)
    right=min(source.width,bbox[2]+padding)
    bottom=min(source.height,bbox[3]+padding)
    cropped=ink.crop((left,top,right,bottom))
    fitted=ImageOps.contain(cropped,(zone[2]-zone[0],zone[3]-zone[1]),
                            method=Image.Resampling.LANCZOS)
    x=zone[0]+((zone[2]-zone[0])-fitted.width)//2
    y=zone[1]+((zone[3]-zone[1])-fitted.height)//2
    background.alpha_composite(fitted,(x,y))

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
        generated=CONCEPT_DIR/f"scene_{int(sid):02d}.png"
        use_concept=generated.is_file()
        # A concept drawing replaces stock for this scene; no photo collage.
        use_photo=use_photo and not use_concept
        layouts=plan_scene([f["added_text"] for f in group],photo=(use_photo or use_concept))
        for i,layout in enumerate(layouts):
            layout["highlight_seed"]=int(sid)*7+i*3
        current=base.copy()
        if use_photo:legacy.add_photo(current,photo)
        if use_concept:
            with Image.open(generated) as illustration:
                add_concept_illustration(current,illustration)
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
       "concept_scenes":[int(g[0]["scene"]) for g in scene_groups if (CONCEPT_DIR/f"scene_{int(g[0]['scene']):02d}.png").is_file()],
       "centered_text":True,"organic_highlights":True,
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
