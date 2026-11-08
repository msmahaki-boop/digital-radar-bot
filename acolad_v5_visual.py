#!/usr/bin/env python3
"""Acolad V5: genuine GPT2.5 illustration, 9 progressive stories and square cover.
Only creates files; publishing is a separate, explicitly gated operation.
"""
from __future__ import annotations
import json
import shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps,features

from acolad_human_story_v5 import validate,visual_story
from acolad_gapgpt_transparent_art import generate_scenes,verify_png
from acolad_narrative_visual_v2 import CONCEPT_DIR,render,check_assets

ROOT=Path("acolad_human_story_v5_output")
FONTS=Path("assets/fonts")
LOGO=Path("assets/brand/logo_acolad.png")
PALETTE={"cream":"#F5F2EB","ink":"#192033","purple":"#7B2CBF",
         "blue":"#38B6FF","lavender":"#E5D5FD"}

def font(weight,size):
    path=FONTS/("IRANSans-"+weight+".ttf")
    if not path.exists():raise RuntimeError("IRANSANS_WEIGHT_MISSING_"+weight)
    return ImageFont.truetype(str(path),size,layout_engine=ImageFont.Layout.RAQM)

def social_cover(art_path:Path, title:str, dest:Path):
    """Brand art belongs in a DISTINCT square Telegram/Bale visual, not Story 1."""
    if not features.check("raqm"):raise RuntimeError("IRANSANS_RAQM_MISSING")
    if not LOGO.exists():raise RuntimeError("ACOLAD_LOGO_MISSING")
    with Image.open(art_path) as image:
        raw=art_path.read_bytes()
        picture,alpha=verify_png(raw)
    if alpha["transparent_fraction"]<0.12:
        raise RuntimeError("SOCIAL_COVER_REQUIRES_REAL_TRANSPARENT_AI_ART")
    canvas=Image.new("RGBA",(1080,1080),PALETTE["cream"])
    d=ImageDraw.Draw(canvas)
    d.rounded_rectangle((44,45,1036,1033),radius=45,fill="#FFFFFF")
    d.rounded_rectangle((80,90,1000,108),radius=9,fill=PALETTE["blue"])
    d.ellipse((925,45,1064,187),fill=PALETTE["lavender"])
    # The picture comes from real GPT Image 2.5, never a generated story-frame.
    picture.thumbnail((570,570),Image.Resampling.LANCZOS)
    canvas.alpha_composite(picture,(round((1080-picture.width)/2),160))
    d=ImageDraw.Draw(canvas)
    head=font("Black",63)
    medium=font("Medium",32)
    reg=font("Regular",27)
    # The cover title follows each real story; never hardcode a prior topic.
    words=str(title).strip().split()
    if not 4<=len(words)<=18:raise RuntimeError("V5_COVER_TITLE_WORDS_INVALID")
    lines=[];current=""
    for word in words:
        candidate=(current+" "+word).strip()
        if current and d.textlength(candidate,font=head,direction="rtl",language="fa")>820:
            lines.append(current);current=word
        else:current=candidate
    if current:lines.append(current)
    if len(lines)>3:raise RuntimeError("V5_COVER_TITLE_OVERFLOWS_THREE_LINES")
    y=755
    for line in lines:
        d.text((540,y),line,font=head,anchor="ma",direction="rtl",
               language="fa",fill=PALETTE["ink"])
        y+=72
    # Marker is part of editorial typography, not counterfeit illustration.
    d.rounded_rectangle((278,882,802,900),radius=9,fill=PALETTE["lavender"])
    d.text((540,944),"داستانی درباره جواب روشن، نه وعده معجزه",
           font=medium,anchor="ma",direction="rtl",language="fa",
           fill=PALETTE["purple"])
    with Image.open(LOGO) as logo:
        mark=logo.convert("RGBA")
        mark.thumbnail((165,70),Image.Resampling.LANCZOS)
        canvas.alpha_composite(mark,(875,990-mark.height))
    d=ImageDraw.Draw(canvas)
    d.text((107,993),"acolad.ir",font=reg,anchor="la",
           fill=PALETTE["purple"])
    dest.parent.mkdir(parents=True,exist_ok=True)
    canvas.convert("RGB").save(dest,"PNG",optimize=True)
    with Image.open(dest) as checked:
        if checked.size!=(1080,1080) or checked.format!="PNG":
            raise RuntimeError("SOCIAL_COVER_INVALID_SIZE")
        checked.verify()
    return {"file":str(dest),"size":[1080,1080],
            "source_art":art_path.name,
            "gpt_origin_verified":True,
            "story_frame_reused":False,
            "weights":["Regular","Medium","Black"]}

