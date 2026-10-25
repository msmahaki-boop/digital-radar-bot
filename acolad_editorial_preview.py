"""Acolad editorial preview for three expansion topics. Strictly read-only.

Reuses the Phase 1 topic definitions and audited RSS parsing code. No publication,
no modifications to active Telegram/Instagram workflows, no state history updates.
"""
from __future__ import annotations
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit, urlunsplit

import requests
import acolad_sources_preview as feeds

BASE = Path(__file__).resolve().parent
OUT = BASE / "acolad_editorial_preview_report"
OUT.mkdir(parents=True, exist_ok=True)
CONFIG = json.loads((BASE / "acolad_topics_v1.json").read_text(encoding="utf-8"))
TOPICS = {t["id"]: t for t in CONFIG["topics"]}
MODELS = list(dict.fromkeys(filter(None, [
    os.getenv("STORY_GEMINI_MODEL", "gemini-3.1-flash-lite").strip(),
    os.getenv("STORY_GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite").strip(),
])))
NOW = dt.datetime.now(dt.timezone.utc)

PLATFORM_NAMES = ["دیجی‌کالا", "دیجیکالا", "ترب", "اسنپ", "تپسی", "دیوار", "باسلام", "دیجی‌پی", "زرین‌پال", "اکوموتیو", "استارتاپ", "پلتفرم", "مارکت‌پلیس", "بازارگاه", "فروشنده", "پرداخت‌یار", "فین‌تک"]
SMALL_BIZ = ["کسب‌وکار", "فروشگاه", "فروش آنلاین", "تجارت الکترونیک", "بازاریابی", "کمپین", "مشتری", "تبلیغات", "سئو", "آنلاین", "دیجیتال", "مدیریت فروش", "باشگاه مشتریان", "پرداخت اینترنتی", "لید", "نرخ تبدیل", "خرده‌فروشی", "برند", "اتوماسیون", "وب‌سایت", "سایت فروشگاهی"]
ECONOMY_IMPACT = ["تورم", "قدرت خرید", "هزینه تولید", "مالیات", "درگاه پرداخت", "تجارت الکترونیک", "تجارت‌الکترونیک", "بنگاه", "کسب‌وکار", "بازار کار", "فروش اینترنتی", "خرده‌فروشی", "بودجه تبلیغات", "هزینه حمل‌ونقل", "مصرف‌کننده", "اقتصاد دیجیتال", "مقررات", "اینماد", "تعرفه", "نرخ ارز", "اختلال اینترنت", "صنف", "فروشگاه", "نرخ بهره", "تسهیلات"]
IRRELEVANT = ["قیمت مرغ", "قیمت برنج", "قیمت دام", "قیمت گوشت", "سهام عدالت", "یارانه‌بگیران", "حراج شمش", "قیمت سکه", "قیمت طلا", "فال روزانه", "قیمت خودرو", "نتایج قرعه کشی", "نتایج قرعه‌کشی"]


def norm(text):
    return re.sub(r"\s+", " ", (text or "").replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")).strip().casefold()


def contains_any(text, words):
    return any(norm(w) in norm(text) for w in words)


def canon(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))


def safe_age(iso_date):
    if not iso_date:
        return None
    try:
        when = dt.datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        return round((NOW - when.astimezone(dt.timezone.utc)).total_seconds() / 3600, 1)
    except (TypeError, ValueError):
        return None


def topic_match(item, cat):
    # Candidate collection only; final topical suitability is judged by Gemini.
    title, excerpt = norm(item['title']), norm(item.get('description', ''))
    combined = title + ' ' + excerpt
    if contains_any(title, IRRELEVANT) and not contains_any(title, ["فروش آنلاین", "فروشگاه", "تبلیغات", "کسب‌وکار"]):
        return False
    if cat == 'iran_platforms':
        return contains_any(title, PLATFORM_NAMES) or (contains_any(title, ["اکوسیستم", "پلتفرم", "سکوی", "تجارت الکترونیک"]) and contains_any(combined, PLATFORM_NAMES))
    if cat == 'small_business_growth':
        return contains_any(title, SMALL_BIZ) or (contains_any(title, ["تجارت", "بازار", "فروش", "رشد"]) and contains_any(excerpt, SMALL_BIZ))
    if cat == 'iran_economy':
        return contains_any(title, ECONOMY_IMPACT) or (contains_any(title, ["بازار", "هزینه", "قیمت‌گذاری", "مصرف"]) and contains_any(excerpt, ECONOMY_IMPACT))
    return False


