"""Acolad Story Generator v2.6: GitHub Actions preview, NEVER PUBLICATION."""
import json
from datetime import datetime, timezone

from story_data_builder import (
    collect_candidates, enrich_candidates, build_story_texts, populate_images,
)
from story_renderer import OUTPUT_DIR, TEMPLATE_DIR, TOPICS, template_name, render_intro, render_story
from story_data_builder import ACTIVE_TOPICS


def verify_minimal_templates():
    """Fail early and clearly, before making expensive calls to Gemini."""
    required = [TEMPLATE_DIR / "intro_story.png"]
    required += [TEMPLATE_DIR / template_name(topic, mode)
                 for topic in ACTIVE_TOPICS for mode in ("text_only", "photo")]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("MISSING MINIMALIST TEMPLATES: " + ", ".join(missing) +
                         ". Keep the original intro and upload the eight final V2.6 images.")
    print("TEMPLATES VERIFIED: 8 minimalist + unchanged intro", flush=True)


def main():
    verify_minimal_templates()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = collect_candidates()
    if not candidates:
        raise SystemExit("No suitable RSS news at this moment")
    enriched = enrich_candidates(candidates)
    stories, ai_used = build_story_texts(enriched)
    present_topics = {story.topic for story in stories}
    for topic in ACTIVE_TOPICS:
        if topic not in present_topics:
            print(f"NOTICE: no validated news story for category {topic}")
    if len(stories) != 4:
        raise SystemExit("Need exactly 4 grounded topics; refuse incomplete daily publication")
    populate_images(stories)
    render_intro()
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "publication_status": "PREVIEW ONLY - NOTHING PUBLISHED",
        "ai_used": ai_used,
        "articles": [],
        "coverage": {topic: {"rss_candidates": sum(x["topic"] == topic for x in candidates),
                             "selected_by_editor": topic in present_topics}
                     for topic in ACTIVE_TOPICS},
    }
    for index, story in enumerate(stories, 2):
        try:
            path, mode = render_story(story, index)
        except Exception as exc:
            # A failed image generation must not silently become a published post.
            print(f"WARNING: Unable to render {story.topic}: {type(exc).__name__}: {exc}")
            continue
        manifest["articles"].append({
            "topic": story.topic,
            "headline": story.title_fa,
            "story_text": story.summary_photo_fa if mode != "text_only" else story.summary_fa,
            "source_for_editor_only": story.source,
            "article_url_for_editor_only": story.link,
            "original_title": story.original_title,
            "mode": mode,
            "image_review_status": story.image_status,
            "emphasis_terms_for_editor_only": getattr(story, "emphasis_terms", []),
            "file": str(path),
        })
    with (OUTPUT_DIR / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    if len(manifest["articles"]) != 4:
        raise SystemExit("No readable stories generated; inspect text layout errors")
    print(f"SUCCESS: {1 + len(manifest['articles'])} preview images created")
    print("NO PUBLISHING, NO CHANGE TO sent_news.json, NO BUFFER WRITE")


if __name__ == "__main__":
    main()
