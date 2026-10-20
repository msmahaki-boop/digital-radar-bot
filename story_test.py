"""Safe GitHub Actions preview. No Instagram/Telegram/Buffer post is published."""
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from story_data_builder import collect_candidates, build_story_texts, populate_images
from story_renderer import OUTPUT_DIR, render_intro, render_story


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    candidates = collect_candidates()
    if not candidates:
        raise SystemExit("No article candidates available from RSS right now")
    stories, ai_used = build_story_texts(candidates)
    if not stories:
        raise SystemExit("No suitable stories were chosen")
    populate_images(stories)
    render_intro()
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ai_used": ai_used,
        "publication_status": "PREVIEW ONLY - NOT PUBLISHED",
        "articles": [],
    }
    for index, story in enumerate(stories, 2):
        path, mode = render_story(story, index)
        manifest["articles"].append({
            "category": story.topic, "source": story.source,
            "source_url": story.link, "original_title": story.original_title,
            "headline": story.title_fa, "summary": story.summary_fa,
            "image_mode": mode, "image_status": story.image_status,
            "file": str(path),
        })
    with (OUTPUT_DIR / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("\nSUCCESS: Story preview generated.")
    print("Stories created:", 1 + len(stories))
    print("Gemini used:", ai_used)
    print("No content was published and sent_news.json was NOT changed.")


if __name__ == "__main__":
    main()