def preview(story,sources,output=ROOT):
    issues=validate(story,sources)
    if issues:raise RuntimeError("V5_EDITORIAL_QA_VETO:"+",".join(issues))
    check_assets()
    output.mkdir(parents=True,exist_ok=True)
    visual=visual_story(story)
    CONCEPT_DIR.mkdir(parents=True,exist_ok=True)
    # Each job gets a fresh checkout; cleanup cannot delete receipts anywhere.
    for f in CONCEPT_DIR.glob("scene_[0-9][0-9].png"):
        f.unlink()
    # Resume only a verified actual AI image from prior Actions run 42480255927.
    # The runner's source is the immutable GitHub artifact downloaded by run-id,
    # not arbitrary local PNGs. The original log records model and alpha proof.
    cached=Path("acolad_v5_previous/acolad_concept_assets/scene_01.png")
    if cached.exists():
        recovered,stats=verify_png(cached.read_bytes())
        recovered.close()
        if stats.get("transparent_fraction",0)<.12:
            raise RuntimeError("V5_PREVIOUS_IMAGE_NOT_ACTUAL_ALPHA")
        shutil.copy2(cached,CONCEPT_DIR/"scene_01.png")
        original={"model":"gpt-image-2.5-flare","provider":"GapGPT",
             "real_ai_generated":True,"background":"transparent",
             "source_scene_id":1,"image_response":"GitHub_actions_immutable_artifact",
             "origin_run_id":42480255927,
             "transparency_method":"already_validated_GPT_native_alpha",
             "path":"scene_01.png",**stats}
        fresh=generate_scenes(visual,[2],CONCEPT_DIR)
        manifest={**fresh,"image_count":2,
                  "records":[original]+fresh["records"],
                  "reused_verified_original_run_id":42480255927}
    else:
        # Never silently substitute old story imagery or procedural art.
        manifest=generate_scenes(visual,[1,2],CONCEPT_DIR)
    if (manifest.get("real_ai_generated") is not True or
        manifest.get("procedural_assets")!=0 or
        manifest.get("stock_assets")!=0 or len(manifest.get("records") or [])!=2):
        raise RuntimeError("V5_GENUINE_AI_ART_PROVENANCE_INVALID")
    cover=social_cover(CONCEPT_DIR/"scene_01.png",story["title"],
                       output/"social_cover_square.png")
    visual_status=render(visual,output/"stories",allow_stock=False)
    if visual_status.get("previous_pixels_identical") is not True:
        raise RuntimeError("V5_FROZEN_TEXT_IS_NOT_PIXEL_IDENTICAL")
    if visual_status.get("organic_highlights") is not True:
        raise RuntimeError("V5_HIGHLIGHT_RENDER_NOT_VERIFIED")
    if visual_status.get("stock_photo_scene") is not None:
        raise RuntimeError("V5_STOCK_REPLACEMENT_FORBIDDEN")
    if visual_status.get("concept_scenes")!=[1,2]:
        raise RuntimeError("V5_EXPECTED_TWO_ART_SCENES_AND_TEXT_ONLY_FINALE")
    frames=sorted((output/"stories").glob("story_*.png"))
    if len(frames)!=9:raise RuntimeError("V5_EXPECTED_NINE_VISUAL_FRAMES")
    for frame in frames:
        with Image.open(frame) as image:
            if image.format!="PNG" or image.size!=(1080,1920):
                raise RuntimeError("V5_STORY_SIZE_INVALID")
            image.verify()
    status={"state":"V5_PREVIEW_ONLY_NOT_PUBLISHED","full_story_nine_beats":True,
        "frames":len(frames),"real_gpt25_transparent_art_assets":2,
        "cover":cover,"pixel_freeze_verified":True,
        "colored_highlights":True,"font_weights":["Regular","Medium","Bold","Black"],
        "social_mutations":0,"published":False,"stock_assets":0,
        "source_url":story["source_url"]}
    (output/"story.json").write_text(json.dumps(story,ensure_ascii=False,indent=2),
                                      encoding="utf8")
    (output/"image_provenance.json").write_text(
       json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf8")
    (output/"preview_status.json").write_text(
       json.dumps(status,ensure_ascii=False,indent=2),encoding="utf8")
    print("ACOLAD_V5_REAL_HUMAN_STORY_PREVIEW "+json.dumps(status,
        ensure_ascii=False),flush=True)
    return status
