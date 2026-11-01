#!/usr/bin/env python3
"""Acolad AI Quality Lab V3 — independent, manual, zero publishing.
Python stdlib only. API use is opt-in and OpenRouter :free exclusively.
The validation gate is NOT human fact-checking nor permission to publish.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import random
import re
import sys
import time
from datetime import datetime, timezone
import urllib.error
import urllib.request

OUTPUT = Path('ai_quality_v3_results')
MODEL_CATALOG = 'https://openrouter.ai/api/v1/models'
CHAT_API = 'https://openrouter.ai/api/v1/chat/completions'
TIMEOUT = 85
MAX_MODELS = 3
PERSIAN = re.compile(r'[\u0600-\u06ff]')
ENGLISH = re.compile(r'[A-Za-z]')
DIGITS = re.compile(r'[\d\u06f0-\u06f9\u0660-\u0669]')
BAD_HYPE = ('تضمین می‌شود', 'تضمین شده', 'قطعاً', 'بدون شک', 'صددرصد', '۱۰۰٪', '100%', 'حتماً سود', 'سود تضمینی')
# Keep this narrow; legitimate English words in technical stories may appear.
STRANGE_MIX = re.compile(r'[\u0600-\u06ff][A-Za-z]{2,}|[A-Za-z]{2,}[\u0600-\u06ff]')
CASES = [
 {'id':'shipping','title':'هزینه واقعی هر سفارش','facts':'سناریوی کاملاً فرضی: فروشگاه اینترنتی کوچکی با افزایش هزینه ارسال و بسته‌بندی روبه‌رو شده و هنوز سود واقعی هر سفارش را نمی‌سنجد. هیچ درصد، عدد هزینه یا خبر تأییدشده‌ای نداریم.'},
 {'id':'ai_workflow','title':'ابزارهای AI برای تیم کوچک','facts':'سناریوی کاملاً فرضی: تیم سه‌نفره‌ای چند ابزار هوش مصنوعی برای پشتیبانی و محتوا به‌کار گرفته، ولی تأثیر آن را بر زمان یا کیفیت کار اندازه نگرفته است. هیچ عدد یا مطالعه مشخصی در دست نیست.'},
 {'id':'local_online','title':'انتخاب مسیر فروش آنلاین','facts':'سناریوی کاملاً فرضی: یک فروشگاه محلی با بودجه محدود بین ساخت سایت، اینستاگرام و فروش در مارکت‌پلیس مردد است. هیچ گزینه‌ای برای همه کسب‌وکارها بهترین نیست و هیچ آمار واقعی ارائه نشده است.'},
]
SYSTEM = '''تو نویسنده ارشد آژانس دیجیتال مارکتینگ آکولاد هستی: شریک رشد دیجیتال کسب‌وکار، نه صرفاً آژانس تبلیغاتی. فارسی روان، دقیق و انسانی بنویس.\nورودی‌ها سناریوی فرضی هستند؛ آنها را به خبر روز، تجربه واقعی آکولاد، داده اثبات‌شده یا مطالعه منتشرشده تبدیل نکن.\nاز عدد، درصد، قانون، مرجع، ادعا، نقل‌قول و نتیجه قطعیِ بیرون از داده ورودی استفاده نکن.\nمرز واقعیت، تحلیل، مثال فرضی و پیشنهاد آزمایشی روشن باشد. از عبارت‌های تضمینی، تبلیغاتی و کلیشه ماشینی دوری کن.\nصرفاً یک JSON معتبر برگردان؛ هیچ Markdown، کدبلاک یا متن بیرون JSON ننویس.'''

def prompt(case):
    return (f"موضوع: {case['title']}\nداده مجاز: {case['facts']}\n" +
      '''یک بسته یکپارچه خروجی بده. قالب JSON دقیقاً:\n{"stories":[{"title":"...","body":"..."},{"title":"...","body":"..."},{"title":"...","body":"..."},{"title":"...","body":"..."},{"title":"...","body":"..."}],"telegram":{"title":"...","body":"..."},"evidence_boundary":"...","hypothetical_example":"...","testable_action":"..."}\nاستوری ۱ هوک کنجکاوی، ۲ مسئله، ۳ تحلیل غیربدیهی، ۴ مثال *صریحاً فرضی*، ۵ دعوت انسانی بدون وعده نتیجه تضمینی. بدنه هر استوری ۲۰ تا ۵۰ کلمه فارسی.\nمتن تلگرام ۱۲۰ تا ۲۱۰ کلمه، پاراگراف کوتاه و نکته کاربردی. مرز شواهد در evidence_boundary روشن باشد. hypothetical_example باید لفظ «فرضی» را داشته باشد. testable_action یک پیشنهاد قابل‌اندازه‌گیری، بدون تضمین نتیجه باشد.\nهر پنج عنوان متفاوت، غیریکسان و مخصوص همین موضوع باشند. عدد، آمار و رویداد خبری تازه نساز.''')

class APIError(Exception):
    def __init__(self, code, reason, retry_after=None):
        self.code, self.reason, self.retry_after = code, reason, retry_after
        super().__init__(f'HTTP {code or "network"}: {reason}')

def api_json(url, key, payload=None, timeout=TIMEOUT, retries=0):
    headers={'Accept':'application/json', 'User-Agent':'Acolad-AI-Lab-V3/1.0',
             'Authorization':'Bearer '+key}
    data=None
    if payload is not None:
        headers['Content-Type']='application/json'
        data=json.dumps(payload,ensure_ascii=False).encode('utf8')
    req=urllib.request.Request(url,data=data,headers=headers,method='POST' if data is not None else 'GET')
    for attempt in range(retries+1):
        try:
            with urllib.request.urlopen(req,timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            reasons={400:'unsupported request',401:'invalid key',403:'access denied',404:'model inaccessible',
                     408:'provider timeout',429:'free tier rate limit or capacity',
                     500:'server error',502:'upstream error',503:'provider overloaded',504:'provider timeout'}
            if exc.code in (408,500,502,503,504) and attempt<retries:
                time.sleep(min(6,2*(attempt+1)))
                continue
            raise APIError(exc.code,reasons.get(exc.code,'provider error'),exc.headers.get('Retry-After')) from None
        except (TimeoutError,urllib.error.URLError):
            if attempt<retries:
                time.sleep(2)
                continue
            raise APIError(None,'network timeout or unreachable') from None
        except (ValueError,UnicodeError):
            raise APIError(None,'invalid provider JSON') from None
    raise APIError(None,'request not completed')

def zero_price(value):
    try: return float(value)==0
    except (TypeError, ValueError): return False

def eligible_models(catalog):
    valid={}
    for model in catalog.get('data',[]):
        if not isinstance(model,dict):continue
        mid=str(model.get('id',''))
        pricing=model.get('pricing') or {}
        outs=(model.get('architecture') or {}).get('output_modalities') or ['text']
        if (mid.endswith(':free') and 'text' in outs and zero_price(pricing.get('prompt'))
                and zero_price(pricing.get('completion'))):
            # exclude non-chat modalities and tools.
            if not any(x in mid.lower() for x in ('/embed','/rerank','/moderation','/safety','/audio','/tts','/transcri')):
                valid[mid]=model
    return valid

def choose_models(available,override=''):
    warnings=[]
    if override.strip():
        choices=list(dict.fromkeys(x.strip() for x in override.replace(',',';').split(';') if x.strip()))
        permitted=[m for m in choices if m in available]
        warnings=[f'Model unavailable or not verified free: {m}' for m in choices if m not in available]
        return permitted[:MAX_MODELS],warnings
    # Prefer editorially diverse families; model presence is checked live, not presumed.
    families=('qwen/','nvidia/','google/gemma-','meta-llama/','deepseek/','mistralai/','cohere/')
    choices=[]
    for family in families:
        candidates=sorted((m for m in available if m.startswith(family)),key=lambda x: ('code' in x.lower(), 'preview' in x.lower(), x))
        if candidates: choices.append(candidates[0])
        if len(choices)>=MAX_MODELS:break
    for m in sorted(available):
        if len(choices)>=MAX_MODELS:break
        if m not in choices:choices.append(m)
    return choices,warnings

def parse_json_text(text):
    t=text.strip()
    if t.startswith('```'):
        t=re.sub(r'^```(?:json)?\s*','',t,flags=re.I)
        t=re.sub(r'\s*```$','',t)
    return json.loads(t)

def words(text):
    return re.findall(r'[\w\u0600-\u06ff]+',text,flags=re.UNICODE)

def validate_result(obj,case,finish='stop'):
    """Static heuristic gate, NOT factual verification. Returns status + review signals."""
    reasons=[]; warnings=[]
    if not isinstance(obj,dict):return 'invalid_output',['expected JSON object'],warnings
    stories=obj.get('stories')
    telegram=obj.get('telegram')
    if not isinstance(stories,list) or len(stories)!=5:reasons.append('exactly five stories required');stories=[]
    if not isinstance(telegram,dict):reasons.append('telegram section missing');telegram={}
    titles=[]; blobs=[]
    for i,s in enumerate(stories):
        if not isinstance(s,dict):reasons.append(f'story {i+1}: invalid');continue
        title=s.get('title');body=s.get('body')
        if not isinstance(title,str) or len(title.strip())<6:reasons.append(f'story {i+1}: title missing')
        else:titles.append(title.strip())
        if not isinstance(body,str):reasons.append(f'story {i+1}: body missing');continue
        n=len(words(body))
        if not 20<=n<=55:reasons.append(f'story {i+1}: word count {n} out of range')
        blobs.append(body)
    if len(titles)==5 and len(set(titles))!=5:reasons.append('repeated story titles')
    tg_title=telegram.get('title');tg_body=telegram.get('body')
    if not isinstance(tg_title,str) or len(tg_title.strip())<8:reasons.append('telegram title missing')
    if not isinstance(tg_body,str):reasons.append('telegram body missing')
    else:
        n=len(words(tg_body))
        if not 120<=n<=230:reasons.append(f'telegram word count {n} out of range')
        blobs.append(tg_body)
    for field in ('evidence_boundary','hypothetical_example','testable_action'):
        value=obj.get(field)
        if not isinstance(value,str) or len(value.strip())<25:reasons.append(field+' missing or too short')
        else:blobs.append(value)
    example=obj.get('hypothetical_example','')
    if isinstance(example,str) and 'فرضی' not in example:reasons.append('hypothetical example not explicitly marked')
    if str(finish).lower() in ('length','max_tokens'):reasons.append('token limit truncation')
    combined=' '.join(blobs)
    count_fa=len(PERSIAN.findall(combined));count_en=len(ENGLISH.findall(combined))
    if count_fa<150 or count_fa/max(1,count_fa+count_en)<.80:reasons.append('insufficient Persian')
    if STRANGE_MIX.search(combined):reasons.append('mixed-script typo detected')
    if any(term in combined for term in BAD_HYPE):reasons.append('unqualified certainty or guarantee')
    # Facts supplied contain no numbers. Schema labels/story numbers excluded by checking only bodies.
    if DIGITS.search(combined):warnings.append('numeric claim or example requires manual evidence check')
    if any(t in combined for t in ('طبق گزارش','تحقیقات نشان می‌دهد','بر اساس آمار','مطالعه نشان')):
        warnings.append('possible unsourced attribution; human check required')
    if any(t in combined for t in ('دیروز','امروز اعلام','اخیراً اعلام','دولت تصویب')):
        warnings.append('potentially invented news/time assertion; human check required')
    if len(set(words(combined)))<45:reasons.append('overly repetitive wording')
    # A passing gate never implies publication permission.
    return ('needs_human_review' if not reasons else 'invalid_output'),reasons,warnings

def completion(key,model,case):
    data={'model':model,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':prompt(case)}],
          'temperature':0.45,'max_tokens':3400,'stream':False}
    r=api_json(CHAT_API,key,payload=data,timeout=TIMEOUT,retries=1)
    choices=r.get('choices') or []
    if not choices:raise APIError(None,'no choices returned')
    c=choices[0]; message=c.get('message') or {}
    body=message.get('content')
    if isinstance(body,list):body='\n'.join(p.get('text','') for p in body if isinstance(p,dict))
    if not isinstance(body,str) or not body.strip():
        raise APIError(None,'no visible answer; may have exhausted reasoning budget')
    return body, c.get('finish_reason','unknown')

def local_fixture(case):
    # Synthetic fixture solely to test the pipeline, NOT real model output.
    topic=case['title']
    make=lambda i: ('این یک سناریوی کاملاً فرضی درباره '+topic+' است. ' +
      'برای تصمیم بهتر باید هزینه واقعی هر سفارش، زمان تیم و رضایت مشتری را جداگانه بسنجیم. ' +
      'بدون اندازه‌گیری، نتیجه‌گیری درباره سود یا موفقیت منطقی نیست. ' +
      'یک آزمایش کوچک پیشنهاد می‌شود و نتیجه آن باید ثبت شود.')
    story=[{'title':topic+' — بخش '+str(i),'body':make(i)} for i in range(1,6)]
    telegram=('این روایت فرضی است و به هیچ کسب‌وکار واقعی اشاره نمی‌کند. '+
      'هر تغییری در مسیر فروش آنلاین لازم است با اندازه‌گیری شروع شود. '+
      'می‌توان هزینه هر سفارش، زمان پاسخ‌گویی و رضایت مشتری را جداگانه ثبت کرد. '+
      'سپس یک تغییر کوچک را برای دوره کوتاهی آزمایش کرد و نتیجه را با دوره قبلی سنجید. ')*3
    return {'stories':story,'telegram':{'title':'چطور '+topic+' را بسنجیم؟','body':telegram},
            'evidence_boundary':'شواهد این تمرین فقط یک سناریوی فرضی است و خبر واقعی یا داده پژوهشی ندارد.',
            'hypothetical_example':'این مثال کاملاً فرضی است و درباره هیچ فروشگاه واقعی نیست.',
            'testable_action':'یک شاخص قابل سنجش مشخص کنید، دوره پایه را ثبت کنید و تغییر کوچک را ارزیابی کنید.'}

def run_candidate(model,cases,key,offline):
    outcomes={}
    for idx,case in enumerate(cases):
        t=time.monotonic()
        try:
            if offline:obj=local_fixture(case);finish='stop';raw=json.dumps(obj,ensure_ascii=False)
            else:raw,finish=completion(key,model,case);obj=parse_json_text(raw)
            status,reasons,warnings=validate_result(obj,case,finish)
            outcomes[case['id']]={'status':status,'reasons':reasons,'warnings':warnings,'payload':obj,
                                  'seconds':round(time.monotonic()-t,2),'finish_reason':finish}
        except APIError as exc:
            outcomes[case['id']]={'status':'api_error','error':str(exc),'http_status':exc.code,
                                  'seconds':round(time.monotonic()-t,2)}
            if exc.code in (401,403,429):
                for later in cases[idx+1:]:outcomes[later['id']]={'status':'skipped','error':'access/quota blocked'}
                break
        except (json.JSONDecodeError,ValueError,TypeError) as exc:
            outcomes[case['id']]={'status':'invalid_output','reasons':['unparseable JSON: '+type(exc).__name__],
                                  'seconds':round(time.monotonic()-t,2)}
        except Exception as exc:
            outcomes[case['id']]={'status':'error','error':'unexpected '+type(exc).__name__,'seconds':round(time.monotonic()-t,2)}
    return outcomes

def report(cases,models,results,warnings,offline):
    OUTPUT.mkdir(exist_ok=True)
    # Randomization is deterministic; no model name on blind review text.
    shuffled=models[:];random.Random(20261101).shuffle(shuffled)
    aliases={chr(65+i):name for i,name in enumerate(shuffled)}
    reverse={v:k for k,v in aliases.items()}
    rows=[];html_parts=[]
    status_counts={}
    passing=0
    for model in models:
        if all(results[model].get(c['id'],{}).get('status')=='needs_human_review' for c in cases):passing+=1
    for case in cases:
        html_parts.append(f'<h2>{html.escape(case["title"])}</h2><p>{html.escape(case["facts"])}</p>')
        for model in shuffled:
            item=results[model].get(case['id'],{'status':'skipped'});label=reverse[model]
            status=item.get('status','skipped');status_counts[status]=status_counts.get(status,0)+1
            body=json.dumps(item.get('payload'),ensure_ascii=False,indent=2) if item.get('payload') is not None else item.get('error','No output')
            flags='؛ '.join(item.get('reasons',[])+item.get('warnings',[]))
            html_parts.append('<section><h3>نمونه '+label+'</h3><p><b>وضعیت: '+html.escape(status)+'</b></p><pre>'+html.escape(body)+'</pre><p>'+html.escape(flags)+'</p></section>')
            rows.append({'case_id':case['id'],'sample':label,'status':status,
             'accuracy_and_evidence_30':'','business_insight_25':'','human_persian_20':'','story_sequence_15':'','cta_10':'',
             'total_100':'','human_approved_yes_no':'','review_notes':''})
    valid=passing>=2 and not offline
    overall=('READY_FOR_BLIND_HUMAN_COMPARISON' if valid else ('OFFLINE_TEST_ONLY' if offline else 'INSUFFICIENT_VALID_RESPONSES'))
    summary={'lab_version':3,'mode':'offline' if offline else 'compare','run_status':overall,'cases':len(cases),
        'models_attempted':len(models),'models_with_all_cases_structurally_valid':passing,
        'status_counts':status_counts,'model_selection_warnings':warnings,'publication':'NEVER',
        'quality_gate_note':'needs_human_review is NOT verified or publishable; human verification is always required',
        'generated_utc':datetime.now(timezone.utc).isoformat()}
    (OUTPUT/'status.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    (OUTPUT/'answer_key.json').write_text(json.dumps(aliases,ensure_ascii=False,indent=2),encoding='utf8')
    # Keep raw model answers in artifact only; no provider key or HTTP response body logged.
    (OUTPUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    css='body{direction:rtl;background:#f5f2eb;color:#152334;font:16px/1.9 Tahoma,Arial,sans-serif}main{max-width:980px;margin:auto;padding:20px}section{background:white;padding:20px;margin:16px 0;border-radius:14px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.8 Tahoma}h1{color:#304bb9}'
    page='<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><style>'+css+'</style></head><body><main><h1>آزمایشگاه مستقل کیفیت آکولاد V3</h1><p>فقط تست، هیچ ارسال یا صف‌گذاری انجام نشده است. وضعیت «نیازمند داوری انسانی» مجوز انتشار نیست.</p><p>وضعیت: '+html.escape(overall)+'</p>'+''.join(html_parts)+'</main></body></html>'
    (OUTPUT/'blind_review.html').write_text(page,encoding='utf8')
    with (OUTPUT/'scoring_sheet.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (OUTPUT/'README_RESULTS_FA.md').write_text('''# گزارش آزمایشگاه AI آکولاد V3\n\nاین آزمایش هیچ چیزی منتشر یا زمان‌بندی نمی‌کند.\n\n۱. ابتدا blind_review.html را بخوانید و بر اساس scoring_sheet.csv امتیاز دهید.\n۲. فقط بعد از امتیازدهی، answer_key.json را باز کنید.\n۳. وضعیت needs_human_review صرفاً عبور از کنترل شکل و چند خطای آشکار است؛ بررسی منابع و صحت محتوا هنوز انسانی است.\n۴. OFFLINE_TEST_ONLY یعنی هیچ مدل واقعی فراخوانی نشده و خروجی‌ها ساختگی و فقط برای تست نرم‌افزارند.\n۵. محدودیت 429/403 به‌خودی‌خود نشانه کیفیت بد مدل نیست.\n''',encoding='utf8')
    return summary

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['offline','compare'],default='offline')
    p.add_argument('--cases',type=int,choices=[1,2,3],default=1)
    a=p.parse_args(argv)
    cases=CASES[:a.cases]
    warnings=[]
    if a.mode=='offline':
        models=['offline:synthetic-A','offline:synthetic-B']
        results={m:run_candidate(m,cases,'',True) for m in models}
    else:
        key=os.getenv('OPENROUTER_API_KEY','').strip()
        if not key:
            print('ERROR: OPENROUTER_API_KEY is missing (GitHub Secrets).',file=sys.stderr)
            return 2
        try:
            catalog=api_json(MODEL_CATALOG,key,timeout=20,retries=1)
            eligible=eligible_models(catalog)
            models,warnings=choose_models(eligible,os.getenv('ACOLAD_V3_MODELS',''))
        except APIError as exc:
            models=[];warnings.append('Catalog access failed: '+str(exc))
        if len(models)<2:
            print('Too few verified zero-price chat models; refuse paid fallback.',flush=True)
            results={}
        else:
            # Keep small to conserve free-tier quotas; max 2 parallel calls.
            results={}
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                jobs={pool.submit(run_candidate,m,cases,key,False):m for m in models}
                for job in concurrent.futures.as_completed(jobs):results[jobs[job]]=job.result()
    if not models:
        models=['none:unavailable'];results={models[0]:{c['id']:{'status':'skipped','error':'No eligible free model'} for c in cases}}
    s=report(cases,models,results,warnings,a.mode=='offline')
    print('LAB V3:',s['run_status'],'|',s['models_with_all_cases_structurally_valid'],'/',s['models_attempted'],'eligible model outputs')
    print('NO PUBLICATION, NO BUFFER/NOVINHUB/TELEGRAM CONNECTIONS.')
    # Expected lack of second free provider is a report status, not a code crash.
    return 0

if __name__=='__main__':raise SystemExit(main())
