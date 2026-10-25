"""Acolad unattended pipeline: build -> audit -> check duplicates -> Buffer.

Default mode PREVIEW, which NEVER uploads or creates anything in Buffer.
Scheduled mode is gated by an explicit GitHub repository variable.
Daily queue mode schedules an exact 18:00 Asia/Tehran publication, not a generic Buffer slot.
Works with existing V2.6 story_test.py and buffer_story_batch.py.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone, time
import hashlib
import json
import os
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
from story_data_builder import ACTIVE_TOPICS as CATEGORIES
CAPTION_START = "خبرهای داغ امروز | آکولاد"
PUBLISH_HOUR = 18
PUBLISH_MINUTE = 0
MIN_PUBLISH_LEAD = timedelta(minutes=20)
DAILY_MARKER = "ACOLAD-DAILY:"
LINK_MARKER = "ACOLAD-IDS:"


def local_date():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def buffer_identity():
    """Find exactly one verified Instagram channel and its organization."""
    organizations = (buffer_graphql(
        "query { account { organizations { id name } } }"
    ).get("account") or {}).get("organizations") or []
    matches = []
    for org in organizations:
        oid = json.dumps(org["id"])
        query = f'query {{ channels(input: {{ organizationId: {oid} }}) {{ id name service }} }}'
        for c in buffer_graphql(query).get("channels", []):
            if (str(c.get("name", "")).strip().casefold() == "acolad.agency"
                    and str(c.get("service", "")).strip().casefold() == "instagram"):
                matches.append((str(org["id"]), str(c["id"])))
    if len(matches) != 1:
        raise BatchError(f"Expected exactly one acolad.agency Instagram channel; got {len(matches)}")
    return matches[0]


def today_publish_target(now_utc=None):
    """Today at 18:00 Iran standard time, represented in UTC for Buffer."""
    now_utc = now_utc or datetime.now(timezone.utc)
    today = now_utc.astimezone(TZ).date()
    publish_local = datetime.combine(today, time(PUBLISH_HOUR, PUBLISH_MINUTE), tzinfo=TZ)
    publish_utc = publish_local.astimezone(timezone.utc)
    return publish_local, publish_utc


def recent_buffer_posts(org_id, channel_id):
    """Read a bounded window of posts; fail closed if pagination incomplete."""
    after = None
    records = []
    # Covers all statuses, including drafts, scheduled, sending and sent.
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat().replace('+00:00','Z')
    for page in range(10):
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
            raise BatchError("Unable to retrieve Buffer history; refuse to queue")
        records.extend(e.get('node', {}) for e in result.get("edges", []))
        page_info = result.get('pageInfo') or {}
        if not page_info.get('hasNextPage'):
            return records
        after = page_info.get('endCursor')
        if not after:
            raise BatchError('Incomplete Buffer post pagination')
    raise BatchError('Buffer history too long for safe duplication check')


def validate_manifest():
    path = OUTPUT / "manifest.json"
    if not path.is_file():
        raise BatchError("Story manifest not generated")
    manifest = json.loads(path.read_text(encoding='utf-8'))
    created = datetime.fromisoformat(str(manifest.get("generated_utc", "")).replace('Z','+00:00'))
    if created.tzinfo is None or abs((datetime.now(timezone.utc) - created).total_seconds()) > 1800:
        raise BatchError("Story manifest is not fresh")
    if manifest.get('ai_used') is not True:
        raise BatchError("Gemini not used successfully; no automatic scheduling")
    articles = manifest.get('articles') or []
    categories = [a.get('topic') for a in articles]
    if len(articles) != 4 or categories != list(CATEGORIES):
        raise BatchError(f"For unattended scheduling exactly 4 validated stories are required; got {categories!r}")
    hashes = []
    for a in articles:
        link = a.get('article_url_for_editor_only', '')
        body = a.get('story_text', '')
        title = a.get('headline', '')
        if not link.startswith(('https://', 'http://')) or len(body) < 110 or len(title) < 12:
            raise BatchError(f"News missing concrete article, substantive text or title: {a.get('topic')}")
        hashes.append(hashlib.sha256(link.encode('utf-8')).hexdigest()[:16])
    if len(set(hashes)) != 4:
        raise BatchError("Article reused across topics")
    return manifest, hashes


def check_no_duplicates(posts, hashes, date_tag):
    """Fail closed: today's manual stories, pending auto posts, or old article reused."""
    for p in posts:
        text = str(p.get('text', ''))
        status = str(p.get('status', '')).lower()
        if DAILY_MARKER + date_tag in text:
            raise BatchError(f"Acolad content already created for {date_tag}; post {p.get('id')}")
        # Also cover the original manually-created story, which had no marker.
        post_days = set()
        for date_field in ('createdAt', 'dueAt', 'sentAt'):
            date_str = p.get(date_field)
            if date_str:
                try:
                    post_days.add(datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
                                  .astimezone(TZ).date().isoformat())
                except (ValueError, TypeError):
                    raise BatchError('Cannot verify an existing post date; refuse to queue')
        if date_tag in post_days and text.strip().startswith(CAPTION_START):
            raise BatchError('An Acolad story sequence already exists for today (manual or automated)')
        if status in ('scheduled', 'sending') and DAILY_MARKER in text:
            raise BatchError('Another automated Acolad story sequence is still pending in Buffer')
        if LINK_MARKER in text:
            old_tokens = set(text.split(LINK_MARKER, 1)[-1].splitlines()[0].split(','))
            if set(hashes).intersection(old_tokens):
                raise BatchError('A story article URL was previously used in the last 14 days')


