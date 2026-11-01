#!/usr/bin/env python3
"""Acolad editorial A/B lab v2: no publish, no third-party packages.
Runs a reproducible blind comparison of available free text/chat models.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
from dataclasses import dataclass
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

OUTPUT = Path('ai_benchmark_results')
OPENROUTER_MODELS = 'https://openrouter.ai/api/v1/models'
OPENROUTER_CHAT = 'https://openrouter.ai/api/v1/chat/completions'
GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta/models/'
REQUEST_TIMEOUT = 90

CASES = [
    {'id':'pricing', 'title':'فروشگاه آنلاین و هزینه ارسال', 'facts':'سناریوی فرضی: فروشگاه اینترنتی کوچکی با افزایش هزینه ارسال و بسته‌بندی روبه‌رو شده، ولی هنوز حاشیه سود هر سفارش را اندازه نگرفته است. هیچ درصد یا خبر روزی تأیید نشده است.', 'audience':'صاحب فروشگاه اینترنتی ایرانی'},
    {'id':'ai_tools','title':'هوش مصنوعی برای یک تیم کوچک', 'facts':'سناریوی فرضی: تیم سه‌نفره کسب‌وکار برای محتوا، فروش و پشتیبانی چند ابزار AI خریده، اما هنوز زمان صرفه‌جویی‌شده یا بازگشت سرمایه را اندازه نگرفته است. هیچ داده عددی تأییدشده‌ای وجود ندارد.', 'audience':'صاحب کسب‌وکار خرد ایرانی'},
    {'id':'online','title':'ورود یک فروشگاه محلی به بازار آنلاین','facts':'سناریوی فرضی: فروشگاه محلی با بودجه محدود می‌خواهد آنلاین شود؛ بین وب‌سایت، اینستاگرام و فروش در مارکت‌پلیس مردد است. هیچ راهکار یکسانی برای همه فروشگاه‌ها وجود ندارد.', 'audience':'صاحب فروشگاه سنتی در ایران'},
]
SYSTEM = '''شما سردبیر حرفه‌ای تحریریه آکولاد هستید. فقط به فارسی روان، طبیعی و محاوره‌ایِ حرفه‌ای بنویسید؛ فارسی اجباری است و پاسخ انگلیسی مردود است.
مخاطب: مدیران و صاحبان کسب‌وکارهای ایرانی که آنلاین شده‌اند یا می‌خواهند آنلاین شوند.
شخصیت: استاد دانشگاه شوخ‌طبعی که سال‌ها پای اجرای واقعی کسب‌وکار بوده؛ دقیق، باهوش و گاهی دارای طنز ظریف، اما بدون تقلید از شخص حقیقی.
هیچ آمار، خبر واقعی، درصد، هزینه، مطالعه یا نقل‌قولی که در داده ورودی نیست جعل نکنید. تمام مثال‌ها فرضی‌اند.
اصطلاحات کلیشه‌ای «برداشت کاربردی آکولاد»، «مثلاً برای یک کسب‌وکار» و «اصل ماجرا» را به عنوان تیتر ننویسید.
تیترها مخصوص موضوع باشند. شوخی بی‌جا یا تبلیغ بیش‌ازحد ممنوع. نام برند دقیقاً «آکولاد» باشد.'''


def prompt_for(case):
    return f'''موضوع: {case['title']}\nمخاطب: {case['audience']}\nشواهد موجود: {case['facts']}\n\nسه بخش بده (تماماً فارسی):
«استوری‌ها»: ۵ استوری پشت‌سرهم، هرکدام تیتر اختصاصی کوتاه و ۲۰ تا ۴۰ کلمه؛ ۱) هوک ۲) مسئله ۳) تحلیل غیر بدیهی ۴) یک مثال فرضی یا راهکار ۵) CTA دوستانه برای دایرکت آکولاد.
«تلگرام»: ۱۴۰ تا ۲۰۰ کلمه با تیتر مخصوص موضوع، ۲ تا ۴ ایموجی درست، ۳ تا ۶ عبارت کلیدی **بولد**، پاراگراف‌های کوتاه، تحلیل، مثال و یک CTA طبیعی. تیترهای ثابت و فرمولی نده.
«مرز واقعیت و فرض»: یک جمله تفکیک شواهد و مثال فرضی.\nاگر یک واقعیت در ورودی وجود ندارد، آن را نساز. فقط محتوای خواسته‌شده را بنویس.'''


@dataclass
class RequestFailure(Exception):
    status: int | None
    reason: str
    retry_after: str = ''

    def __str__(self):
        code = f'HTTP {self.status}: ' if self.status else ''
        return (code + self.reason)[:350]


def request_json(url, *, payload=None, key=None, headers=None, timeout=REQUEST_TIMEOUT, retries=0):
    h = {'Accept':'application/json','User-Agent':'Acolad-AI-Quality-Lab/2.0'}
    if payload is not None: h['Content-Type']='application/json'
    if key: h['Authorization']='Bearer '+key
    h.update(headers or {})
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=h, method='POST' if payload is not None else 'GET')
    for attempt in range(retries+1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            # Error message: intentionally do not store provider body, prompt, query URL or secrets.
            reason = {
                400:'bad request or unsupported model option',
                401:'API key rejected',403:'API key / model access denied',
                404:'model missing or inaccessible for this key',
                408:'provider timeout',429:'free quota or provider capacity exceeded',
                500:'provider internal error',502:'provider unavailable',503:'provider overloaded'
            }.get(exc.code, 'provider returned an error')
            if exc.code in (502,503) and attempt < retries:
                time.sleep(2)
                continue
            raise RequestFailure(exc.code, reason, str(exc.headers.get('Retry-After',''))) from None
        except (TimeoutError, urllib.error.URLError) as exc:
            raise RequestFailure(None, 'network timeout/unreachable ('+type(exc).__name__+')') from None
    raise RequestFailure(None,'provider unavailable')


BAD_IDS = ('embed', 'rerank', 'guard', 'safety', 'moderation', 'audio', 'speech', 'transcribe', 'tts', 'code', 'coding', 'vl-', 'vision', 'image', 'ocr', 'flint', 'router/')
PREFERRED = ('qwen/', 'google/gemma-', 'thinkingmachines/', 'meta-llama/', 'mistralai/', 'deepseek/', 'nvidia/nemotron-3.5-lightning', 'nvidia/nemotron-3-ultra', 'dots-studio/')


def free_text_models(token, custom=''):
    models = request_json(OPENROUTER_MODELS,key=token,timeout=20).get('data',[])
    available = {m['id']:m for m in models if isinstance(m,dict) and str(m.get('id','')).endswith(':free')}
    def suitable(model_id):
        l = model_id.lower()
        if any(x in l for x in BAD_IDS): return False
        model = available[model_id]
        arch = model.get('architecture') or {}
        out = arch.get('output_modalities') or ['text']
        return 'text' in out
    allowed = [mid for mid in available if suitable(mid)]
    if custom.strip():
        ids=[x.strip() for x in custom.replace(',', ';').split(';') if x.strip()]
        invalid = [x for x in ids if x not in allowed]
        if invalid: raise ValueError('Not suitable/available free chat IDs: '+', '.join(invalid))
        return list(dict.fromkeys(ids))[:2]
    selected=[]
    for prefix in PREFERRED:
        family=sorted((m for m in allowed if m.startswith(prefix)),
                      key=lambda m: (0 if ('preview' not in m) else 1, len(m), m))
        if family:
            selected.append(family[0])
        if len(selected)==2: break
    for m in sorted(allowed):
        if len(selected)==2:break
        if m not in selected:selected.append(m)
    return selected


def openrouter_completion(token, model, case):
    response=request_json(OPENROUTER_CHAT,key=token,retries=0,timeout=REQUEST_TIMEOUT,
        headers={'X-Title':'Acolad Editorial Quality Lab'}, payload={
        'model':model,
        'messages':[{'role':'system','content':SYSTEM}, {'role':'user','content':prompt_for(case)}],
        'temperature':0.65,'max_tokens':5200,'stream':False,
    })
    choices=response.get('choices') or [{}]
    c=choices[0]
    m=c.get('message') or {}
    content=m.get('content')
    if isinstance(content,list): content='\n'.join(x.get('text','') for x in content if isinstance(x,dict))
    if not isinstance(content,str) or not content.strip():
        meta=response.get('usage') or {}
        raise RequestFailure(None,'empty visible text; finish_reason='+str(c.get('finish_reason'))+'; completion_tokens='+str(meta.get('completion_tokens')))
    return content.strip(), {'finish_reason':c.get('finish_reason'), 'provider_model':response.get('model',model)}


def gemini_completion(key, model, case):
    payload={
       'systemInstruction':{'parts':[{'text':SYSTEM}]},
       'contents':[{'role':'user','parts':[{'text':prompt_for(case)}]}],
       'generationConfig':{'temperature':0.65,'maxOutputTokens':5500},
    }
    if model in ('gemini-3.8-flash','gemini-3.6-flash'):
        payload['generationConfig']['thinkingConfig']={'thinkingLevel':'low'}
    response=request_json(GEMINI_BASE+model+':generateContent',payload=payload,timeout=REQUEST_TIMEOUT,
        headers={'x-goog-api-key':key},retries=0)
    c=(response.get('candidates') or [{}])[0]
    parts=(c.get('content') or {}).get('parts') or []
    content='\n'.join(p.get('text','') for p in parts if isinstance(p,dict) and p.get('text'))
    if not content.strip():
        raise RequestFailure(None,'Gemini no visible text; finishReason='+str(c.get('finishReason','unknown')))
    return content.strip(),{'finish_reason':c.get('finishReason'), 'provider_model':model}


PERSIAN_RE=re.compile('[\u0600-\u06ff]')


def quality_status(text,meta):
    visible=len(text.strip())
    persian=len(PERSIAN_RE.findall(text))
    ratio=persian/max(1,len(re.findall(r'[A-Za-z\u0600-\u06ff]',text)))
    reasons=[]
    if visible<480:reasons.append('too short/incomplete')
    if ratio<0.48:reasons.append('mostly non-Persian')
    if 'استوری' not in text or 'تلگرام' not in text:reasons.append('requested sections missing')
    finish=str(meta.get('finish_reason','')).lower()
    if finish in ('length','max_tokens'):reasons.append('truncated at token limit')
    return ('scoreable' if not reasons else 'invalid_output',reasons)


def evaluate_model(candidate,cases,router_key,gemini_key,self_test=False):
    typ,model=candidate.split(':',1)
    rows={}
    for case in cases:
        start=time.monotonic()
        try:
            if self_test:
                txt=('استوری‌ها\n' + ('در فروش آنلاین، باید اول مسئلهٔ مشتری را بفهمیم. '*16) + '\nتلگرام\n' + ('برای تصمیم‌گیری کسب‌وکار، هزینه و رضایت مشتری را با هم بسنجیم. '*22) + '\nمرز واقعیت و فرض: همه مثال‌ها فرضی‌اند.')
                meta={'finish_reason':'stop','provider_model':model}
            elif typ=='gemini': txt,meta=gemini_completion(gemini_key,model,case)
            else: txt,meta=openrouter_completion(router_key,model,case)
            status,flags=quality_status(txt,meta)
            rows[case['id']]={'status':status,'text':txt,'seconds':round(time.monotonic()-start,2),'flags':flags,'meta':meta}
        except RequestFailure as e:
            rows[case['id']]={'status':'api_error','error':str(e),'http_status':e.status,'seconds':round(time.monotonic()-start,2)}
            if e.status in (401,403,429):
                # Stop further expensive requests to a model already unavailable/limited.
                for later in cases[cases.index(case)+1:]:
                    rows[later['id']]={'status':'skipped','error':'Skipped after '+str(e),'seconds':0}
                break
        except Exception as e:
            rows[case['id']]={'status':'api_error','error':'Unexpected: '+type(e).__name__,'seconds':round(time.monotonic()-start,2)}
    return rows


def produce_report(cases,candidates,results,selection_warnings):
    OUTPUT.mkdir(parents=True,exist_ok=True)
    rng=random.Random(20261101)
    shuffled=candidates[:];rng.shuffle(shuffled)
    mapping={chr(65+i):candidate for i,candidate in enumerate(shuffled)}
    label_of={v:k for k,v in mapping.items()}
    records={c['id']:{} for c in cases}
    status_counts={}
    for case in cases:
        for candidate in candidates:
            label=label_of[candidate]
            entry=results.get(candidate,{}).get(case['id'],{'status':'skipped','error':'Not run'})
            records[case['id']][label]=entry
            status_counts[entry['status']]=status_counts.get(entry['status'],0)+1
    scoreable=sum(entry['status']=='scoreable' for case in records.values() for entry in case.values())
    scoreable_models=sum(all(records[c['id']][label]['status']=='scoreable' for c in cases) for label in mapping)
    overview={'run_status':('VALID_COMPARISON' if scoreable_models>=2 else 'INSUFFICIENT_VALID_RESPONSES'),
              'cases':len(cases),'candidates':len(candidates),'scoreable_texts':scoreable,
              'scoreable_models_all_cases':scoreable_models,'status_counts':status_counts,
              'selection_warnings':selection_warnings}
    (OUTPUT/'answer_key.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf8')
    (OUTPUT/'provider_status.json').write_text(json.dumps(overview,ensure_ascii=False,indent=2),encoding='utf8')
    (OUTPUT/'raw_outputs.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')

    css='''<style>body{direction:rtl;margin:0;background:#f5f2eb;color:#152334;font:16px/1.95 Tahoma,Arial,sans-serif}main{max-width:920px;margin:auto;padding:25px}h1{color:#244bc3}section{background:white;padding:22px;border-radius:16px;margin:15px 0;box-shadow:0 2px 12px #0000000b}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/2.05 Tahoma,Arial,sans-serif}small{color:#667}strong.bad{color:#a02328}strong.ok{color:#176f4a}</style>'''
    parts=['<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'+css+'</head><body><main>',
           '<h1>آزمایش کور کیفیت نویسندگی آکولاد</h1><p>این گزارش هیچ چیزی منتشر نکرده است؛ مدل‌ها در فایل answer_key.json مشخص‌اند.</p>']
    if overview['run_status']!='VALID_COMPARISON':
        parts.append('<section><strong class="bad">مقایسه معتبر شکل نگرفته است.</strong> فقط خروجی‌هایی که با برچسب قابل‌امتیاز دیده می‌شوند، قابل داوری هستند.</section>')
    rows=[]
    for case in cases:
        parts.append('<h2>'+html.escape(case['title'])+'</h2><p>'+html.escape(case['facts'])+'</p>')
        for label in sorted(mapping):
            entry=records[case['id']][label]; good=entry.get('status')=='scoreable'
            status='قابل امتیازدهی' if good else 'غیرقابل امتیازدهی — '+entry.get('status','')
            body=entry.get('text') or entry.get('error','No response')
            if entry.get('flags'):body+='\n\nدلیل عدم پذیرش: '+', '.join(entry['flags'])
            parts.append('<section><h3>نمونه '+label+'</h3><strong class="'+('ok' if good else 'bad')+'">'+html.escape(status)+'</strong><pre>'+html.escape(body)+'</pre></section>')
            rows.append({'case_id':case['id'],'candidate':label,'status':entry.get('status'),
                         'factual_fidelity_25':'','business_insight_20':'','iran_relevance_20':'',
                         'human_voice_15':'','story_hook_10':'','cta_10':'','total_100':'','notes':''})
    parts.append('</main></body></html>')
    (OUTPUT/'blind_review.html').write_text('\n'.join(parts),encoding='utf8')
    with (OUTPUT/'scoring_sheet.csv').open('w',encoding='utf-8-sig',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    summary=['# گزارش آزمایش آکولاد V2','','**هیچ چیزی منتشر نشده و هیچ تغییری در جریان‌های انتشار ایجاد نشده است.**',
             '',f"وضعیت نهایی: **{overview['run_status']}**",
             f"مدل‌های دارای پاسخ قابل‌امتیاز برای تمام سناریوها: **{scoreable_models} از {len(candidates)}**",
             '', 'فایل `blind_review.html` را باز کنید. تنها متن‌هایی با وضعیت «قابل امتیازدهی» را داوری کنید.',
             'تا زمانی که حداقل دو مدل برای تمام سناریوها پاسخ معتبر نداده‌اند، برنده‌ای اعلام نکنید.',
             '', '## مدل‌های واقعی', 'برای جلوگیری از سوگیری، پس از خواندن متن‌ها فایل `answer_key.json` را ببینید.',
             '', '## علت‌های احتمالی',
             '- 404 برای Gemini 2.5 ممکن است به محدودیت دسترسی نسخه قدیمی مربوط باشد؛ V2 از مدل جدید استفاده می‌کند.',
             '- 429 سقف/ازدحام سرویس است و کیفیت مدل را نشان نمی‌دهد.',
             '- پاسخ خالی، انگلیسی یا ناقص در رتبه‌بندی وارد نمی‌شود.',
             '', '## توضیحات انتخاب مدل']+[f'- {w}' for w in selection_warnings]
    (OUTPUT/'README_RESULTS.md').write_text('\n'.join(summary),encoding='utf8')
    return overview


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cases',type=int,choices=(1,2,3),default=1)
    ap.add_argument('--self-test',action='store_true')
    args=ap.parse_args()
    router=os.getenv('OPENROUTER_API_KEY','').strip()
    gemini=os.getenv('GEMINI_API_KEY','').strip()
    preferred=os.getenv('ACOLAD_GEMINI_MODEL','').strip()
    # Avoid a legacy 2.5 override left over from older workflows.
    gemini_model=preferred if preferred and not preferred.startswith('gemini-2.5-') else 'gemini-3.8-flash'
    custom=os.getenv('ACOLAD_OPENROUTER_MODELS','')
    candidates=[]; warnings=[]
    if gemini or args.self_test:candidates.append('gemini:'+gemini_model)
    if router or args.self_test:
        if args.self_test:
            selections=['qwen/test-text:free','google/test-instruct:free']
        else:
            try: selections=free_text_models(router,custom)
            except Exception as exc:
                selections=[];warnings.append('OpenRouter catalog failed: '+str(exc))
        candidates.extend('openrouter:'+s for s in selections)
    if not candidates:
        OUTPUT.mkdir(parents=True,exist_ok=True)
        (OUTPUT/'README_RESULTS.md').write_text('No provider available. Configure GEMINI_API_KEY or OPENROUTER_API_KEY.',encoding='utf8')
        print('ERROR: missing provider credentials or free models',file=sys.stderr)
        return 2
    print('Selected candidate count:',len(candidates),'; scenarios:',args.cases,flush=True)
    print('No publication requests will be sent.',flush=True)
    cases=CASES[:args.cases]
    results={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(candidates),3)) as pool:
        jobs={pool.submit(evaluate_model,c,cases,router,gemini,args.self_test):c for c in candidates}
        for future in concurrent.futures.as_completed(jobs):
            c=jobs[future]
            try:results[c]=future.result()
            except Exception as exc:
                results[c]={case['id']:{'status':'api_error','error':'Worker: '+type(exc).__name__} for case in cases}
            for case in cases:
                entry=results[c].get(case['id'],{})
                print('Candidate',c.split(':',1)[0], '|',c.split(':',1)[1], '|',case['id'],'|',entry.get('status'), '|',entry.get('seconds',0),'s',flush=True)
    report=produce_report(cases,candidates,results,warnings)
    print('STATUS:',report['run_status'],'| scoreable full candidates:',report['scoreable_models_all_cases'],flush=True)
    print('REPORT:',OUTPUT,flush=True)
    # Do not show GitHub green for a failed comparison; artifact always uploaded.
    return 0 if report['run_status']=='VALID_COMPARISON' else 1

if __name__=='__main__':sys.exit(main())
