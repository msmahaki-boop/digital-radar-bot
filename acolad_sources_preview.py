"""Safe, read-only RSS source check for Acolad's three new editorial areas.
No credentials, Gemini calls, scheduling or Telegram/Instagram publishing.
"""
from __future__ import annotations
import datetime as dt
import email.utils
import html
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / 'acolad_topics_v1.json').read_text(encoding='utf-8'))
REPORT = ROOT / 'acolad_new_topics_report'
REPORT.mkdir(exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)


def plain(s: str) -> str:
    s = re.sub(r'<[^>]*>', ' ', s or '')
    s = html.unescape(s).replace('\u200c', '‌')
    return re.sub(r'\s+', ' ', s).strip()


def tagname(element):
    return element.tag.rsplit('}', 1)[-1]


def direct_child_text(node, name):
    for child in node:
        if tagname(child) == name:
            return ''.join(child.itertext()).strip()
    return ''


def parsedate(s):
    if not s:
        return None
    try:
        date = email.utils.parsedate_to_datetime(s)
        if date:
            return date.replace(tzinfo=dt.timezone.utc) if date.tzinfo is None else date.astimezone(dt.timezone.utc)
    except (ValueError, TypeError, IndexError):
        pass
    try:
        date = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
        return date.replace(tzinfo=dt.timezone.utc) if date.tzinfo is None else date.astimezone(dt.timezone.utc)
    except (ValueError, TypeError):
        return None


def parse_feed(data):
    root = ET.fromstring(data)
    items = []
    for node in root.iter():
        if tagname(node) not in ('item', 'entry'):
            continue
        title = plain(direct_child_text(node, 'title'))
        description = plain(direct_child_text(node, 'description') or direct_child_text(node, 'summary') or direct_child_text(node, 'content'))
        link = direct_child_text(node, 'link')
        if not link:
            for child in node:
                if tagname(child) == 'link' and child.attrib.get('href'):
                    link = child.attrib['href']
                    if child.attrib.get('rel') in ('alternate', None):
                        break
        date = parsedate(direct_child_text(node, 'pubDate') or direct_child_text(node, 'published') or direct_child_text(node, 'updated') or direct_child_text(node, 'date'))
        if title and link.startswith(('https://', 'http://')):
            items.append({'title': title, 'description': description[:1000], 'url': link, 'published': date.isoformat() if date else None, 'date_obj': date})
    return items


def get_feed(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; AcoladFeedPreview/1.0; +https://acolad.ir)', 'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*'})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = response.read(3_000_001)
    if len(data) > 3_000_000:
        raise ValueError('Feed too large')
    return parse_feed(data)


def score_item(item, topic):
    text = (item['title'] + ' ' + item['description']).casefold()
    title = item['title'].casefold()
    required = any(word.casefold() in text for word in topic['must_include_any'])
    hits = [word for word in topic['keywords'] if word.casefold() in text]
    if not required or not hits:
        return None
    # Simple relevance signal for SOURCE AUDIT ONLY, not Gemini's editorial rating.
    score = min(100, 20 + 13 * sum(k.casefold() in title for k in hits) + 4 * len(hits))
    age = None
    if item['date_obj']:
        age = round((NOW - item['date_obj']).total_seconds() / 3600, 1)
        if age < -3 or age > topic['max_age_hours']:
            return None
    else:
        # No date = useful for diagnosing feed, but not eligible for auto-publish.
        score = max(0, score - 30)
    return {'category': topic['id'], 'topic_label': topic['label'], 'title': item['title'], 'url': item['url'], 'published': item['published'], 'age_hours': age, 'keyword_hits': hits[:8], 'preliminary_relevance_score': score, 'publish_eligible': bool(item['date_obj'])}


def main():
    by_topic = {t['id']: [] for t in CFG['topics']}
    topic_by_id = {t['id']: t for t in CFG['topics']}
    status = []
    for source in CFG['sources']:
        try:
            articles = get_feed(source['feed'])
            print(f"FEED OK: {source['name']} ({len(articles)} entries)", flush=True)
            status.append({'source': source['name'], 'url': source['feed'], 'status': 'OK', 'entries': len(articles)})
            for item in articles[:50]:
                for cat in source['topics']:
                    result = score_item(item, topic_by_id[cat])
                    if result:
                        result['source'] = source['name']
                        by_topic[cat].append(result)
        except Exception as ex:
            err = f'{type(ex).__name__}: {ex}'[:200]
            print(f"FEED WARN: {source['name']} ({err})", flush=True)
            status.append({'source': source['name'], 'url': source['feed'], 'status': 'WARNING', 'error': err})
    deduped = {}
    for cat, candidates in by_topic.items():
        unique = {}
        for x in sorted(candidates, key=lambda r: r['preliminary_relevance_score'], reverse=True):
            key = x['url'].split('?')[0].rstrip('/')
            unique.setdefault(key, x)
        deduped[cat] = list(unique.values())[:8]
        print(f"CATEGORY {cat}: {len(unique)} relevant candidates, {len(deduped[cat])} shown", flush=True)
    report = {'generated_at_utc': NOW.isoformat(), 'read_only': True, 'not_editorial_verification': True, 'feeds': status, 'topics': deduped}
    (REPORT / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# پیش‌نمایش توسعه ۷ حوزه آکولاد: آزمون ۳ حوزه جدید', '', 'این گزارش فقط برای بررسی منابع و تناسب اولیه خبر است و انتشار یا امتیازدهی واقعی Gemini انجام نمی‌دهد.', '', '## وضعیت خوراک‌ها', '']
    for src in status:
        lines.append(f"- **{src['source']}**: {src['status']} — {src.get('entries', src.get('error',''))}")
    for topic in CFG['topics']:
        lines += ['', f"## {topic['label']}", f"بازه پیشنهادی: {topic['max_age_hours']} ساعت", '']
        rows = deduped[topic['id']]
        if not rows:
            lines.append('خبر مرتبط تازه‌ای در این آزمون پیدا نشد؛ منابع و فیلترها باید بازبینی شوند.')
        for r in rows:
            age = f"{r['age_hours']} ساعت" if r['age_hours'] is not None else 'نامعلوم؛ انتشار خودکار ممنوع'
            lines.append(f"- **{r['title']}** — {r['source']}، {age}، تناسب اولیه {r['preliminary_relevance_score']}/100 — {r['url']}")
    (REPORT / 'audit.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('AUDIT READY: acolad_new_topics_report/audit.md and audit.json. Nothing published.', flush=True)


if __name__ == '__main__':
    main()
