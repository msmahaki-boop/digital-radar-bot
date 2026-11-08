#!/usr/bin/env python3
"""Acolad V5: source-aware, human Persian nine-beat stories.
No GitHub or social mutations; only guarded copy construction and validation.
A slide's full prose is NEVER also pasted whole beneath its own first photo.
"""
from __future__ import annotations
import json, os, re
from pathlib import Path

BEATS=("hook","old_path","dialogue","turn","new_expectation","science_knot",
       "practical_actions","emotional_cost","payoff")
BAD_CLICHES=("در دنیای امروز","شایان ذکر است","در نهایت","بیایید بررسی کنیم",
             "در عصر دیجیتال","نقش بسزایی","همان‌طور که می‌دانید")
EXEMPLAR_NOTE = (
    "نمونه لحنِ کارفرما: محمد دنبال مسیر مرجوعی در صفحه سفارش می‌گرده، "
    "به جزئیات سفارش و بعد قوانین سایت می‌ره، وقتی می‌فهمه مهلتش تمام شده "
    "احساس می‌کنه حق دانستن ازش گرفته شده؛ نتیجه انسانی: «دکمه رو می‌شه "
    "برداشت؛ توضیح رو نه.» این یک نمونه آموزشیِ ساختگیه، نه رخداد "
    "ثبت‌شدهٔ پژوهش و نه متنی برای کپی کردن."
)

SYSTEM_INSTRUCTION = """تو سردبیر ارشد آکولاد و یک داستان‌نویس فارسی محاوره‌ایِ باسواد هستی.
برای یک مطالعه یا رویداد دارای منبع دست اول، دقیقاً ۹ اسلاید پشت‌سرهم می‌نویسی.
لحن نمونه: ریزجزئیات قابل دیدن؛ یک آدم و یک مشکل معلوم؛ فعل‌های کوتاه طبیعی؛
دیالوگ درونی ایرانی؛ گره، تغییر، کشف، یک نتیجه انسانی و چهار اقدام قابل‌سنجش.
متن نباید انشای شرکتی یا فهرست توصیه‌های کلی باشد. «در دنیای امروز»،
«در نهایت»، «بیایید بررسی کنیم»، «نقش بسزایی» و شعارهای کلی ممنوع.
اصل پژوهش، تفسیر تو، توصیهٔ آزمایشی و شخصیت/دیالوگِ خیالی را از هم جدا کن.
هر رقم، نتیجه پژوهشی، نام نویسنده، تاریخ یا اثر قطعی باید در منبع ورودی
قابل دفاع باشد. مثالِ ایرانیِ ساختگی را صریحاً «فرض کن...» معرفی کن؛
هرگز آن را شرکت‌کننده واقعی پژوهش جا نزن.
الگوی هر اسلاید: text شامل ۳۵ تا ۶۵ واژه فارسی انسانی که برای پیام‌رسان
خواندنی است، overlay شامل ۶ تا ۱۵ واژهٔ خلاصهٔ نمایشی همان اسلاید،
دارای حداقل یک عبارت **پررنگ** جهت هایلایت رنگی.
۹ beat به ترتیب: hook, old_path, dialogue, turn, new_expectation,
science_knot, practical_actions, emotional_cost, payoff.
قلاب اسلاید اول را با 💭 و پاراگراف روایت را با 📌 شروع کن؛
در لیست اقدامات اسلاید ۷ دقیقاً چهار خط + بنویس.
اسلاید ۲ به ۳ با «...» و اسلاید ۶ به ۷ با «یعنی...» وصل شود؛
اسلاید ۹ گره را ببندد و جمله طلایی تألیفیِ بدون نسبت‌دادن جعلی به شاعر داشته باشد.
آخر داستان باید پرسش صمیمی و غیرتزئینی داشته باشد.
روایت تصویری ۹ فریم با scene_idهای ۱,۱,۱,۲,۲,۲,۳,۳,۳
و visual_actionهای new_scene,add_text,add_text در هر صحنه؛
فقط صحنه‌های ۱ و ۲ تصویرسازی مفهومی اصیل با GPT Image، صحنه ۳ متن‌محور.
رنگی‌شدن زیر عبارت‌های **مهم** و ثابت‌ماندن پیکسل‌های متن قبلی در
اسلاید بعد ضروری است. overlay متنِ خلاصه است؛ جمله تازه و ادعای جدید نده.
اگر در سند اصلی نمودار یا اسکرین‌شات قابل استفاده نیست، جعل نمودار ممنوع.
فقط JSON با ساختار title, fictional_example, source_url, source_date,
slides:[{n,beat,text,overlay,scene_id,visual_action,visual_idea,
source_ids,claim_type}] بده. source_ids فقط از شناسه‌های واقعی ورودی باشد."""

