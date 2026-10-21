"""Acolad story sequence -> ONE Instagram Story draft in Buffer.

Only writes anything when --create-draft yes; NEVER publishes or queues posts.
Accepts only a GitHub Actions artifact produced by the existing Story Generator.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

import requests
from PIL import Image

BUFFER_API = "https://api.buffer.com"
ARTIFACT_DIR = Path("downloaded_stories")
TARGET_ACCOUNT = "acolad.agency"
TOPICS = ("tech", "ai", "marketing", "social")

class BatchError(RuntimeError):
    pass


def collect_images():
    manifest_path = ARTIFACT_DIR / "manifest.json"
    if not manifest_path.is_file():
        raise BatchError("manifest.json missing from story preview artifact")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        raise BatchError("Unreadable manifest.json") from e
    if manifest.get("publication_status") != "PREVIEW ONLY - NOTHING PUBLISHED":
        raise BatchError("Unexpected manifest publication_status; refusing to proceed")
    articles = manifest.get("articles")
    if not isinstance(articles, list) or not (1 <= len(articles) <= 4):
        raise BatchError("Expected 1 to 4 validated news articles")
    intro = ARTIFACT_DIR / "01_intro.png"
    paths = [intro]
    topics_seen = set()
    for article in articles:
        topic = article.get("topic")
        if topic not in TOPICS or topic in topics_seen:
            raise BatchError(f"Duplicate or unknown topic: {topic!r}")
        topics_seen.add(topic)
        original = str(article.get("file", ""))
        if not original.startswith("stories_output/"):
            raise BatchError("Unexpected file path in manifest")
        file_name = original.split("/")[-1]
        if not re.fullmatch(r"0[2-5]_(tech|ai|marketing|social)_(photo|text_only)\.png", file_name):
            raise BatchError(f"Unexpected PNG filename in manifest: {file_name!r}")
        if file_name.split("_")[1] != topic:
            raise BatchError("Article category disagrees with PNG filename")
        paths.append(ARTIFACT_DIR / file_name)
    if len(paths) != len(set(paths)):
        raise BatchError("Duplicate image filenames")
    for image_path in paths:
        if not image_path.is_file():
            raise BatchError(f"Missing image: {image_path.name}")
        if image_path.stat().st_size > 20 * 1024 * 1024:
            raise BatchError(f"PNG larger than 20MB: {image_path.name}")
        try:
            with Image.open(image_path) as im:
                w, h = im.size
                if im.format != "PNG" or (w, h) != (1080, 1920):
                    raise BatchError(f"Expected 1080x1920 PNG: {image_path.name} ({w}x{h})")
                im.verify()
        except (OSError, ValueError) as e:
            raise BatchError(f"Invalid PNG: {image_path.name}") from e
        print(f"IMAGE OK: {image_path.name} ({w}x{h})", flush=True)
    print("ORDER VERIFIED: " + " → ".join(p.name for p in paths), flush=True)
    if len(topics_seen) < 4:
        print("NOTICE: missing news categories: " + ", ".join(t for t in TOPICS if t not in topics_seen), flush=True)
    return paths


def buffer_graphql(query: str, variables: dict | None = None) -> dict:
    api_key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not api_key:
        raise BatchError("GitHub secret BUFFER_API_KEY missing")
    try:
        res = requests.post(
            BUFFER_API,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"query": query, "variables": variables or {}},
            timeout=45,
        )
        res.raise_for_status()
        parsed = res.json()
    except requests.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", "network")
        raise BatchError(f"Buffer connection error HTTP/status {status}") from None
    except ValueError:
        raise BatchError("Buffer response not JSON") from None
    if parsed.get("errors"):
        raise BatchError("Buffer GraphQL: " + str(parsed["errors"][0].get("message", "unknown"))[:300])
    if not isinstance(parsed.get("data"), dict):
        raise BatchError("Missing Buffer response data")
    return parsed["data"]


def find_channel():
    account = buffer_graphql("query { account { organizations { id name } } }").get("account") or {}
    orgs = account.get("organizations") or []
    matches = []
    for org in orgs:
        org_id = json.dumps(org["id"])
        query = f"query {{ channels(input: {{ organizationId: {org_id} }}) {{ id name service }} }}"
        matches.extend(c for c in buffer_graphql(query).get("channels", [])
                       if str(c.get("name", "")).strip().casefold() == TARGET_ACCOUNT
                       and str(c.get("service", "")).strip().casefold() == "instagram")
    if len(matches) != 1:
        raise BatchError(f"Expected one connected Instagram channel {TARGET_ACCOUNT}, found {len(matches)}")
    print("BUFFER OK: Instagram " + TARGET_ACCOUNT, flush=True)
    return matches[0]["id"]


def upload_image(path: Path):
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    key = os.getenv("CLOUDINARY_API_KEY", "").strip()
    secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    if not all((cloud_name, key, secret)):
        raise BatchError("Missing Cloudinary secrets: CLOUDINARY_CLOUD_NAME / CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", cloud_name):
        raise BatchError("Invalid Cloudinary cloud name")
    url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    try:
        with path.open("rb") as f:
            res = requests.post(
                url, auth=(key, secret), files={"file": (path.name, f, "image/png")},
                data={"folder": "acolad/automated-stories"}, timeout=120,
            )
        res.raise_for_status()
        result = res.json()
    except requests.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", "network")
        raise BatchError(f"Cloudinary upload error HTTP/status {status} for {path.name}") from None
    except ValueError:
        raise BatchError("Cloudinary response not JSON") from None
    media_url = result.get("secure_url", "")
    if not media_url.startswith("https://res.cloudinary.com/"):
        raise BatchError("Cloudinary did not return a usable HTTPS URL")
    print(f"CLOUDINARY OK: {path.name}", flush=True)
    return media_url


def save_one_story_draft(channel_id: str, urls: list[str]):
    query = """
    mutation CreateStoryDraft($input: CreatePostInput!) {
      createPost(input: $input) {
        __typename
        ... on PostActionSuccess { post { id text } }
        ... on MutationError { message }
      }
    }
    """
    data = buffer_graphql(query, {"input": {
        "channelId": channel_id,
        "text": "خبرهای داغ امروز | آکولاد",
        "schedulingType": "automatic",
        "mode": "addToQueue",
        "saveToDraft": True,
        "aiAssisted": True,
        "assets": [{"image": {"url": url}} for url in urls],
        "metadata": {"instagram": {"type": "story", "shouldShareToFeed": False}},
    }}).get("createPost") or {}
    if data.get("__typename") != "PostActionSuccess":
        raise BatchError("Buffer draft failed: " + str(data.get("message", data.get("__typename", "unknown")))[:250])
    post_id = (data.get("post") or {}).get("id")
    if not post_id:
        raise BatchError("Buffer returned success but no draft ID; check Buffer Drafts")
    print(f"DRAFT SUCCESS: {post_id} | {len(urls)} images | published=NO, queued=NO", flush=True)
    print("Open Buffer > Instagram acolad.agency > Drafts", flush=True)
    return post_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-draft", choices=("no", "yes"), default="no")
    args = parser.parse_args()
    paths = collect_images()
    channel_id = find_channel()
    if args.create_draft != "yes":
        print("DRY RUN PASSED. Images validated, Buffer channel verified; NO media uploaded, NO draft, NO publishing.", flush=True)
        return 0
    urls = [upload_image(path) for path in paths]
    save_one_story_draft(channel_id, urls)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except BatchError as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
