#!/usr/bin/env python3
"""Acolad approved source-locked editorial -> original transparent AI art -> preview.

Never imports NovinHub token, never queues or publishes, and never weakens QA.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

import acolad_v4_hourly_publish as publish
from acolad_gapgpt_transparent_art import generate_scenes, verify_png, OUT as ART
from acolad_narrative_visual_v2 import render, scene_chunks

def run(source: Path):
    day = datetime.now(ZoneInfo("Asia/Tehran")).date()
    if day.isoformat() != "2026-11-07":
        raise RuntimeError("NOV7_PREVIEW_EXPIRED_NEW_SOURCE_NEEDED")
    root = source / "acolad_v4_daily_publication"
    story = json.loads((root / "story.json").read_text(encoding="utf8"))
    evidence = json.loads((root / "sources_private.json").read_text(encoding="utf8"))
    approved = json.loads((root / "hourly_ready.json").read_text(encoding="utf8"))
    if approved.get("day") != day.isoformat() or approved.get("validated") is not True:
        raise RuntimeError("EDITORIAL_NOT_APPROVED")
    scores = approved.get("critics") or []
    if len(scores) != 2 or not all(
        c.get("veto") is False and isinstance(c.get("score"), int)
        and c["score"] >= 85 for c in scores
    ):
        raise RuntimeError("INDEPENDENT_CRITIC_VETO")
    if len(evidence) != 1 or evidence[0].get("url") != (
        "https://doi.org/10.1016/j.respol.2026.105630"
    ):
        raise RuntimeError("VERIFIED_EVIDENCE_IDENTITY_CHANGED")
    if story.get("story_link") != evidence[0]["url"]:
        story["story_link"] = evidence[0]["url"]
        story["original_source_link_repaired"] = True
    publish.check_verified_editorial(story, evidence)
    publish.save_editorial(day, story, evidence)
    if set(approved.get("captions") or {}) != set(publish.NETWORKS):
        raise RuntimeError("APPROVED_CAPTIONS_NOT_COMPLETE")
    groups = scene_chunks(story)
    scenes = [int(g[0]["scene"]) for g in groups]
    if len(scenes) != len(set(scenes)):
        raise RuntimeError("REPEATED_SCENE_ID")
    manifest = generate_scenes(story, scenes, ART)
    if manifest["image_count"] != len(scenes):
        raise RuntimeError("NOT_ALL_SCENES_HAVE_REAL_AI")
    publish.OUT.mkdir(parents=True, exist_ok=True)
    frames_dir = publish.OUT / "frames"
    status = render(story, frames_dir, allow_stock=False)
    if sorted(status.get("concept_scenes") or []) != sorted(scenes):
        raise RuntimeError("ILLUSTRATION_MISSING_FROM_LAYOUT")
    if not status.get("previous_pixels_identical"):
        raise RuntimeError("SCENE_TEXT_LAYOUT_CHANGED")
    frames = sorted(frames_dir.glob("story_*.png"))
    if len(frames) != len(story.get("slides") or []) or len(frames) != 7:
        raise RuntimeError("STORY_FRAME_COUNT_INVALID")
    for frame in frames:
        with Image.open(frame) as image:
            if image.format != "PNG" or image.size != (1080,1920):
                raise RuntimeError("COMPOSED_FRAME_BAD")
            image.verify()
    (publish.OUT / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2),encoding="utf8")
    (publish.OUT / "sources_private.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2),encoding="utf8")
    publish.READY.write_text(json.dumps(approved, ensure_ascii=False, indent=2),encoding="utf8")
    # Explicitly preserve *real* cutout provenance separate from final 1080x1920 frames.
    (publish.OUT / "real_ai_art_provenance.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    if publish.existing_bundle(day) is None:
        raise RuntimeError("FINAL_BUNDLE_NOT_COMPLETE")
    result = {"status": "PREVIEW_REAL_GPT_IMAGE_2_5_PASSED",
              "date_tehran": day.isoformat(), "model": manifest["model"],
              "real_ai_assets": len(scenes), "transparent_assets": True,
              "procedural_assets": 0, "scenes": scenes,
              "frames": len(frames), "critics": [c["score"] for c in scores],
              "caption_networks": sorted(approved["captions"]),
              "published": 0, "queued": 0, "novinhub_requests": 0}
    (publish.OUT / "transparent_preview_status.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print("ACOLAD_GAPGPT_TRANSPARENT_PREVIEW " + json.dumps(result, ensure_ascii=False), flush=True)
    return result

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,default=Path("checked_editorial"))
    opts=parser.parse_args()
    run(opts.source)
