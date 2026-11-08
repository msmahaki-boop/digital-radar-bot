#!/usr/bin/env python3
"""Strict daily Acolad story compositor: real GapGPT GPT Image 2.5 only.

Called only after factual/evidence/voice and two independent editorial critics
have approved the story. Never touches Telegram, Bale, Instagram or NovinHub.
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image

from acolad_gapgpt_transparent_art import generate_scenes, MAX_IMAGES
from acolad_narrative_visual_v2 import CONCEPT_DIR, render, scene_chunks

OUTPUT = Path("acolad_v4_daily_publication")


def verify_generated_alpha_file(path:Path):
    """Validate PNG bytes before reading its real alpha pixels (Pillow order)."""
    with Image.open(path) as probe:
        if probe.format != "PNG" or "A" not in probe.getbands():
            raise RuntimeError("GPT25_ALPHA_PNG_MISSING")
        probe.verify()
    with Image.open(path) as image:
        if image.getchannel("A").getextrema()[0] >= 255:
            raise RuntimeError("GPT25_ALPHA_NOT_TRANSPARENT")
    return True


def illustrate_strict(story: dict):
    groups = scene_chunks(story)
    scene_ids = [int(group[0]["scene"]) for group in groups]
    if not 2 <= len(groups) <= MAX_IMAGES or len(set(scene_ids)) != len(scene_ids):
        raise RuntimeError("GPT25_STRICT_DISTINCT_SCENE_COUNT_INVALID")
    CONCEPT_DIR.mkdir(parents=True, exist_ok=True)
    # Prevent any previous procedural PNG leaking into new real-AI previews.
    for file in CONCEPT_DIR.glob("scene_[0-9][0-9].png"):
        file.unlink()
    manifest = generate_scenes(story, scene_ids, CONCEPT_DIR)
    records = manifest["records"]
    if manifest.get("procedural_assets") != 0 or len(records) != len(scene_ids):
        raise RuntimeError("GPT25_ART_PROVENANCE_INVALID")
    for row in records:
        if not row.get("real_ai_generated") or row.get("background") != "transparent":
            raise RuntimeError("GPT25_REAL_AI_CUTOUT_REQUIRED")
        path = CONCEPT_DIR / row["path"]
        verify_generated_alpha_file(path)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    output = OUTPUT / "frames"
    visual = render(story, output, allow_stock=False)
    if sorted(visual.get("concept_scenes") or []) != sorted(scene_ids):
        raise RuntimeError("GPT25_ART_NOT_VISIBLE_ALL_SCENES")
    if visual.get("previous_pixels_identical") is not True:
        raise RuntimeError("GPT25_FROZEN_LAYOUT_FAILED")
    frames = sorted(output.glob("story_*.png"))
    if len(frames) != len(story.get("slides") or []):
        raise RuntimeError("GPT25_FINAL_FRAMES_INCOMPLETE")
    for p in frames:
        with Image.open(p) as image:
            if image.format != "PNG" or image.size != (1080, 1920):
                raise RuntimeError("GPT25_STORY_FRAME_INVALID")
            image.verify()
    (OUTPUT / "image_provenance.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    print("ACOLAD_GAPGPT_GPT25_REAL_IMAGE_LAYOUT " + json.dumps({
        "image_count":len(records), "story_frames":len(frames),
        "procedural_assets":0, "real_model":manifest["model"],
        "published":0, "queued":0
    },ensure_ascii=False),flush=True)
    return frames, records