def collect():
    output = {cat: [] for cat in TOPICS}
    health = []
    # Bring platform news from ALL audited outlets, not only sources tagged platforms in v1.
    for src in CONFIG['sources']:
        try:
            entries = feeds.get_feed(src['feed'])
            health.append({'source': src['name'], 'status': 'OK', 'items': len(entries)})
            for item in entries[:100]:
                age = safe_age(item.get('published'))
                if age is None or age < -2:
                    continue
                for cat, cfg in TOPICS.items():
                    if age > cfg['max_age_hours'] or not topic_match(item, cat):
                        continue
                    output[cat].append({
                        'category': cat,
                        'title': item['title'],
                        'excerpt': (item.get('description') or '')[:500],
                        'url': item['url'],
                        'source': src['name'],
                        'published': item['published'],
                        'age_hours': age,
                    })
            print(f"RSS OK {src['name']}: {len(entries)} item(s)", flush=True)
        except Exception as exc:
            health.append({'source': src['name'], 'status': 'WARN', 'error': type(exc).__name__})
            print(f"RSS WARN {src['name']}: {type(exc).__name__}", flush=True)
    for cat in output:
        uniq = {}
        for item in sorted(output[cat], key=lambda x: x['age_hours']):
            uniq.setdefault(canon(item['url']), item)
        pool = list(uniq.values())[:12]
        for i, item in enumerate(pool):
            item['candidate_id'] = f"{cat}_{i+1}"
        output[cat] = pool
        print(f"CANDIDATES {cat}: {len(pool)}", flush=True)
    return health, output


SYSTEM = """You are the editorial research assistant of Acolad, an Iranian digital-marketing and digital-transformation agency, NOT merely an ad agency. Audience: small-business owners, online shops and B2B managers. Expertise: websites, SEO, e-commerce, marketing in domestic messaging apps, CRM, sales automation, AI, campaign infrastructure and conversion optimization. Distinguish proven news facts from editorial interpretation and a hypothetical example. Be rigorous with economic facts. Reject generic prices of food, routine gold/stock quotations, unsupported trends, irrelevant politics and press-release hype unless a clear and documented operational business implication is evident. No made-up statistics, claims, access, fees or platform features. Do not assume headlines alone verify body text. No guarantee of sales growth. Respond exclusively in valid JSON with Persian strings."""


def ai_payload(cat, candidates):
    instructions = """Evaluate each supplied news candidate solely from supplied headline, excerpt, outlet and date. This is PREVIEW, not verification for publication. Score newsworthiness /100 using: direct relevance to an Iranian business adopting digital tools 30; actionable implications for sales/customer/operations 25; significance and specificity of the actual news 20; timeliness and novelty 15; sufficiency of textual evidence 10. No numerical claims not explicitly found in title/excerpt. Produce EXACT JSON object with 'assessments': array, one assessment per candidate, each including: 'candidate_id', 'score' integer 0..100, 'decision' one of 'consider'/'reject', 'reason' one concise Persian sentence, 'business_angle' one concise Persian sentence, 'fact_limit' one concise Persian sentence about what is not verified. Top 2 may also have 'sample_headline', 'sample_summary' (2-3 sentences: fact in source, separated from inference), and 'hypothetical_example' (ONE realistic, clearly hypothetical suggestion). For decisions: consider requires >=72 AND credible and actionable; otherwise reject. With thin evidence state this explicitly and reject regardless of curiosity factor. Don't expand facts beyond source. Existing brands and platforms must not be invented."""
    data = [{k: c[k] for k in ('candidate_id', 'title', 'excerpt', 'source', 'published')} for c in candidates]
    return {'contents': [{'role': 'user', 'parts': [{'text': SYSTEM + '\n' + instructions + '\ncategory=' + cat + '\nCANDIDATES=' + json.dumps(data, ensure_ascii=False)}]}],
            'generationConfig': {'temperature': 0.25, 'maxOutputTokens': 4200, 'responseMimeType': 'application/json'}}


