"""Acolad Story Generator v2: GitHub Actions preview, NEVER PUBLICATION."""
import json
from datetime import datetime, timezone

from story_data_builder import (
    collect_candidates, enrich_candidates, build_story_texts, populate_images,
)
from story_renderer import OUTPUT_DIR, render_intro, render_story


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = collect_candidates()
    if not candidates:
        raise SystemExit("No suitable RSS news at this moment")
    enriched = enrich_candidates(candidates)
    stories, ai_used = build_story_texts(enriched)
    present_topics = {story.topic for story in stories}
    for topic in ("tech", "ai", "marketing", "social"):
        if topic not in present_topics:
            print(f"NOTICE: no validated news story for category {topic}")
    if not stories:
        raise SystemExit("Gemini found no stories worthy of publication. Try again later.")
    populate_images(stories)
    render_intro()
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "publication_status": "PREVIEW ONLY - NOTHING PUBLISHED",
        "ai_used": ai_used,
        "articles": [],
        "coverage": {topic: {"rss_candidates": sum(x["topic"] == topic for x in candidates),
                             "selected_by_editor": topic in present_topics}
                     for topic in ("tech", "ai", "marketing", "social")},
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
            "file": str(path),
        })
    with (OUTPUT_DIR / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    if not manifest["articles"]:
        raise SystemExit("No readable stories generated; inspect text layout errors")
    print(f"SUCCESS: {1 + len(manifest['articles'])} preview images created")
    print("NO PUBLISHING, NO CHANGE TO sent_news.json, NO BUFFER WRITE")


if __name__ == "__main__":
    main()
