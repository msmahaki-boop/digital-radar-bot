"""Acolad Digital Radar → one Buffer *draft* Story from an existing Actions artifact.

Important safeguards:
- Requires explicit '--create-draft yes' to upload media or create a Buffer draft.
- Never asks Buffer to publish, schedule, share now or queue content.
- Does not call bot.py, Gemini, or change sent_news.json.
- Only one image per invocation, and only a channel named acolad.agency.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

import requests
from PIL import Image

BUFFER_API = "https://api.buffer.com"
BUFFER_CHANNEL_NAME = "acolad.agency"
ARTIFACT_DIR = Path("downloaded_stories")


class WorkflowError(Exception):
    pass


def validate_png(filename: str) -> Path:
    """Only read a PNG from the downloaded artifact, never from arbitrary paths."""
    if not filename or Path(filename).name != filename or not filename.endswith(".png"):
        raise WorkflowError("Choose one PNG filename from the downloaded artifact (e.g. 01_intro.png).")
    path = ARTIFACT_DIR / filename
    if not path.is_file():
        options = sorted(x.name for x in ARTIFACT_DIR.glob("*.png"))
        raise WorkflowError(f"Image {filename!r} not found. Available PNG files: {options}")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise WorkflowError("Image larger than 20MB; choose a smaller story PNG.")
    with Image.open(path) as im:
        if im.format != "PNG":
            raise WorkflowError("Input file is not a valid PNG.")
        w, h = im.size
        if w < 600 or h < 1000:
            raise WorkflowError(f"Image dimensions too small: {w}x{h}.")
        if abs((w / h) - 9 / 16) > 0.015:
            raise WorkflowError(f"Expected vertical 9:16 story, got {w}x{h}.")
        im.verify()
    print(f"IMAGE OK: {filename} ({w}x{h})")
    return path


def graphql(query: str, variables: dict | None = None) -> dict:
    api_key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not api_key:
        raise WorkflowError("GitHub Secret BUFFER_API_KEY is missing.")
    payload = {"query": query, "variables": variables or {}}
    try:
        response = requests.post(
            BUFFER_API, json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + api_key,
            }, timeout=40,
        )
        response.raise_for_status()
        parsed = response.json()
    except requests.RequestException as exc:
        code = getattr(getattr(exc, "response", None), "status_code", "network error")
        raise WorkflowError(f"Buffer connection failed (HTTP/status: {code}).") from None
    except ValueError:
        raise WorkflowError("Buffer returned an invalid JSON response.") from None

    if parsed.get("errors"):
        error = parsed["errors"][0]
        raise WorkflowError("Buffer GraphQL error: " + str(error.get("message", "unknown"))[:200])
    if not isinstance(parsed.get("data"), dict):
        raise WorkflowError("Buffer GraphQL response has no data.")
    return parsed["data"]


def find_account_channel() -> str:
    organizations = graphql("query { account { organizations { id name } } }")["account"]["organizations"]
    matches = []
    for org in organizations:
        org_id = json.dumps(org["id"])
        query = f'query {{ channels(input: {{ organizationId: {org_id} }}) {{ id name service }} }}'
        for channel in graphql(query).get("channels", []):
            if (str(channel.get("name", "")).casefold() == BUFFER_CHANNEL_NAME
                    and str(channel.get("service", "")).casefold() == "instagram"):
                matches.append(channel)
    if len(matches) != 1:
        raise WorkflowError(f"Found {len(matches)} Instagram channels named {BUFFER_CHANNEL_NAME!r}; expected exactly one.")
    channel = matches[0]
    print(f"BUFFER OK: Instagram channel {channel['name']} (ID: {channel['id']})")
    return channel["id"]


def upload_to_cloudinary(image_path: Path) -> str:
    """Cloudinary's signed Basic Auth upload API; only a public secure_url is returned."""
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    key = os.getenv("CLOUDINARY_API_KEY", "").strip()
    secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    if not all([cloud_name, key, secret]):
        raise WorkflowError(
            "Cloudinary secrets missing: CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET."
        )
    if not cloud_name.replace("-", "").replace("_", "").isalnum():
        raise WorkflowError("Invalid CLOUDINARY_CLOUD_NAME format.")
    url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    try:
        with image_path.open("rb") as img:
            result = requests.post(url, auth=(key, secret),
                                   files={"file": (image_path.name, img, "image/png")},
                                   timeout=90)
        result.raise_for_status()
        info = result.json()
    except requests.RequestException as exc:
        code = getattr(getattr(exc, "response", None), "status_code", "network error")
        raise WorkflowError(f"Cloudinary upload failed (HTTP/status: {code}).") from None
    except ValueError:
        raise WorkflowError("Cloudinary returned an invalid JSON response.") from None
    direct_url = info.get("secure_url", "")
    if not direct_url.startswith("https://res.cloudinary.com/"):
        raise WorkflowError("Cloudinary did not provide a direct HTTPS media URL.")
    print("CLOUDINARY OK: one PNG uploaded and public delivery URL created")
    return direct_url


def create_instagram_story_draft(channel_id: str, image_url: str) -> str:
    """Create a private-to-Buffer DRAFT; it never enters the posting queue."""
    query = """
    mutation SaveStoryDraft($input: CreatePostInput!) {
      createPost(input: $input) {
        __typename
        ... on PostActionSuccess { post { id text } }
        ... on MutationError { message }
      }
    }
    """
    data = graphql(query, {
        "input": {
            "channelId": channel_id,
            "text": "خبرهای داغ امروز | آکولاد",
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "saveToDraft": True,
            "aiAssisted": True,
            "assets": [{"image": {"url": image_url}}],
            "metadata": {"instagram": {"type": "story", "shouldShareToFeed": False}},
        }
    })["createPost"]
    if data.get("__typename") != "PostActionSuccess":
        raise WorkflowError("Buffer did not create a draft: " + str(data.get("message", data.get("__typename", "unknown")))[:250])
    post_id = data.get("post", {}).get("id")
    if not post_id:
        raise WorkflowError("Buffer success payload lacks a post ID; please inspect Drafts manually.")
    print(f"DRAFT CREATED in Buffer; post ID: {post_id}")
    print("NO PUBLISHING / NO SCHEDULING. Open Buffer → acolad.agency → Drafts.")
    return post_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage one Acolad Instagram draft test")
    parser.add_argument("--story", default="01_intro.png", help="PNG filename from Actions artifact")
    parser.add_argument("--create-draft", choices=("no", "yes"), default="no")
    args = parser.parse_args()
    path = validate_png(args.story)
    channel_id = find_account_channel()
    if args.create_draft != "yes":
        print("DRY RUN PASSED. No upload and NO BUFFER DRAFT created.")
        print("When approved, set create_draft to 'yes' in manual workflow inputs.")
        return 0
    media_url = upload_to_cloudinary(path)
    create_instagram_story_draft(channel_id, media_url)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except WorkflowError as error:
        print("ERROR:", error, file=sys.stderr)
        sys.exit(1)