def model_response(cat, candidates):
    key = os.getenv('GEMINI_API_KEY', '').strip()
    if not key:
        return None, 'GEMINI_API_KEY missing (no AI ranking performed)'
    last = 'unknown'
    for model in MODELS:
        if not re.fullmatch(r'[A-Za-z0-9._-]{2,90}', model):
            continue
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
        for attempt in range(2):
            try:
                resp = requests.post(url, json=ai_payload(cat, candidates), headers={'x-goog-api-key': key}, timeout=(8, 60))
                if resp.status_code != 200:
                    last = f'{model}: HTTP {resp.status_code}'
                    if resp.status_code in (408, 429, 500, 502, 503, 504):
                        time.sleep(2 + attempt * 2)
                        continue
                    break
                body = resp.json()
                raw = ''.join(part.get('text', '') for c in body.get('candidates', []) for part in c.get('content', {}).get('parts', []))
                parsed = json.loads(raw)
                if not isinstance(parsed, dict) or not isinstance(parsed.get('assessments'), list):
                    last = f'{model}: invalid JSON shape'
                    continue
                assessments = parsed['assessments']
                allowed = {c['candidate_id']: c for c in candidates}
                seen, cleaned = set(), []
                for item in assessments:
                    ident = item.get('candidate_id', '') if isinstance(item, dict) else ''
                    if ident not in allowed or ident in seen or type(item.get('score')) is not int:
                        continue
                    seen.add(ident)
                    score = max(0, min(100, item['score']))
                    safe = {k: str(item.get(k, ''))[:700] for k in ('reason','business_angle','fact_limit','sample_headline','sample_summary','hypothetical_example')}
                    safe['candidate_id'] = ident
                    safe['score'] = score
                    safe['decision'] = 'consider' if item.get('decision') == 'consider' and score >= 72 else 'reject'
                    cleaned.append({**allowed[ident], **safe})
                for ident, original in allowed.items():
                    if ident not in seen:
                        cleaned.append({**original, 'score': None, 'decision': 'not_assessed', 'reason': 'مدل این مورد را ارزیابی نکرده است.'})
                return sorted(cleaned, key=lambda x: -1 if x.get('score') is None else -x['score']), f'OK ({model})'
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                last = f'{model}: {type(exc).__name__}'
        print(f"Gemini fallback after {model}: {last}", flush=True)
    return None, f'unavailable: {last}'


def md_escape(s):
    return re.sub(r'[\r\n]+', ' ', str(s or '')).strip()


def main():
    health, pools = collect()
    results = {}
    lines = ['# آزمون تحریریه آکولاد — سه حوزه جدید', '', '**حالت: پیش‌نمایش صرفاً برای بازبینی انسانی. هیچ خبر یا استوری منتشر نمی‌شود.**', '', 'این آزمون از تیتر و توضیح کوتاه RSS استفاده می‌کند؛ راستی‌آزمایی مستقل خبر یا ارقام اقتصادی انجام نمی‌دهد.', '', '## منابع', '']
    for h in health:
        lines.append(f"- {h['source']}: {h['status']} ({h.get('items', h.get('error', '-'))})")
    for cat, candidates in pools.items():
        lines += ['', f"## {TOPICS[cat]['label']}", f'نامزدهای اولیه: {len(candidates)}', '']
        if not candidates:
            results[cat] = {'status': 'no_candidates', 'items': []}
            lines.append('نامزد کافی یافت نشد؛ هیچ محتوایی پیشنهاد نشده است.')
            continue
        evaluated, status = model_response(cat, candidates)
        results[cat] = {'status': status, 'items': evaluated or [], 'raw_candidates': candidates}
        lines.append(f'وضعیت Gemini: **{status}**')
        if evaluated is None:
            lines.append('رتبه‌بندی معتبر موجود نیست؛ نامزدهای خام به معنی تأیید انتشار نیستند.')
            for a in candidates[:6]:
                lines.append(f"- نامزد خام: {md_escape(a['title'])} — {a['source']}")
            continue
        for a in evaluated:
            score = str(a['score']) if a.get('score') is not None else '?'
            lines += [f"- **{a['decision']} — {score}/100:** {md_escape(a['title'])} ({a['source']})",
                      f"  - دلیل: {md_escape(a.get('reason', ''))}",
                      f"  - اثر برای کسب‌وکار: {md_escape(a.get('business_angle', ''))}",
                      f"  - محدودیت شواهد: {md_escape(a.get('fact_limit', ''))}"]
            if a.get('decision') == 'consider':
                lines += [f"  - تیتر آزمایشی: {md_escape(a.get('sample_headline', ''))}",
                          f"  - توضیح آزمایشی: {md_escape(a.get('sample_summary', ''))}",
                          f"  - مثال فرضی: {md_escape(a.get('hypothetical_example', ''))}"]
    result = {'generated_at_utc': NOW.isoformat(), 'preview_only': True, 'source_health': health, 'topics': results, 'not_fact_verified': True}
    (OUT/'editorial_review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT/'editorial_review.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('EDITORIAL PREVIEW READY: acolad_editorial_preview_report/', flush=True)
    print('NO PUBLISHING: no Telegram, Instagram, Buffer or files changed.', flush=True)

if __name__ == '__main__':
    main()