def normalize_visible(text):
    return re.sub(r"\*\*|__|\u200e|\u200f","",str(text)).strip()

def word_count(text):
    return len(re.findall(r"\S+",normalize_visible(text)))

def validate(story:dict, sources:list[dict], *, visual_max_words:int=15):
    """Fail closed; never auto-fix unsupported claims by changing facts."""
    issues=[]
    if not isinstance(story,dict):return ["INVALID_JSON_STORY"]
    slides=story.get("slides")
    if not isinstance(slides,list) or len(slides)!=9:return ["EXPECTED_EXACTLY_NINE_SLIDES"]
    source_ids={str(s.get("id")) for s in sources if isinstance(s,dict) and s.get("id")}
    urls={str(s.get("url")) for s in sources if isinstance(s,dict) and s.get("url")}
    if story.get("source_url") not in urls:issues.append("SOURCE_URL_NOT_IN_VERIFIED_INPUT")
    if not story.get("fictional_example"):issues.append("FICTIONAL_EXAMPLE_NOT_LABELED")
    all_text=[]
    for i,s in enumerate(slides):
        if not isinstance(s,dict):issues.append(f"SLIDE_{i+1}_MALFORMED");continue
        expected_scene=1+i//3
        expected_action="new_scene" if i%3==0 else "add_text"
        if (s.get("n")!=i+1 or s.get("beat")!=BEATS[i] or
            s.get("scene_id")!=expected_scene or
            s.get("visual_action")!=expected_action):
            issues.append(f"SLIDE_{i+1}_CHRONOLOGY_OR_FREEZE")
        full=str(s.get("text") or "").strip()
        overlay=str(s.get("overlay") or "").strip()
        if not 35<=word_count(full)<=65:issues.append(f"SLIDE_{i+1}_FULL_WORDS")
        if not 6<=word_count(overlay)<=visual_max_words:
            issues.append(f"SLIDE_{i+1}_OVERLAY_WORDS")
        if overlay.count("**")<2 or overlay.count("**")%2:
            issues.append(f"SLIDE_{i+1}_HIGHLIGHT_MISSING")
        for bad in BAD_CLICHES:
            if bad in full or bad in overlay:
                issues.append(f"SLIDE_{i+1}_ROBOT_CLICHE")
        refs=s.get("source_ids") or []
        if not isinstance(refs,list) or any(str(x) not in source_ids for x in refs):
            issues.append(f"SLIDE_{i+1}_INVALID_SOURCE_REFERENCE")
        if s.get("claim_type") not in ("fact","interpretation","hypothetical","testable"):
            issues.append(f"SLIDE_{i+1}_CLAIM_TYPE")
        if s.get("claim_type")=="fact" and not refs:
            issues.append(f"SLIDE_{i+1}_FACT_WITHOUT_SOURCE")
        all_text.append(full)
    if "فرض کن" not in all_text[0] and "تصور کن" not in all_text[0]:
        issues.append("HYPOTHETICAL_CHARACTER_PRESENTED_AS_REAL")
    if not all_text[1].rstrip().endswith("..."):
        issues.append("SLIDE_2_MISSING_SUSPENSE_BRIDGE")
    if "یعنی..." not in all_text[5][-28:]:
        issues.append("SLIDE_6_MISSING_ACTION_BRIDGE")
    if len(re.findall(r"(?:^|\n)\s*\+\s+",all_text[6]))!=4:
        issues.append("SLIDE_7_REQUIRES_FOUR_ACTIONS")
    if not any(x in all_text[-1] for x in ("مخلص کلام","دکمه","حرف آخر","اصل قصه")):
        issues.append("SLIDE_9_NO_SPECIFIC_PAYOFF")
    if len(set(normalize_visible(x) for x in all_text))!=9:
        issues.append("REPEATED_TEXT")
    if not any("بایمرد" in x or "Baymard" in x for x in all_text):
        # For this exemplar, credible research must be identified, not fabricated.
        if any("baymard.com" in u for u in urls):
            issues.append("RESEARCH_NOT_IDENTIFIED_IN_STORY")
    return list(dict.fromkeys(issues))