def caption(date_tag, hashes):
    return f"{CAPTION_START}\n{DAILY_MARKER}{date_tag}\n{LINK_MARKER}{','.join(hashes)}"


def create_one_post(channel_id, urls, date_tag, hashes, draft: bool, target_utc: datetime):
    """Only draft or schedule exactly 18:00 Tehran today; never share-now."""
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
    if not post.get('id'):
        raise BatchError('Buffer responded success without an ID; inspect the Buffer queue/drafts manually')
    if draft and post.get('status') != 'draft':
        raise BatchError(f"Unexpected Buffer draft status: {post.get('status')}")
    if not draft and post.get('status') not in ('scheduled', 'sending', 'buffer'):
        raise BatchError(f"Buffer returned unexpected status {post.get('status')}; post ID {post['id']}; CHECK BUFFER MANUALLY")
    if not draft:
        due_at = post.get('dueAt')
        if not due_at:
            raise BatchError(f"Buffer returned no dueAt for post {post['id']}; CHECK BUFFER MANUALLY")
        try:
            verified_due = datetime.fromisoformat(str(due_at).replace('Z', '+00:00')).astimezone(timezone.utc)
        except ValueError:
            raise BatchError(f"Buffer returned invalid dueAt for post {post['id']}; CHECK BUFFER MANUALLY")
        if abs((verified_due - target_utc).total_seconds()) > 60:
            raise BatchError(f"BUFFER TIMING MISMATCH for post {post['id']}: {due_at}; CHECK AND FIX BUFFER MANUALLY")
    print('BUFFER ' + ('DRAFT' if draft else 'SCHEDULE') + f" CREATED: {post['id']} status={post.get('status')} dueAt={post.get('dueAt')}", flush=True)
    return post


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('preview', 'draft', 'queue'), default='preview')
    parser.add_argument('--approval', default='')
    args = parser.parse_args()
    date_tag = local_date()
    print(f'ACOLAD DAILY | local date={date_tag} | mode={args.mode}', flush=True)
    if args.mode == 'queue' and args.approval != 'QUEUE_APPROVED':
        raise BatchError('Queue mode requires QUEUE_APPROVED (automated workflow supplies it only when explicitly enabled)')
    publish_local, publish_utc = today_publish_target()
    print(f'TARGET PUBLISH: {publish_local.isoformat()} | UTC {publish_utc.isoformat()}', flush=True)
    if args.mode == 'queue' and datetime.now(timezone.utc) + MIN_PUBLISH_LEAD >= publish_utc:
        raise BatchError('Too late to safely prepare todays 18:00 Tehran stories; refuse to queue for tomorrow')
    org_id = channel_id = None
    if args.mode != 'preview':
        org_id, channel_id = buffer_identity()
        # Do an early preflight so we don't burn Gemini quota if published today.
        posts = recent_buffer_posts(org_id, channel_id)
        check_no_duplicates(posts, [], date_tag)

    shutil.rmtree(OUTPUT, ignore_errors=True)
    shutil.rmtree(ARTIFACTS, ignore_errors=True)
    subprocess.run([sys.executable, 'story_test.py'], check=True)
    _, hashes = validate_manifest()
    ARTIFACTS.mkdir(parents=True)
    for file in OUTPUT.iterdir():
        if file.is_file():
            shutil.copy2(file, ARTIFACTS / file.name)
    paths = collect_images()  # Reuse proven PNG size and filename validation.
    if len(paths) != 5:
        raise BatchError('Refusing automatic run without 5 PNGs')
    if args.mode == 'preview':
        # Validate read-only Buffer history query before enabling unattended queue.
        # Do not enforce duplicate rules in a preview: the operator may already
        # have posted a manual story today.
        preview_org, preview_channel = buffer_identity()
        preview_posts = recent_buffer_posts(preview_org, preview_channel)
        print(f'BUFFER READ-ONLY PREFLIGHT OK: {len(preview_posts)} recent posts inspected', flush=True)
        print('PREVIEW PASSED: 5 validated images. NO Cloudinary upload, NO Buffer change.', flush=True)
        return 0
    # Repeat uniqueness check after expensive generation, just before any write.
    posts = recent_buffer_posts(org_id, channel_id)
    check_no_duplicates(posts, hashes, date_tag)
    # Recheck time before any media writes: Gemini may have taken a long time.
    if args.mode == 'queue' and datetime.now(timezone.utc) + MIN_PUBLISH_LEAD >= publish_utc:
        raise BatchError('Generation finished too near 18:00; not uploading or scheduling stale stories')
    urls = [upload_image(p) for p in paths]
    # Recheck again before creating the public-facing scheduled post.
    if args.mode == 'queue' and datetime.now(timezone.utc) + timedelta(minutes=5) >= publish_utc:
        raise BatchError('Cloudinary upload finished too late; do not schedule')
    create_one_post(channel_id, urls, date_tag, hashes, draft=(args.mode == 'draft'), target_utc=publish_utc)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (BatchError, subprocess.CalledProcessError, ValueError, OSError) as e:
        print('ACOLAD DAILY STOPPED SAFELY:', str(e), file=sys.stderr, flush=True)
        raise SystemExit(1)
