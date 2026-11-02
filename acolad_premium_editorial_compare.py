#!/usr/bin/env python3
"""Standalone, manual-only GapGPT editorial comparison for Acolad.
Never publishes, queues, or modifies social channels. Standard library only.
Run offline by default. Live requests require explicit approval and a cost ceiling.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import random
import re
import sys
import time
import urllib.error
import urllib.request

OUT = Path('acolad_premium_editorial_results')
BASE = 'https://api.gapgpt.app/v1'
APPROVAL = 'I_APPROVE_PAID_COMPARISON'
GIFT_CONFIRM = 'I_CONFIRMED_GIFT_KEY'
MAX_OUTPUT_TOKENS = 2500
ASSUMED_INPUT_UPPER = 3500  # budget planning assumption; NOT a guaranteed tokenizer limit
PRICES = {
    'gpt-6.1-sol': (2.00, 10.00),
    'claude-sonnet-5-5': (2.00, 10.00),
    'gemini-3.1-pro-preview': (2.00, 12.00),
    'claude-opus-5-5': (4.00, 20.00),
    'gpt-6-luna': (0.10, 0.50),
}
CORE = ['gpt-6.1-sol', 'claude-sonnet-5-5', 'gemini-3.1-pro-preview', 'gpt-6-luna']
ALL = ['gpt-6.1-sol', 'claude-opus-5-5', 'claude-sonnet-5-5', 'gemini-3.1-pro-preview', 'gpt-6-luna']
FACTS = ('این یک سناریوی کاملاً فرضی است: فروشگاه اینترنتی کوچکی در ایران با هزینه‌های ارسال و بسته‌بندی روبه‌روست، '
         'اما حاشیه سود واقعی سفارش را محاسبه نکرده است. هیچ رقم، درصد، رویداد روز، تغییر تعرفه یا قانون واقعی '
         'در داده ورودی تأیید نشده است. این مسئله برای مشاوره محتوا مطرح شده، نه یک خبر.')
SYSTEM = ('تو سردبیر و نویسنده ارشد آژانس دیجیتال مارکتینگ آکولاد هستی؛ شریک رشد کسب‌وکارها در سایت، سئو، '
          'تجربه مشتری، اتوماسیون فروش و محتوا، نه صرفاً مجری تبلیغات. به فارسی دقیق، طبیعی و جذاب بنویس. '
          'مخاطب مدیران کسب‌وکار ایرانی‌اند. هیچ آمار، خبر، قانون، مطالعه، ادعای قطعی، تجربه مشتری واقعی یا '
          'افزایش تعرفه واقعی از خودت نساز. هر مثال را فرضی معرفی کن. نسبت به سود، هزینه و وعده فروش محتاط باش. '
          'لحن انسانی و غیرکلیشه‌ای باشد و مشخصاً به تصمیم مدیر کسب‌وکار کمک کند.')
PROMPT = (f'موضوع آزمون مشترک برای همه مدل‌ها:\n{FACTS}\n\n'
          'دو خروجی مجزا به فارسی و فقط بر مبنای واقعیت‌های بالا تهیه کن:\n'
          'بخش اول «استوری‌ها»: دقیقاً پنج استوری زنجیره‌ای؛ هرکدام یک عنوان کوتاه و ۲۰ تا ۴۰ کلمه متن. '
          '۱ قلاب قوی و ملموس، ۲ طرح مسئله، ۳ تحلیل مرتبط با فروش و تجربه مشتری، ۴ مثال صریحاً فرضی و '
          'یک روش سنجش، ۵ نتیجه‌گیری و دعوت طبیعی برای مشورت با آکولاد.\n'
          'بخش دوم «تلگرام»: یک تیتر مخصوص موضوع و ۱۲۰ تا ۱۶۰ کلمه در پاراگراف‌های کوتاه؛ '
          'توضیح اینکه چه چیزی داده ورودی است و چه چیزی تحلیل یا پیشنهاد آزمایشی. '
          'برای محاسبه سود، بهای خرید/تأمین کالا، ارسال، بسته‌بندی، تخفیف و هزینه‌های مرتبط را فراموش نکن. '
          'هیچ خبر تأییدنشده‌ای را به‌جای واقعیت بیان نکن.\n'
          'از تیترهای کلیشه‌ای، عبارت «تحلیل غیربدیهی»، جملات طولانی ماشینی و وعده نتیجه تضمینی پرهیز کن. '
          'خروجی را با تیترهای «استوری ۱» تا «استوری ۵» و «تلگرام» جدا کن؛ JSON لازم نیست.')

class RequestError(Exception):
    def __init__(self, status: int | None, category: str):
        super().__init__(f'HTTP {status if status is not None else "network"}: {category}')
        self.status = status
        self.category = category


def money(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    inn, out = PRICES[model]
    return (prompt_tokens * inn + completion_tokens * out) / 1_000_000


def quote_max(model: str) -> float:
    return money(model, ASSUMED_INPUT_UPPER, MAX_OUTPUT_TOKENS)


def build_payload(model: str) -> dict:
    payload = {
        'model': model,
        'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': PROMPT}],
        'max_tokens': MAX_OUTPUT_TOKENS,
        'stream': False,
    }
    if model == 'gpt-6.1-sol':
        # Explicitly NOT 'none' (unsupported on GPT-6.1 Sol); don't send temperature.
        payload['reasoning_effort'] = 'low'
    elif model == 'gpt-6-luna':
        # Proven working in the previous GapGPT connection probe.
        payload['reasoning_effort'] = 'none'
    else:
        payload['temperature'] = 0.5
    return payload


def fetch_json(path: str, key: str, payload: dict | None = None, timeout: int = 120) -> dict:
    if path not in ('/models', '/chat/completions'):
        raise ValueError('Endpoint not permitted')
    headers = {'Authorization': 'Bearer ' + key, 'Accept': 'application/json',
               'User-Agent': 'Acolad-Premium-Editorial-Lab/1.0'}
    body = None
    if payload is not None:
        headers['Content-Type'] = 'application/json'
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=body, headers=headers,
                                 method='POST' if payload is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(1_500_001)
        if len(raw) > 1_500_000:
            raise RequestError(None, 'response too large')
        result = json.loads(raw.decode('utf-8'))
        if not isinstance(result, dict):
            raise RequestError(None, 'unexpected JSON response')
        return result
    except urllib.error.HTTPError as exc:
        # NEVER persist provider body, request Authorization, API key, or full headers.
        labels = {400:'bad request/model parameters', 401:'key invalid', 402:'insufficient credit',
                  403:'model not permitted', 404:'model not found', 429:'rate limit',
                  500:'provider server error', 502:'upstream error', 503:'upstream overloaded',
                  504:'upstream timeout'}
        raise RequestError(exc.code, labels.get(exc.code, 'provider error')) from None
    except (TimeoutError, urllib.error.URLError, OSError):
        raise RequestError(None, 'network error or timeout') from None
    except (UnicodeError, json.JSONDecodeError):
        raise RequestError(None, 'non-JSON provider response') from None


def extract_response(data: dict) -> tuple[str, dict, str]:
    choices = data.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise RequestError(None, 'no completion choices')
    first = choices[0]
    message = first.get('message') or {}
    if not isinstance(message, dict):
        message = {}
    text = message.get('content')
    if isinstance(text, list):
        text = '\n'.join(x.get('text', '') for x in text if isinstance(x, dict) and isinstance(x.get('text'), str))
    if not isinstance(text, str):
        text = ''
    usage = data.get('usage') or {}
    if not isinstance(usage, dict):
        usage = {}
    safe_usage = {}
    for field in ('prompt_tokens','completion_tokens','total_tokens'):
        val=usage.get(field)
        if type(val) is int and val >= 0:
            safe_usage[field] = val
    return text.strip(), safe_usage, str(first.get('finish_reason', 'unknown'))


def safe_hint(text: str) -> list[str]:
    hints=[]
    if not text:
        hints.append('empty visible text')
    if not all(label in text for label in ('استوری ۱','استوری ۵','تلگرام')):
        hints.append('some requested headings may be absent')
    if re.search(r'\b(?:حتماً|قطعاً|تضمین)\b',text):
        hints.append('possible unsupported promise')
    if re.search(r'(?:دولت|بانک مرکزی|تعرفه جدید).{0,40}(?:اعلام|تصویب|ابلاغ)',text):
        hints.append('possible invented real-world claim')
    return hints


def make_report(mode: str, results: list[dict], notes: list[str], budget: float) -> dict:
    OUT.mkdir(exist_ok=True)
    rng=random.Random(20261102)
    ordered = list(results)
    rng.shuffle(ordered)
    aliases = {chr(65 + i): x['model'] for i, x in enumerate(ordered)}
    key_lookup={v:k for k,v in aliases.items()}
    status = 'OFFLINE_ESTIMATE_ONLY' if mode == 'offline' else (
        'REQUIRES_HUMAN_BLIND_REVIEW' if sum(bool(x.get('text')) for x in results) >= 2
        else 'INSUFFICIENT_VISIBLE_RESPONSES')
    summary={
        'mode':mode, 'run_status':status, 'publication':'NEVER',
        'requests_sent':sum(x.get('api_requested', False) for x in results),
        'visible_texts':sum(bool(x.get('text')) for x in results),
        'planning_budget_usd':budget, 'price_source':'user GapGPT screenshots 2026-11-01',
        'budget_caveat':'Estimated from listed token rates, not a provider billing hard-stop; check GapGPT wallet/logs',
        'created_utc':datetime.now(timezone.utc).isoformat(), 'notes':notes,
    }
    (OUT/'status.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'answer_key.json').write_text(json.dumps(aliases,ensure_ascii=False,indent=2),encoding='utf-8')
    public=[]; costs=[]; score=[]
    for x in ordered:
        label=key_lookup[x['model']]
        public.append((label,x.get('text',''),x.get('status','unknown'),x.get('hints',[])))
        costs.append({
            'sample':label,'model':x['model'],'status':x.get('status'),
            'input_tokens':x.get('input_tokens',''), 'output_tokens':x.get('output_tokens',''),
            'estimated_charge_usd':f"{x['cost_estimate']:.7f}" if x.get('cost_estimate') is not None else '',
            'reserved_upper_usd':f"{x['reserved_upper']:.7f}",
            'seconds':x.get('seconds',''), 'finish_reason':x.get('finish_reason',''),
            'model_reported_by_proxy':x.get('model_returned',''),
        })
        score.append({
            'sample':label,'status':x.get('status'),'evidence_accuracy_30':'',
            'useful_business_insight_25':'','natural_persian_brand_voice_20':'',
            'story_narrative_15':'','cta_relevance_10':'',
            'total_100':'','factual_red_flag_yes_no':'','human_comments':'',
        })
    def write_csv(filename,rows):
        with (OUT/filename).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)
    write_csv('cost_by_model.csv',costs)
    write_csv('human_scoring.csv',score)
    css='body{direction:rtl;font:16px/1.95 Tahoma,Arial,sans-serif;max-width:980px;margin:auto;background:#f5f2eb;padding:24px;color:#192233}section{background:white;border-radius:14px;padding:20px;margin:18px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.9 Tahoma,Arial,sans-serif}small{color:#667}'
    parts=[f'<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><style>{css}</style></head><body>',
           '<h1>مقایسه کور نویسندگی آکولاد — بدون انتشار</h1>',
           '<p>این خروجی فقط برای ارزیابی انسانی است. نخست متن‌ها را بررسی و امتیازدهی کنید، سپس answer_key.json را باز کنید.</p>',
           '<p>سناریوی مشترک: '+html.escape(FACTS)+'</p>']
    for label,body,s,hints in public:
        parts.append(f'<section><h2>نمونه {label}</h2><small>وضعیت: {html.escape(s)}</small><pre>{html.escape(body or "هیچ متن قابل‌مشاهده‌ای دریافت نشد.")}</pre><p>{html.escape("؛ ".join(hints))}</p></section>')
    parts.append('</body></html>')
    (OUT/'blind_review.html').write_text('\n'.join(parts),encoding='utf-8')
    (OUT/'README_FA.txt').write_text('اول blind_review.html و human_scoring.csv را بررسی کنید؛ سپس answer_key.json را باز کنید. مبلغ واقعی فقط در پنل GapGPT معلوم است. هیچ انتشار یا صف‌گذاری انجام نشده است.',encoding='utf-8')
    return summary


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['offline','compare'],default='offline')
    ap.add_argument('--set', choices=['core','all'],default='core')
    ap.add_argument('--budget-usd',type=float,default=0.12)
    ap.add_argument('--approval',default='')
    ap.add_argument('--gift-confirmation',default='')
    opt=ap.parse_args(argv)
    models = CORE if opt.set == 'core' else ALL
    notes=[]
    if opt.mode=='offline':
        rs=[{'model':m,'status':'QUOTE_ONLY','api_requested':False,'reserved_upper':quote_max(m)} for m in models]
        s=make_report('offline',rs,['Zero API calls: cost estimates only'],opt.budget_usd)
        print('OFFLINE_ESTIMATE_ONLY | NO API | NO PUBLICATION')
        return 0
    if opt.approval!=APPROVAL or opt.gift_confirmation!=GIFT_CONFIRM:
        print('BLOCKED: explicit consent plus gift-key confirmation are required',file=sys.stderr)
        return 2
    if not 0.01 <= opt.budget_usd <= 0.19:
        print('BLOCKED: budget must be between $0.01 and $0.19',file=sys.stderr)
        return 2
    key=os.getenv('GAPGPT_API_KEY','').strip()
    if not key:
        print('BLOCKED: GAPGPT_API_KEY missing in GitHub Secrets',file=sys.stderr)
        return 2
    try:
        catalog=fetch_json('/models',key,timeout=30)
        available={x.get('id') for x in catalog.get('data',[]) if isinstance(x,dict) and isinstance(x.get('id'),str)}
    except RequestError as exc:
        print('Model catalog could not be checked:',str(exc),file=sys.stderr)
        rs=[{'model':m,'status':'CATALOG_ERROR','api_requested':False,'reserved_upper':quote_max(m)} for m in models]
        make_report('compare',rs,[str(exc)],opt.budget_usd)
        return 0
    results=[]
    spent_or_reserved=0.0
    for model in models:
        reserve=quote_max(model)
        row={'model':model,'reserved_upper':reserve,'api_requested':False}
        if model not in available:
            row['status']='NOT_IN_CATALOG'; results.append(row);continue
        if spent_or_reserved+reserve>opt.budget_usd+1e-9:
            row['status']='BUDGET_GATE_SKIP'; results.append(row);continue
        spent_or_reserved+=reserve  # reserve before potentially charged request
        row['api_requested']=True
        start=time.monotonic()
        try:
            response=fetch_json('/chat/completions',key,payload=build_payload(model),timeout=130)
            text, usage, finish=extract_response(response)
            row.update(text=text[:50000], status='VISIBLE_NEEDS_HUMAN_REVIEW' if text else 'EMPTY_RESPONSE',
                       finish_reason=finish, model_returned=str(response.get('model',''))[:120],
                       hints=safe_hint(text), seconds=round(time.monotonic()-start,2),
                       input_tokens=usage.get('prompt_tokens',''),output_tokens=usage.get('completion_tokens',''))
            if 'prompt_tokens' in usage and 'completion_tokens' in usage:
                row['cost_estimate']=money(model,usage['prompt_tokens'],usage['completion_tokens'])
                # For budget tracking use actual usage when provided; not authoritative GapGPT bill.
                spent_or_reserved += row['cost_estimate'] - reserve  # Adjust in either direction; may block further requests
            if finish.lower() in ('length','max_tokens'):row['hints'].append('output truncated: quality review should mark incomplete')
        except RequestError as exc:
            row.update(status='API_ERROR',error_category=str(exc),seconds=round(time.monotonic()-start,2),hints=['Provider request failed; true charge unknown'])
        print(model, '|',row['status'],'|',row.get('seconds',0),'s')
        results.append(row)
    notes.append('Usage-token pricing is estimated; verify actual amount in GapGPT Logs/Wallet. No automatic retries and no paid fallback.')
    s=make_report('compare',results,notes,opt.budget_usd)
    print('STATUS:',s['run_status'],'| visible:',s['visible_texts'],'| requests:',s['requests_sent'],'| NEVER PUBLISHES')
    return 0

if __name__=='__main__':
    sys.exit(main())
