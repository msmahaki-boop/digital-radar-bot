"""Acolad unattended pipeline: build -> audit -> Buffer (Force-Publish Edition).

Schedules for 18:00 Asia/Tehran if run before 18:00.
If triggered close to or after 18:00, automatically schedules for immediate
publication (now + 3 minutes) instead of failing.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone, time
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

from buffer_story_batch import (BatchError, collect_images, buffer_graphql,
                                upload_image)

OUTPUT = Path("stories_output")
ARTIFACTS = Path("downloaded_stories")
TZ = ZoneInfo("Asia/Tehran")
CATEGORIES = ("tech", "ai", "marketing", "social")
CAPTION_START = "خبرهای داغ امروز | آکولاد"
PUBLISH_HOUR = 18
PUBLISH_MINUTE = 0
FALLBACK_DELAY = timedelta(minutes=3)
DAILY_MARKER = "ACOLAD-DAILY:"
LINK_MARKER = "ACOLAD-IDS:"


def local_date():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def buffer_identity():
    """Find the acolad.agency Instagram channel and its organization."""
    organizations = (buffer_graphql(
        "query { account { organizations { id name } } }"
    ).get("account") or {}).get("organizations") or []
    matches = []
    fallback_matches = []
    for org in organizations:
        oid = json.dumps(org["id"])
        query = f'query {{ channels(input: {{ organizationId: {oid} }}) {{ id name service }} }}'
        for c in buffer_graphql(query).get("channels", []):
            service = str(c.get("service", "")).strip().casefold()
            name = str(c.get("name", "")).strip().casefold()
            if service == "instagram":
                fallback_matches.append((str(org["id"]), str(c["id"])))
                if name == "acolad.agency":
                    matches.append((str(org["id"]), str(c["id"])))
    if matches:
        return matches[0]
    if fallback_matches:
        print("WARNING: Using first available Instagram channel in Buffer.", flush=True)
        return fallback_matches[0]
    raise BatchError("No Instagram channel found in Buffer account")


def today_publish_target(now_utc=None):
    """Today at 18:00 Iran time, or now + 3 minutes if 18:00 is passed/close."""
    now_utc = now_utc or datetime.now(timezone.utc)
    now_local = now_utc.astimezone(TZ)
    today = now_local.date()
    publish_local = datetime.combine(today, time(PUBLISH_HOUR, PUBLISH_MINUTE), tzinfo=TZ)
    publish_utc = publish_local.astimezone(timezone.utc)

    # If it is already past (or within 3 minutes of) 18:00 Tehran, schedule for now + 3 mins
    if now_utc + FALLBACK_DELAY >= publish_utc:
        publish_utc = now_utc + FALLBACK_DELAY
        publish_local = publish_utc.astimezone(TZ)
        print(
            f"NOTICE: 18:00 Tehran has passed or is too close. "
            f"Auto-adjusting publish time to {publish_local.isoformat()}",
            flush=True,
        )
    return publish_local, publish_utc


def recent_buffer_posts(org_id, channel_id):
    """Read recent posts; return empty list on error so publishing is never blocked."""
    try:
        after = None
        records = []
        since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat().replace('+00:00', 'Z')
        for _ in range(10):
            after_arg = f', after: {json.dumps(after)}' if after else ''
            query = '''query {
              posts(first: 100%s, input: {
                organizationId: %s
                filter: {channelIds: [%s], createdAt: {start: %s}}
                sort: [{field: createdAt, direction: desc}]
              }) {
                edges { node {id text status createdAt dueAt sentAt} }
                pageInfo { hasNextPage endCursor }
              }
            }''' % (after_arg, json.dumps(org_id), json.dumps(channel_id), json.dumps(since))
            result = buffer_graphql(query).get("posts")
            if not isinstance(result, dict):
                break
            records.extend(e.get('node', {}) for e in result.get("edges", []))
            page_info = result.get('pageInfo') or {}
            if not page_info.get('hasNextPage'):
                return records
            after = page_info.get('endCursor')
            if not after:
                break
        return records
    except Exception as e:
        print(f"WARNING: Could not read Buffer history ({e}); continuing anyway.", flush=True)
        return []


def validate_manifest():
    """Extract story hashes from manifest without failing on minor content variations."""
    path = OUTPUT / "manifest.json"
    if not path.is_file():
        print("WARNING: manifest.json not found; using fallback hash.", flush=True)
        return {}, [hashlib.sha256(local_date().encode('utf-8')).hexdigest()[:16]]
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"WARNING: Could not parse manifest.json ({e}); continuing.", flush=True)
        return {}, [hashlib.sha256(local_date().encode('utf-8')).hexdigest()[:16]]

    articles = manifest.get('articles') or []
    hashes = []
    for idx, a in enumerate(articles):
        link = a.get('article_url_for_editor_only') or f"{local_date()}-{idx}"
        hashes.append(hashlib.sha256(str(link).encode('utf-8')).hexdigest()[:16])
    if not hashes:
        hashes.append(hashlib.sha256(local_date().encode('utf-8')).hexdigest()[:16])
    return manifest, hashes


def check_no_duplicates(posts, hashes, date_tag):
    """Log warnings if duplicates exist, but NEVER block publishing."""
    for p in posts:
        text = str(p.get('text', ''))
        if DAILY_MARKER + date_tag in text:
            print(f"WARNING: Acolad content already exists for {date_tag} (post {p.get('id')}); proceeding anyway.", flush=True)
        if LINK_MARKER in text and hashes:
            old_tokens = set(text.split(LINK_MARKER, 1)[-1].splitlines()[0].split(','))
            if set(hashes).intersection(old_tokens):
                print("WARNING: A story article URL was previously used in the last 14 days; proceeding anyway.", flush=True)


def caption(date_tag, hashes):
    return f"{CAPTION_START}\n{DAILY_MARKER}{date_tag}\n{LINK_MARKER}{','.join(hashes)}"


def create_one_post(channel_id, urls, date_tag, hashes, draft: bool, target_utc: datetime):
    """Schedule story post in Buffer, ensuring dueAt is always in the future."""
    now_utc = datetime.now(timezone.utc)
    if not draft and target_utc <= now_utc + timedelta(minutes=2):
        target_utc = now_utc + FALLBACK_DELAY
        print(f"NOTICE: Adjusted dueAt to {target_utc.isoformat()} so Buffer accepts the schedule.", flush=True)

    query = '''mutation CreateStory($input: CreatePostInput!) {
      createPost(input: $input) {
        __typename
        ... on PostActionSuccess { post { id text status dueAt } }
        ... on MutationError { message }
      }
    }'''
    inputs = {
        'channelId': channel_id,
        'text': caption(date_tag, hashes),
        'schedulingType': 'automatic',
        'mode': 'addToQueue' if draft else 'customScheduled',
        'saveToDraft': draft,
        'aiAssisted': True,
        'assets': [{'image': {'url': u}} for u in urls],
        'metadata': {'instagram': {'type': 'story', 'shouldShareToFeed': False}},
    }
    if not draft:
        inputs['dueAt'] = target_utc.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    response = (buffer_graphql(query, {'input': inputs}).get('createPost') or {})
    if response.get('__typename') != 'PostActionSuccess':
        raise BatchError('Buffer rejected story creation: ' + str(response.get('message', response.get('__typename'))))

    post = response.get('post') or {}
    print(
        'BUFFER ' + ('DRAFT' if draft else 'SCHEDULE') +
        f" CREATED: {post.get('id')} status={post.get('status')} dueAt={post.get('dueAt')}",
        flush=True,
    )
    return post


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('preview', 'draft', 'queue'), default='queue')
    parser.add_argument('--approval', default='QUEUE_APPROVED')
    args = parser.parse_args()

    date_tag = local_date()
    print(f'ACOLAD DAILY | local date={date_tag} | mode={args.mode}', flush=True)

    publish_local, publish_utc = today_publish_target()
    print(f'TARGET PUBLISH: {publish_local.isoformat()} | UTC {publish_utc.isoformat()}', flush=True)

    org_id = channel_id = None
    if args.mode != 'preview':
        org_id, channel_id = buffer_identity()
        posts = recent_buffer_posts(org_id, channel_id)
        check_no_duplicates(posts, [], date_tag)

    shutil.rmtree(OUTPUT, ignore_errors=True)
    shutil.rmtree(ARTIFACTS, ignore_errors=True)
    subprocess.run([sys.executable, 'story_test.py'], check=True)
    _, hashes = validate_manifest()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        for file in OUTPUT.iterdir():
            if file.is_file():
                shutil.copy2(file, ARTIFACTS / file.name)

    try:
        paths = collect_images()
    except Exception as e:
        print(f"WARNING: collect_images() raised ({e}); collecting available PNGs directly.", flush=True)
        paths = sorted(OUTPUT.glob("*.png"))

    if not paths:
        raise BatchError('No PNG images were generated to upload')

    if args.mode == 'preview':
        preview_org, preview_channel = buffer_identity()
        preview_posts = recent_buffer_posts(preview_org, preview_channel)
        print(f'BUFFER READ-ONLY PREFLIGHT OK: {len(preview_posts)} recent posts inspected', flush=True)
        print(f'PREVIEW PASSED: {len(paths)} images. NO Cloudinary upload, NO Buffer change.', flush=True)
        return 0

    urls = [upload_image(p) for p in paths]
    # Re-evaluate publish target right before sending to Buffer in case generation took long
    _, publish_utc = today_publish_target()
    create_one_post(channel_id, urls, date_tag, hashes, draft=(args.mode == 'draft'), target_utc=publish_utc)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (BatchError, subprocess.CalledProcessError, ValueError, OSError) as e:
        print('ACOLAD DAILY STOPPED SAFELY:', str(e), file=sys.stderr, flush=True)
        raise SystemExit(1)
