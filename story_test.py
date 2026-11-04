"""Acolad Story Generator v2.6: GitHub Actions preview, NEVER PUBLICATION."""
import json
from datetime import datetime, timezone

from story_data_builder import (
    collect_candidates, enrich_candidates, build_story_texts, populate_images,
)
from story_renderer import OUTPUT_DIR, TEMPLATE_DIR, TOPICS, template_name, render_intro, render_story
from story_data_builder import ACTIVE_TOPICS, ALL_OLD_KEYS, NEW_TOPIC_KEYS
from bot import canonical_link


def verify_minimal_templates():
    """Fail early and clearly, before making expensive calls to Gemini."""
    required = [TEMPLATE_DIR / "intro_story.png"]
    required += [TEMPLATE_DIR / template_name(topic, mode)
                 for topic in (*ALL_OLD_KEYS, *NEW_TOPIC_KEYS)
                 for mode in ("text_only", "photo")]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("MISSING MINIMALIST TEMPLATES: " + ", ".join(missing) +
                         ". Keep the original intro, all eight old PNGs and six new PNGs.")
    print("TEMPLATES VERIFIED: 14 minimalist + unchanged intro", flush=True)


def main():
    verify_minimal_templates()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = collect_candidates()
    if not candidates:
        raise SystemExit("No suitable RSS news at this moment")
    enriched = enrich_candidates(candidates)
    initial_stories, ai_used = build_story_texts(enriched)
    present_topics = {story.topic for story in initial_stories}
    for topic in ACTIVE_TOPICS:
        if topic not in present_topics:
            print(f"NOTICE: no validated news story for category {topic}")

    stories = []
    seen_links = set()

    def add_unique(items):
        for story in items:
            key = canonical_link(story.link) or story.link
            if key in seen_links:
                print(f"EDITOR DEDUP: skipped same article in {story.topic}")
                continue
            seen_links.add(key)
            stories.append(story)

    add_unique(initial_stories)

    # Reserve two places for the legacy topics and two for the three new topics.
    # A missing RSS category is not a reason to invent a story or stop when another
    # category has a verifiable, distinct article. Never change a post's category.
    old = set(ALL_OLD_KEYS)
    new = set(NEW_TOPIC_KEYS)
    for group, label in ((ALL_OLD_KEYS, "original"), (NEW_TOPIC_KEYS, "new")):
        current = sum(story.topic in group for story in stories)
        if current >= 2:
            continue
        # Only substitute categories that weren't requested in the initial rotation.
        for fallback in group:
            if current >= 2:
                break
            if fallback in ACTIVE_TOPICS or any(story.topic == fallback for story in stories):
                continue
            print(f"EDITOR FALLBACK: trying {fallback} to replace a missing {label} topic", flush=True)
            alternatives = collect_candidates((fallback,))
            if not alternatives:
                print(f"EDITOR FALLBACK SKIP: no recent relevant RSS for {fallback}")
                continue
            alternatives = enrich_candidates(alternatives)
            backup_stories, backup_ai = build_story_texts(alternatives, requested_topics=(fallback,))
            ai_used = ai_used or backup_ai
            before = len(stories)
            add_unique(backup_stories)
            if len(stories) > before:
                current += 1
                print(f"EDITOR FALLBACK SUCCESS: {fallback}", flush=True)

    # Preserve balanced coverage and never pad with invented or reused news.
    old_count = sum(story.topic in old for story in stories)
    new_count = sum(story.topic in new for story in stories)
    if len(stories) != 4 or old_count != 2 or new_count != 2:
        raise SystemExit(f"Need 2 original + 2 new verified distinct stories; "
                         f"got old={old_count}, new={new_count}. Safe skip.")
    present_topics = {story.topic for story in stories}
    print("EDITOR SELECTED: " + ", ".join(story.topic for story in stories), flush=True)
    if __import__('os').getenv('ACOLAD_IMAGE_LADDER_ENABLED') == 'true':
        from acolad_story_image_ladder import enrich_images
        enrich_images(stories,allow_billable=__import__('os').getenv('ACOLAD_IMAGE_API_PAID_ENABLED') == 'true')
    else:
        populate_images(stories)
    render_intro()
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "publication_status": "PREVIEW ONLY - NOTHING PUBLISHED",
        "ai_used": ai_used,
        "articles": [],
        "coverage": {topic: {"rss_candidates": sum(x["topic"] == topic for x in candidates),
                             "selected_by_editor": topic in present_topics}
                     for topic in (*ALL_OLD_KEYS, *NEW_TOPIC_KEYS)},
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
