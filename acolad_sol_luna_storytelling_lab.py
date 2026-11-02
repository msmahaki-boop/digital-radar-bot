#!/usr/bin/env python3
"""Independent, opt-in, paid GapGPT editorial writing comparison for Acolad.

Two models only; one identical evidence-grounded prompt; one request per model.
No Telegram, Buffer, Cloudinary, Instagram, NovinHub, GitHub writes, or publication.
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

ROOT = Path('acolad_sol_luna_storytelling_results')
ENDPOINT = 'https://api.gapgpt.app/v1/chat/completions'
MODELS = ('gpt-6.1-sol', 'gpt-6-luna')
MODEL_RATES = {'gpt-6.1-sol': (2.0, 10.0), 'gpt-6-luna': (0.10, 0.50)}
USD_TO_TOMAN = 250_000
MAX_OUTPUT_TOKENS = 3500
PLANNED_INPUT_UPPER = 4500  # estimate, not an enforceable tokenizer or billing ceiling
CONFIRM_APPROVAL = 'I_APPROVE_SOL_LUNA_PAID_TEST'
CONFIRM_KEY = 'I_CONFIRMED_LIMITED_GIFT_KEY'
DEFAULT_PLANNING_BUDGET = 0.06
SOURCE_1 = 'https://baymard.com/lists/cart-abandonment-rate'
SOURCE_2 = 'https://baymard.com/blog/ecommerce-ux-audit'

# Hand-verified public source facts, provided to BOTH models verbatim.
# Do not silently substitute a made-up university, sample size, or Iran statistic.
FACTS = '''\
منابع راستی‌آزمایی‌شده برای این آزمایش (فقط این موارد را واقعی روایت کن):
۱) Baymard Institute، گزارش «50 Cart Abandonment Rate Statistics 2026»،
آدرس: https://baymard.com/lists/cart-abandonment-rate
این منبع در بررسی دلایل رهاکردن خرید آنلاین در آمریکا (جدا از کسانی که صرفاً در حال گشتن و مقایسه بودند)
می‌گوید ۴۰٪ به بالا بودن هزینه‌های جانبی، از جمله ارسال، مالیات و کارمزد، اشاره کرده‌اند.
این عدد «درصد کسب‌وکارهای ایرانی»، «درصد کل سفارش‌های رهاشده ایران» یا «اثر قطعی یک راهکار» نیست.
۲) Baymard Institute، مقاله «Ecommerce UX Audit: How to Find What's Hurting Your Conversion» در ۲۰۲۶،
آدرس: https://baymard.com/blog/ecommerce-ux-audit
در این مقاله سبد خرید Best Buy نمونه‌ای از نمایش شفاف هزینه کل سفارش (هزینه‌های جانبی و ارسال) پیش از پرداخت معرفی شده است.
این فقط مثال واقعی طراحی رابط است؛ منبع نگفته Best Buy با این کار حتماً فروشش چند درصد بالا رفته.
هیچ مطالعه دانشگاهی روی ۳۸۰ کسب‌وکار و هیچ ادعای ۹۸٪ در شواهد این آزمایش وجود ندارد.
این آمار درباره آمریکا است و تعمیم مستقیم به ایران معتبر نیست.
'''

SYSTEM = '''\
تو نویسنده و سردبیر خلاق آکولاد هستی. آکولاد شریک رشد دیجیتال کسب‌وکارهاست: سایت، سئو، تجربه مشتری، بازاریابی، CRM و اتوماسیون.
فارسی باید کاملاً زنده، طبیعی، محاوره‌ایِ حرفه‌ای و خوش‌آهنگ باشه؛ مثل متخصصی که پای صحبت صاحب کسب‌وکار نشسته.
از فعل‌های گفتاری مثل «می‌تونه»، «می‌خوای»، «یه»، «اگه»، «ولی» در جای درست استفاده کن. متنِ مقاله‌ای و اداری ننویس.
روایت را با کشمکش، غافلگیری، جزئیات ملموس، مثال واقعی و یک مثال فرضی پیش ببر؛ فقط آمار چاشنی داستان باشد.
از نسبت دادن داده ساختگی به دانشگاه، شرکت، ایران یا Baymard اکیداً پرهیز کن.
دانسته‌های عمومی خودت منبع مجاز برای افزودن عدد، نمونه پژوهشی، خبر یا نقل‌قول تازه نیستند.
واقعیت منبع، تفسیر، مثال فرضی و پیشنهاد قابل‌آزمایش را از هم جدا نگه دار.
جملات «طبق تحقیقات ثابت شده»، «حتماً»، «تضمینی»، «۹۸ درصد کسب‌وکارها»، «تحلیل غیربدیهی»، «برداشت کاربردی آکولاد»، «اصل ماجرا» و شعارهای کلیشه‌ای ممنوع‌اند.
لحن جسور و تکان‌دهنده مجاز است؛ آمار دروغ یا اغراق گمراه‌کننده مجاز نیست.
'''

TASK = '''\
موضوع محتوای آزمایش: «هزینه پنهان در مرحله پرداخت؛ مشتریِ آماده خرید چطور منصرف می‌شه؟»
مخاطب: صاحب فروشگاه آنلاین ایرانی. هدف: هم سرگرم و کنجکاو شود، هم نکته به‌دردبخور یاد بگیرد.

پنج استوری متوالی بساز؛ این‌ها پنج پرده از یک داستان‌اند، نه پنج پستِ مستقل.
- استوری ۱: با یک صحنه ضربه‌زننده و کنجکاوی‌ساز آغاز کن؛ انگار مشتری دمِ پرداخت غیب شده. مستقیم سراغ ۴۰٪ نرو و پایان داستان را لو نده.
- استوری ۲: پرده از مسئله بردار؛ پژوهش واقعی Baymard را به زبان ساده وارد کن. نسبت ۴۰٪ را درست توضیح بده: بررسی دلایل رهاکردن خرید در آمریکا، نه آمار ایران.
- استوری ۳: نمونه واقعی Best Buy از مقاله Baymard را با یک تصویر ذهنی ملموس توصیف کن؛ ادعای افزایش فروش برای Best Buy نساز.
- استوری ۴: فروشگاه آنلاین فرضی ایرانی را زنده کن. برای مثال خرید یک پک هدیه، هزینه ارسال ناگهانی و واکنش مشتری. اگر مبلغ ساختی حتماً همان‌جا «مثال فرضی» بنویس.
- استوری ۵: یک اقدام کوچک، مشخص و قابل سنجش برای فروشگاه پیشنهاد بده؛ اندازه‌گیری نرخ تکمیل خرید و سود هر سفارش، نه وعده نتیجه قطعی. CTA طبیعی: «اگه خواستی این نقطه رو تو فروشگاهت پیدا کنیم، به آکولاد پیام بده» یا مشابه خلاقانه‌تر.

برای هر استوری فقط برچسب «استوری ۱:» تا «استوری ۵:» و سپس متن اصلی بیاور.
هیچ عنوان/تیتر جداگانه‌ای برای هر اسلاید لازم نیست. هر استوری ۱۸ تا ۴۸ کلمه، به‌جز استوری اول که ۱۲ تا ۳۰ کلمه باشد.
هر استوری باید خواننده را به استوری بعد بکشاند؛ از نکته‌چینیِ فهرست‌وار پرهیز کن.

بعد بخش «تلگرام:» را بنویس: ۱۴۰ تا ۲۰۰ کلمه فارسی محاوره‌ای، با شروعی تازه و متفاوت با استوری اول.
از دو منبع داده‌شده دقیق استفاده کن، تفاوت واقعیت و فرض را روشن کن، و با یک مثال ایرانی و توصیه سنجش‌پذیر تمام کن.
تیتر تلگرام اجباری نیست؛ چند پاراگراف کوتاه، صفر تا دو ایموجی، بدون هشتگ و فروش‌زدگی.
اگر درباره سود حرف می‌زنی بهای خرید/تأمین کالا و هزینه‌های جانبی را هم در نظر بگیر؛ صرف نرخ تبدیل کافی نیست.

در انتها «منابع:» و فقط همین دو URL داده‌شده را ذکر کن. منبع جدید، درصد یا مطالعه دانشگاهی تازه نساز.
متن را فارسی محاوره‌ایِ واقعی بنویس. هیچ توضیحی درباره فرایند تولید متن یا پرامپت نده.
'''

PROMPT = FACTS + '\n' + TASK


class ProviderError(Exception):
    def __init__(self, status: int | None, category: str):
        self.status = status
        self.category = category
        super().__init__(f'HTTP {status if status is not None else "network"}: {category}')


def estimated_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_usd, output_usd = MODEL_RATES[model]
    return round((input_tokens * input_usd + output_tokens * output_usd) / 1_000_000, 9)


def planned_max(model: str) -> float:
    return estimated_cost(model, PLANNED_INPUT_UPPER, MAX_OUTPUT_TOKENS)


def build_payload(model: str) -> dict:
    payload = {
        'model': model,
        'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': PROMPT}],
        'max_tokens': MAX_OUTPUT_TOKENS,
        'stream': False,
    }
    if model == 'gpt-6.1-sol':
        # Sol previously returned visible text with low reasoning at GapGPT.
        payload['reasoning_effort'] = 'low'
    elif model == 'gpt-6-luna':
        # Previous successful Luna test used none and no temperature.
        payload['reasoning_effort'] = 'none'
    return payload


def query_model(key: str, model: str) -> dict:
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(build_payload(model), ensure_ascii=False).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                 'Accept': 'application/json', 'User-Agent': 'Acolad-Sol-Luna-Story-Lab/1.0'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=140) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ProviderError(None, 'provider response too large')
        data = json.loads(raw.decode('utf-8'))
        if not isinstance(data, dict):
            raise ProviderError(None, 'unexpected provider response')
        return data
    except urllib.error.HTTPError as e:
        mapping = {400:'bad model parameters', 401:'key invalid', 402:'insufficient API credit',
                   403:'model forbidden', 404:'model not found', 408:'provider timeout',
                   429:'rate limited', 500:'provider error', 502:'upstream error',
                   503:'provider overloaded', 504:'upstream timeout'}
        # Do not persist HTTP bodies, headers, prompts from provider, or credentials.
        raise ProviderError(e.code, mapping.get(e.code, 'provider HTTP error')) from None
    except (TimeoutError, urllib.error.URLError, OSError):
        raise ProviderError(None, 'network failure or timeout') from None
    except (UnicodeError, json.JSONDecodeError):
        raise ProviderError(None, 'non-JSON provider response') from None


def extract_response(reply: dict) -> tuple[str, int | None, int | None, str, str]:
    choices = reply.get('choices') or []
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderError(None, 'empty choices')
    first = choices[0]
    message = first.get('message') or {}
    if not isinstance(message, dict):
        message = {}
    content = message.get('content', '')
    if isinstance(content, list):
        content = '\n'.join(p.get('text','') for p in content if isinstance(p,dict) and isinstance(p.get('text'),str))
    if not isinstance(content, str):
        content = ''
    usage = reply.get('usage') or {}
    if not isinstance(usage, dict):
        usage = {}
    i = usage.get('prompt_tokens')
    o = usage.get('completion_tokens')
    i = i if type(i) is int and i >= 0 else None
    o = o if type(o) is int and o >= 0 else None
    return (content.strip(), i, o, str(first.get('finish_reason','unknown')),
            str(reply.get('model',''))[:120])


STORY_RE = re.compile(r'^\s*استوری\s*([1-5۱-۵])\s*[:：\-–]?\s*', re.M)


def review_flags(text: str, finish: str) -> list[str]:
    flags = []
    if not text:
        return ['متن قابل مشاهده دریافت نشد']
    nums = STORY_RE.findall(text)
    if len(nums) != 5:
        flags.append(f'برچسب پنج استوری کامل نیست؛ تعداد: {len(nums)}')
    if 'تلگرام' not in text:
        flags.append('بخش تلگرام دیده نمی‌شود')
    if 'بایمارد' not in text and 'Baymard' not in text:
        flags.append('نام منبع پژوهشی در متن دیده نمی‌شود')
    if 'آمریکا' not in text and 'آمریکایی' not in text:
        flags.append('محدودیت جغرافیایی پژوهش ذکر نشده')
    if not ('۴۰' in text or '40' in text):
        flags.append('عدد مستند پژوهش، ۴۰٪، در متن یافت نشد')
    if 'فرضی' not in text:
        flags.append('مثال فرضی صریحاً مشخص نشده')
    if ('۹۸٪' in text or '۹۸ درصد' in text or '98%' in text):
        flags.append('هشدار جدی: ادعای ۹۸٪ بدون منبع در پاسخ دیده شد')
    if any(x in text for x in ('تضمینی', 'تضمین می‌شود', 'صددرصد نتیجه')):
        flags.append('احتمال وعده قطعی یا تضمینی')
    if SOURCE_1 not in text or SOURCE_2 not in text:
        flags.append('فهرست دو URL پژوهشی کامل نیست')
    if finish.lower() in ('length', 'max_tokens'):
        flags.append('هشدار جدی: پاسخ به سقف توکن خورده و احتمالاً ناقص است')
    return flags


def save_report(rows: list[dict], budget: float, error_message: str = '') -> dict:
    ROOT.mkdir(parents=True, exist_ok=True)
    shuffled = list(rows)
    random.Random(20261102).shuffle(shuffled)
    mapping = {chr(65 + n): x['model'] for n, x in enumerate(shuffled)}
    aliases = {v:k for k,v in mapping.items()}
    usable = sum(x.get('status') == 'VISIBLE_NEEDS_HUMAN_REVIEW' for x in rows)
    # Do not show a clean comparison if evidence labels, links, or structure are missing.
    # Static checks are conservative signals, never human fact verification.
    complete = sum(x.get('status') == 'VISIBLE_NEEDS_HUMAN_REVIEW'
                   and not x.get('flags', []) for x in rows)
    result = {
        'version': 'sol-luna-story-v1', 'run_status': ('READY_FOR_BLIND_HUMAN_REVIEW' if complete == 2 else
                     'PARTIAL_RESULTS_NEEDS_REVIEW' if usable else 'NO_USABLE_TEXT'),
        'models_requested': len(rows), 'visible_outputs': usable,
        'complete_outputs_by_heuristic': complete,
        'requests_attempted': sum(1 for x in rows if x.get('api_requested')),
        'budget_planning_usd': budget, 'budget_planning_toman': round(budget*USD_TO_TOMAN),
        'publication': 'NEVER', 'generated_utc': datetime.now(timezone.utc).isoformat(),
        'source_urls': [SOURCE_1, SOURCE_2],
        'important': 'هزینه‌ها برآورد هستند؛ مبلغ واقعی فقط در پنل گپ‌جی‌پی‌تی مشخص می‌شود. عبور از کنترل ساختاری به معنی تأیید حقیقت یا مجوز انتشار نیست.',
    }
    if error_message:
        result['error'] = error_message
    (ROOT/'status.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT/'answer_key.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding='utf-8')
    costs=[]
    grade=[]
    pages=['<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
           '<title>مقایسه کور Sol و Luna — آکولاد</title>',
           '<style>body{font:16px/2 Tahoma,Arial,sans-serif;color:#132237;max-width:920px;margin:0 auto;padding:22px;background:#f5f2eb}section{background:#fff;padding:24px;margin:20px 0;border-radius:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:16px/2.2 Tahoma,Arial,sans-serif}h1{color:#7b2cbf}small{color:#5e6c7a}</style>',
           '<h1>مقایسه کور نویسندگی روایی آکولاد</h1>',
           '<p>نام مدل عمداً پنهان است؛ ابتدا متن‌ها را بخوان و امتیاز بده، سپس answer_key.json را باز کن.</p>',
           '<p><strong>موضوع:</strong> مشتری تا مرحله پرداخت می‌رسد اما ممکن است به‌خاطر هزینه‌های جانبی از خرید منصرف شود. پژوهش معتبر مربوط به آمریکا است، نه ایران.</p>']
    for row in shuffled:
        label=aliases[row['model']]
        txt=row.get('text','')
        flags=row.get('flags',[])
        pages.extend([f'<section><h2>نمونه {label}</h2><small>{html.escape(row.get("status","unknown"))}</small>',
                      '<pre>'+html.escape(txt or 'متن قابل مشاهده دریافت نشد.')+'</pre>',
                      '<p><b>نکات بررسی دستی:</b> '+html.escape('؛ '.join(flags) if flags else 'خروجی نیازمند بررسی حقیقت و لحن توسط انسان است.')+'</p>',
                      '</section>'])
        costs.append({
            'sample':label,'model':row['model'],'status':row.get('status',''),
            'prompt_tokens':row.get('input_tokens',''), 'completion_tokens':row.get('output_tokens',''),
            'estimated_usd':row.get('estimate_usd',''),
            'estimated_toman':row.get('estimate_toman',''),
            'planned_upper_usd':planned_max(row['model']),
            'planned_upper_toman':round(planned_max(row['model'])*USD_TO_TOMAN),
            'response_seconds':row.get('seconds',''),
            'finish_reason':row.get('finish_reason',''),
            'reported_model':row.get('model_returned',''),
        })
        grade.append({
            'sample':label,'status':row.get('status',''),
            'factual_precision_30':'','specific_examples_25':'','colloquial_persian_20':'',
            'story_hook_continuity_15':'','natural_cta_10':'',
            'total_100':'','human_approved_yes_no':'','editorial_notes':'',
        })
    pages.append('<p>منبع مستند مقایسه: <a href="'+SOURCE_1+'">Baymard / cart abandonment</a> و <a href="'+SOURCE_2+'">Baymard / UX audit</a>.</p>')
    pages.append('</html>')
    (ROOT/'blind_review.html').write_text('\n'.join(pages),encoding='utf-8')

    def write_csv(path: str, values: list[dict]):
        with (ROOT/path).open('w',encoding='utf-8-sig',newline='') as fp:
            wr=csv.DictWriter(fp,fieldnames=list(values[0]));wr.writeheader();wr.writerows(values)
    write_csv('costs_in_toman.csv',costs)
    write_csv('scoring_sheet.csv',grade)
    (ROOT/'raw_results.json').write_text(json.dumps({x['model']:{k:v for k,v in x.items() if k!='model'}
                                                   for x in rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT/'README_RESULTS_FA.md').write_text('''# نتیجه آزمایش واقعی Sol و Luna

هیچ پست یا استوری‌ای منتشر یا صف‌گذاری نشده است.

۱. ابتدا blind_review.html را بخوان و بدون دیدن اسم مدل به متن‌ها امتیاز بده.
۲. برای امتیازدهی، scoring_sheet.csv را پر کن؛ accuracy=30، examples=25، natural tone=20، narrative=15، CTA=10.
۳. سپس answer_key.json را باز کن. costs_in_toman.csv هزینه محاسبه‌شده بر پایه توکن را نشان می‌دهد، نه مبلغ قطعی کیف پول.
۴. منبع Baymard فقط درباره آمریکا است. ۴۰٪ هرگز به معنای ۴۰٪ از کسب‌وکارهای ایرانی نیست.
۵. هر ادعای نامستند، ادعای پژوهش ساختگی یا وعده قطعی باعث رد سردبیری است؛ حتی اگر متن خوش‌خوان باشد.
''',encoding='utf-8')
    return result


def main(argv=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['compare'],default='compare')
    parser.add_argument('--budget-usd',type=float,default=DEFAULT_PLANNING_BUDGET)
    parser.add_argument('--approval',default='')
    parser.add_argument('--gift-confirmation',default='')
    args=parser.parse_args(argv)
    if args.approval != CONFIRM_APPROVAL or args.gift_confirmation != CONFIRM_KEY:
        print('BLOCKED: explicit paid-request approval and limited gift key confirmation required',file=sys.stderr)
        return 2
    if not 0.05 <= args.budget_usd <= 0.08:
        print('BLOCKED: planning budget must be between $0.05 and $0.08',file=sys.stderr)
        return 2
    key=os.environ.get('GAPGPT_API_KEY','').strip()
    if not key:
        print('BLOCKED: GAPGPT_API_KEY not configured',file=sys.stderr)
        return 2

    rows=[]
    reserved_usd=0.0
    for model in MODELS:
        pre_quote=planned_max(model)
        row={'model':model,'api_requested':False,'planned_reserve_usd':pre_quote}
        if reserved_usd+pre_quote>args.budget_usd+1e-9:
            row['status']='BUDGET_SKIP'
            rows.append(row)
            continue
        reserved_usd+=pre_quote  # conservative reservation; keep even on error/timeout
        row['api_requested']=True
        start=time.monotonic()
        try:
            data=query_model(key,model)
            text, input_tok, output_tok, finish, reported_model=extract_response(data)
            row.update(text=text[:50000],input_tokens=input_tok,output_tokens=output_tok,
                       finish_reason=finish,model_returned=reported_model,
                       seconds=round(time.monotonic()-start,2))
            row['flags']=review_flags(text,finish)
            row['status']='VISIBLE_NEEDS_HUMAN_REVIEW' if text else 'EMPTY_RESPONSE'
            if input_tok is not None and output_tok is not None:
                price=estimated_cost(model,input_tok,output_tok)
                row['estimate_usd']=price
                row['estimate_toman']=round(price*USD_TO_TOMAN)
                # Keep reservation if actual estimate is lower, safer for later calls.
                reserved_usd+=max(0.0,price-pre_quote)
        except ProviderError as err:
            row.update(status='API_ERROR',error_category=str(err),seconds=round(time.monotonic()-start,2),
                       flags=['درخواست خطا داد؛ صورتحساب واقعی باید در پنل بررسی شود'])
        rows.append(row)
        print(f'MODEL {model}: {row["status"]}; {row.get("seconds",0)} sec',flush=True)
    report=save_report(rows,args.budget_usd)
    print(f'RUN_STATUS={report["run_status"]}; SENT={report["requests_attempted"]}; PUBLICATION=NEVER',flush=True)
    return 0 if report['run_status']=='READY_FOR_BLIND_HUMAN_REVIEW' else 1

if __name__=='__main__':
    raise SystemExit(main())