def visual_story(story):
    """Give existing IRANSans/highlight/frozen-pixel engine only SHORT overlays."""
    out=dict(story)
    out["slides"]=[{
       "n":s["n"],"text":s["overlay"],"scene_id":s["scene_id"],
       "visual_action":s["visual_action"],"visual_idea":s.get("visual_idea",""),
       "source_ids":s.get("source_ids",[]),"beat":s["beat"]
    } for s in story["slides"]]
    return out

def thread_parts(story,network):
    """No duplicated complete caption and no robotic 'part 1/3' prefaces."""
    if network not in ("telegram","bale"):raise ValueError("UNKNOWN_NETWORK")
    from acolad_v4_daily_autopublish import footer_for
    slides=story["slides"]
    bounds=((0,2),(2,5),(5,9))
    parts=[]
    for i,(left,right) in enumerate(bounds):
        text="\n\n".join(normalize_visible(s["text"]) for s in slides[left:right])
        if i==2:text+="\n\n"+footer_for(network)
        if i==0 and len(text)>985:
            raise RuntimeError("PHOTO_CAPTION_EXCEEDS_TELEGRAM_1024_LIMIT")
        if len(text)>3900:raise RuntimeError("NATIVE_MESSAGE_LONGER_THAN_LIMIT")
        if not text.strip():raise RuntimeError("EMPTY_STORY_PART")
        parts.append(text)
    if any(parts[i] in parts[j] for i in range(3) for j in range(i+1,3)):
        raise RuntimeError("DUPLICATE_NARRATIVE_PARTS")
    return parts

def build_from_gapgpt(sources:list[dict], *, key:str|None=None):
    """One source-locked candidate; model scores are not publication receipts."""
    import acolad_luna_research_preview as research
    key=key or os.getenv("GAPGPT_API_KEY","").strip()
    if not key:raise RuntimeError("GAPGPT_KEY_MISSING")
    if not sources or any(not s.get("url") or not s.get("excerpt") for s in sources):
        raise RuntimeError("PRIMARY_EVIDENCE_NOT_PREPARED")
    brief={"sources":[{k:s.get(k) for k in
        ("id","url","title","date","excerpt","verified_claims")} for s in sources],
        "human_voice_exemplar":EXEMPLAR_NOTE,
        "avoid_duplication":"Do not copy the user exemplar or earlier Nov8 site-performance story.",
        "narrative_brief":"Write a NEW grounded nine-part story about a concrete human dilemma."}
    usage={"requests_sent":0,"cost_estimated_usd":0.0,"budget_usd":0.22,"stages":[]}
    draft=research.api_call(key,SYSTEM_INSTRUCTION,
       json.dumps(brief,ensure_ascii=False),7900,usage)
    issues=validate(draft,sources)
    if issues:raise RuntimeError("V5_HUMAN_STORY_VETO:"+",".join(issues[:9]))
    return draft,usage
