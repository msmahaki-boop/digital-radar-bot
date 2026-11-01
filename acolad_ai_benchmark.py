#!/usr/bin/env python3
"""Manual, publication-free Acolad Persian editorial quality benchmark.
All sample scenarios are explicitly hypothetical. Standard library only.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import os
from pathlib import Path
import random
import sys
import time
import urllib.error
import urllib.request

OUTPUT = Path('ai_benchmark_results')
OPENROUTER_CHAT = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_MODELS = 'https://openrouter.ai/api/v1/models'

CASES = [
    {
        'id': 'pricing', 'title': 'فروشگاه آنلاین و هزینه ارسال',
        'facts': 'سناریوی فرضی: فروشگاه کوچکی را تصور کن که هزینه ارسال و بسته‌بندی‌اش زیاد شده؛ فروشگاه هنوز داده کافی برای تعیین حاشیه سود هر سفارش ندارد. هیچ درصد، آمار یا خبر روزی تأیید نشده است.',
        'audience': 'مالک فروشگاه اینترنتی ایرانی که درگیر قیمت‌گذاری، ارسال رایگان و حفظ مشتری است.'
    },
    {
        'id': 'ai_tools', 'title': 'هوش مصنوعی برای تیم سه‌نفره',
        'facts': 'سناریوی فرضی: یک تیم سه‌نفره برای شبکه اجتماعی، پشتیبانی و فروش به چند ابزار هوش مصنوعی اشتراک داده است؛ ولی هنوز زمان صرفه‌جویی‌شده، خطاها و هزینه واقعی را اندازه نگرفته است. داده عددی واقعی وجود ندارد.',
        'audience': 'صاحب کسب‌وکار خرد که نمی‌داند ابزارهای AI واقعاً چقدر برایش ارزش دارند.'
    },
    {
        'id': 'website', 'title': 'ورود یک کسب‌وکار سنتی به فضای آنلاین',
        'facts': 'سناریوی فرضی: یک فروشگاه محلی می‌خواهد آنلاین شود؛ بودجه محدود دارد و بین سایت اختصاصی، پیج اینستاگرام و مارکت‌پلیس مردد است. هیچ نتیجه قطعی درباره همه کسب‌وکارها وجود ندارد.',
        'audience': 'کسب‌وکار ایرانی که به‌تازگی تصمیم گرفته فروش آنلاین را شروع کند.'
    }
]

SYSTEM = '''تو تحلیلگر ارشد رشد کسب‌وکار و سردبیر محتوای آکولاد هستی.
شخصیت: یک استاد خوش‌بیان و شوخ‌طبع با تجربه طولانی کار عملی در بازار آنلاین؛ فارسی روان و محاوره‌ای حرفه‌ای، هوشمند، صمیمی، دقیق، بی‌تعارف اما محترمانه. از تقلید کلام شخص حقیقی پرهیز کن.
مخاطب: صاحبان کسب‌وکارهای ایرانی که آنلاین شده‌اند یا قصد آنلاین شدن دارند.
از تیترهای کلیشه‌ای مانند «برداشت کاربردی آکولاد»، «اصل ماجرا» و «مثلاً برای یک کسب‌وکار» استفاده نکن؛ هر تیتر باید مخصوص همان موضوع باشد.
در متن هوک قوی، یک بینش غیر بدیهی، یک مثال کوچک و یک توصیه قابل اجرا داشته باش. طنز ظریف، نه شوخی بی‌جا. از ایموجی محدود و هدفمند استفاده کن.
هیچ داده، درصد، خبر، نقل‌قول یا ادعای واقعی که در حقایق ورودی نیست نساز. همه سناریوها فرضی‌اند. از حمله به اشخاص یا ادعاهای سیاسی بی‌منبع پرهیز کن.
فقط متن نهایی را بنویس؛ توضیح فرایند، عذرخواهی، هشدار متا و عبارت‌های رباتیک نده.'''


def prompt_for(case):
    return f'''موضوع: {case['title']}\nمخاطب: {case['audience']}\nشواهد موجود: {case['facts']}
سه خروجی با رعایت دقیق محدودیت‌ها بده:
الف) رشته ۵ استوری، هر استوری حداکثر ۴۰ کلمه: ۱ هوک، ۲ مسئله، ۳ تحلیل غیر بدیهی، ۴ مثال/راهکار، ۵ CTA طبیعی برای مشاوره آکولاد. هر استوری یک عنوان خلاق کوتاه و یک پاراگراف داشته باشد.
ب) متن تلگرام بین ۱۵۰ تا ۲۲۰ کلمه، با یک تیتر متفاوت و طبیعی، میان‌تیترهای اختصاصی موضوع، ۲ تا ۴ ایموجی، بولد واقعی به شیوه Markdown **...** برای گزاره‌های مهم، پاراگراف کوتاه، مثال و CTA. کلمات توخالی و کلیشه‌ای نه.
ج) «مرز واقعیت و فرض»: در یک جمله بگو کدام بخش صرفاً مثال فرضی بود.
لحن: مثل مشاور باتجربه‌ای که هم درس استراتژی داده و هم واقعاً پای دخل و خرج کسب‌وکار بوده؛ دوستانه و گاهی طعنه‌دار، با دقت علمی.
فقط با عنوان‌های «استوری‌ها»، «تلگرام»، «مرز واقعیت و فرض» خروجی بده.'''


def fetch_json(url: str, payload=None, token=None, timeout=75, extra_headers=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'Acolad-AI-Quality-Lab/1.0'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method='POST' if payload is not None else 'GET')
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Error payload may contain internal provider messages; never include credentials/URL.
            if exc.code in (429, 502, 503) and attempt == 0:
                time.sleep(5)
                continue
            raise RuntimeError(f'HTTP {exc.code} ({exc.reason})') from None
        except urllib.error.URLError as exc:
            raise RuntimeError(f'Network error: {type(exc.reason).__name__}') from None
    raise RuntimeError('Provider unavailable after retry')


def free_models(token, custom=''):
    catalog = fetch_json(OPENROUTER_MODELS, token=token, timeout=35)
    available = {m.get('id'):m for m in catalog.get('data',[]) if str(m.get('id','')).endswith(':free')}
    if not available:
        raise RuntimeError('No :free models found in current OpenRouter catalog')
    if custom.strip():
        ids = [x.strip() for x in custom.replace(',', ';').split(';') if x.strip()]
        invalid = [x for x in ids if x not in available]
        if invalid:
            raise RuntimeError('Specified IDs not in current free catalog: ' + ', '.join(invalid))
        return list(dict.fromkeys(ids))[:3]
    priority = ('qwen/', 'google/gemma', 'meta-llama/', 'nvidia/')
    ids = []
    for prefix in priority:
        family = [m for k,m in available.items() if k.startswith(prefix) and not any(bad in k for bad in ('-vl-', 'vision', 'audio', 'guard', 'safety'))]
        family.sort(key=lambda m: (m.get('context_length') or 0, m.get('id')), reverse=True)
        if family:
            ids.append(family[0]['id'])
        if len(ids) == 3:
            break
    if len(ids) < 3:
        for k in sorted(available):
            if k not in ids and not any(bad in k for bad in ('vision', 'audio', 'guard')):
                ids.append(k)
            if len(ids) == 3:
                break
    return ids


def openrouter_completion(token, model, case):
    result = fetch_json(OPENROUTER_CHAT, payload={
        'model': model,
        'messages': [{'role':'system','content':SYSTEM}, {'role':'user','content':prompt_for(case)}],
        'temperature': .67, 'max_tokens': 3100, 'stream': False,
    }, token=token, timeout=110, extra_headers={'X-Title': 'Acolad Editorial Quality Lab'})
    choice = result.get('choices', [{}])[0]
    msg = choice.get('message') or {}
    content = msg.get('content')
    if isinstance(content, list):
        content = '\n'.join(x.get('text','') for x in content if isinstance(x,dict))
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError('Empty content from model (possibly reasoning-only response)')
    return content.strip()


def gemini_completion(key, model, case):
    # The Gemini subscription and this API are separate. This key is an existing GitHub secret.
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    result = fetch_json(url, payload={
        'systemInstruction': {'parts': [{'text':SYSTEM}]},
        'contents': [{'role':'user','parts':[{'text':prompt_for(case)}]}],
        'generationConfig': {'temperature':.67, 'maxOutputTokens':3100},
    }, timeout=110, extra_headers={'x-goog-api-key':key})
    parts = ((result.get('candidates') or [{}])[0].get('content') or {}).get('parts') or []
    content = '\n'.join(p.get('text','') for p in parts if p.get('text'))
    if not content.strip():
        reason = (result.get('candidates') or [{}])[0].get('finishReason','unknown')
        raise RuntimeError('Gemini returned no text; finishReason=' + str(reason))
    return content.strip()


def make_outputs(cases, responses, label_for_model, warnings):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    mapping = {label: model for model, label in label_for_model.items()}
    (OUTPUT/'answer_key.json').write_text(json.dumps(mapping, ensure_ascii=False,indent=2),encoding='utf-8')
    (OUTPUT/'provider_status.json').write_text(json.dumps({'warnings':warnings,'models':list(label_for_model)}, ensure_ascii=False,indent=2),encoding='utf-8')
    (OUTPUT/'raw_outputs.json').write_text(json.dumps(responses, ensure_ascii=False,indent=2),encoding='utf-8')
    css = '''<style>body{margin:0;background:#f5f2eb;color:#182332;font:16px/1.9 Tahoma,Arial,sans-serif}main{max-width:980px;margin:auto;padding:28px}h1{color:#244bc3}section{background:white;border-radius:18px;margin:18px 0;padding:22px;box-shadow:0 2px 14px #0000000a}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/2.15 Tahoma,Arial,sans-serif;direction:rtl;text-align:right}small{color:#667}code{direction:ltr}</style>'''
    chunks=['<!doctype html><html lang="fa" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">'+css+'</head><body><main>','<h1>آزمایش کور تحریریه آکولاد</h1><p>نام مدل‌ها عمداً مخفی است. برای ارزیابی ابتدا متن‌ها را بخوان؛ سپس فایل answer_key.json را باز کن. هیچ‌کدام از متن‌ها برای انتشار تأیید نشده‌اند.</p>']
    rows=[]
    for case in cases:
        chunks.append('<h2>'+html.escape(case['title'])+' — سناریوی فرضی</h2><p>'+html.escape(case['facts'])+'</p>')
        for label in sorted(mapping):
            item = responses.get(case['id'],{}).get(label,{})
            body = item.get('text') or 'خطا: '+item.get('error','پاسخی دریافت نشد')
            chunks.append('<section><h3>نمونه '+label+'</h3><pre>'+html.escape(body)+'</pre></section>')
            rows.append({'case_id':case['id'],'candidate':label,'factual_fidelity_25':'','business_insight_20':'','iran_relevance_20':'','human_voice_15':'','story_hook_10':'','cta_10':'','total_100':'','notes':''})
    chunks.append('<p><small>تمام مثال‌ها فرضی‌اند؛ نمره واقعی فقط باید توسط ارزیاب انسانی و پس از بررسی ادعاها ثبت شود.</small></p></main></body></html>')
    (OUTPUT/'blind_review.html').write_text('\n'.join(chunks), encoding='utf-8')
    with (OUTPUT/'scoring_sheet.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['case_id']);w.writeheader();w.writerows(rows)
    summary = ['# Acolad AI Editorial Benchmark', '','**این اجرا هیچ محتوایی منتشر نکرده است.**', '', 'کلید رمز مدل‌ها در `answer_key.json` است؛ آن را تا پایان امتیازدهی باز نکن.', '', 'فایل `blind_review.html` را برای خواندن خروجی‌های فارسی باز کن.', '']
    if warnings:
        summary += ['## هشدارها']+[f'- {w}' for w in warnings]
    (OUTPUT/'README_RESULTS.md').write_text('\n'.join(summary),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases', type=int, choices=[2,3], default=2)
    parser.add_argument('--self-test', action='store_true')
    args=parser.parse_args()
    gemini_key=os.getenv('GEMINI_API_KEY','').strip()
    router_key=os.getenv('OPENROUTER_API_KEY','').strip()
    gemini_model=os.getenv('ACOLAD_GEMINI_MODEL','gemini-2.5-flash').strip() or 'gemini-2.5-flash'
    cases=CASES[:args.cases]
    warnings=[]
    names=[]
    if gemini_key or args.self_test:
        names.append('gemini:'+gemini_model)
    if router_key or args.self_test:
        if args.self_test:
            free=['qwen/dry-run:free','google/dry-run:free','nvidia/dry-run:free']
        else:
            try: free=free_models(router_key,os.getenv('ACOLAD_OPENROUTER_MODELS',''))
            except Exception as e:
                warnings.append('OpenRouter model discovery failed: '+str(e));free=[]
        names.extend('openrouter:'+m for m in free)
    if not names:
        print('ERROR: Add GEMINI_API_KEY or OPENROUTER_API_KEY to GitHub repository Secrets.',file=sys.stderr)
        return 2
    # Reproducible anonymous labelling; no model identity in blind review.
    rng=random.Random(20261101)
    shuffled=names[:];rng.shuffle(shuffled)
    labels={name:chr(65+i) for i,name in enumerate(shuffled)}
    responses={case['id']:{} for case in cases}
    for case in cases:
        for name in names:
            print('Comparing:',case['id'], '|', 'anonymous candidate', labels[name])
            start=time.monotonic()
            try:
                if args.self_test:
                    answer='[SELF-TEST ONLY: synthetic placeholder; not model output]\n'+prompt_for(case)[:150]
                elif name.startswith('gemini:'):
                    answer=gemini_completion(gemini_key,name.split(':',1)[1],case)
                else:
                    answer=openrouter_completion(router_key,name.split(':',1)[1],case)
                responses[case['id']][labels[name]]={'text':answer,'seconds':round(time.monotonic()-start,2)}
            except Exception as e:
                responses[case['id']][labels[name]]={'error':str(e),'seconds':round(time.monotonic()-start,2)}
                warnings.append(case['id']+' / '+labels[name]+': '+str(e))
            time.sleep(1 if not args.self_test else 0)
    make_outputs(cases,responses,labels,warnings)
    print('Saved:',OUTPUT,'| candidates:',len(names),'| cases:',len(cases))
    return 0 if any('text' in obj for case in responses.values() for obj in case.values()) else 1

if __name__=='__main__':
    sys.exit(main())
