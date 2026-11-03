#!/usr/bin/env python3
"""Daily Acolad editorial intake and approval-gated cinematic visual preview.

Daily scheduled mode = FREE source scouting only.
Manual full-preview = existing Luna researched storytelling + optionally ONE paid
Gemini illustration + local original pen-sketch backups, ALWAYS NEVER PUBLISH.
No telegram/instagram/NovinHub write APIs. Every artifact is review-only.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import acolad_luna_research_preview as news

OUT=Path("acolad_daily_editorial_output")
RESEARCH_OUT=Path("acolad_luna_research_preview")
PAID_APPROVAL="APPROVED_DAILY_EDITORIAL_PREVIEW_20000_TOMAN"
IRAN=ZoneInfo("Asia/Tehran")
TOPICS={
 "iran_economy":("اقتصاد و معیشت ایران",("ایران","تورم","معیشت","خرید","هزینه","مالیات")),
 "iran_platforms":("پلتفرم‌های ایرانی",("دیجی","اسنپ","ترب","دیوار","تپسی","باسلام")),
 "ai":("هوش مصنوعی و مدل‌های کسب‌وکار",("هوش مصنوعی","AI","agent","artificial intelligence")),
 "tech":("فناوری کاربردی و جستجو",("Google","گوگل","سئو","search","mobile","app")),
 "marketing":("بازاریابی، برند و خرید",("برند","خریدار","مشتری","marketing","brand","consumer")),
 "social":("رسانه‌های اجتماعی و محتوا",("instagram","tiktok","telegram","content","social","اینستاگرام")),
 "small_business_growth":("تجربه مشتری و رشد کسب‌وکار",("فروشگاه","checkout","shop","تجربه","website","payment")),
}
HOOKS=(
 ("morning","فکر کن صبح از خواب پاشدی و با یه اتفاق عجیب روبه‌رو شدی…"),
 ("dialogue","یه مشتری درست قبل از خرید یه سؤال ساده می‌پرسه…"),
 ("reversal","قرار بود این کار فروش رو بیشتر کنه؛ ولی نتیجه برعکس از آب دراومد…"),
 ("you","خودتو بذار جای صاحب این کسب‌وکار…"),
 ("experiment","محقق‌ها یه چیز کوچیک رو توی یک آزمایش واقعی عوض کردند…"),
 ("incident","ماجرا از یه تصمیم به ظاهر بی‌ضرر شروع شد…"),
 ("reality","یه خبر تازه به کسب‌وکارها یادآوری کرد که…"),
)
def local_day():
    return dt.datetime.now(IRAN).date()
def selected_style(day):
    return HOOKS[day.toordinal()%len(HOOKS)]
def assigned_focus(day):
    return list(TOPICS)[day.toordinal()%len(TOPICS)]
def source_bucket(source):
    text=(str(source.get("title") or "")+" "+str(source.get("excerpt") or "")[:300]).casefold()
    matches=[]
    for slug,(_,needles) in TOPICS.items():
        if any(x.casefold() in text for x in needles):matches.append(slug)
    return matches or ["other"]
def source_safe(source):
    return {k:source.get(k) for k in (
      "id","title","publisher","date","url","source_type","evidence_depth",
      "doi","rank","excerpt") if k in source}
def write_intake(day=None, output=OUT):
    output.mkdir(parents=True,exist_ok=True)
    date=day or local_day()
    diag=[]
    # All seven themes are represented in categorization; latest live
    # RSS/OpenAlex/Crossref sources are fetched by the existing research engine.
    sources=news.collect_sources("auto",diag)
    groups={key:[] for key in TOPICS}
    for source in sources:
        for tag in source_bucket(source):
            if tag in groups:groups[tag].append(source_safe(source))
    paired=news.suggested_evidence_pairs(sources,limit=8)
    day_focus=assigned_focus(date)
    style,hint=selected_style(date)
    report={
       "status":"FREE_DAILY_EDITORIAL_INTAKE_NOT_STORY",
       "date_tehran":date.isoformat(),"daily_topic_rotation":day_focus,
       "daily_narrative_style":style,"narrative_hook_direction":hint,
       "candidate_count":len(sources),
       "verified_experimental_articles_only_if_abstract_provides_design":True,
       "categories":groups,"proposed_evidence_pairs":paired,
       "diagnostics":diag,"model_calls":0,"estimated_paid_cost_toman":0,
       "drafts":0,"queued":0,"instagram_posts":0,"telegram_posts":0,
       "important":"Sources are candidates, not fact-checked finished stories. Human source verification before any publish."}
    (output/"intake.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    md=[f"# تحریریه روزانه آکولاد — {date.isoformat()}","",
       f"**موضوعِ چرخشیِ امروز:** {TOPICS[day_focus][0]}",
       f"**شروع روایت امروز:** {hint}",
       "**وضعیت:** تحقیق بدون هزینه؛ هنوز داستان، Draft یا انتشار نیست.","",
       "## هفت بخش تحریریه"]
    for slug,(label,_) in TOPICS.items():
        selected=groups[slug]
        md.extend([f"### {label} ({len(selected)} سرنخ)"])
        for item in selected[:3]:
            md.append(f"- {item.get('title','')} | {item.get('publisher','')} | {item.get('date','')} | {item.get('url','')}")
    md.append("## هشدار")
    md.append("عدد، ارتباطِ پژوهش و خبر، و تازگی باید مستقل بررسی شوند؛ تیتر کافی نیست.")
    (output/"DAILY_BRIEF_FA.md").write_text("\n\n".join(md),encoding="utf-8")
    print("FREE_EDITORIAL_INTAKE "+json.dumps({
        "date":report["date_tehran"],"categories":{k:len(v) for k,v in groups.items()},
        "candidate_count":len(sources),"next_hook":style},ensure_ascii=False))
    return report

def narrative_prompts(day):
    style,hook=selected_style(day)
    opening=(
        "\n\nالزام روزانه: زاویه نگاه و فرم شروع را بر اساس «"
        +style+"» طراحی کن؛ نمونه فقط جهت لحن است: «"+hook+"»"
        "\n جمله نمونه را کپی نکن و اگر به خبر واقعی نمی‌خورد از همان الگوی روایی،"
        " نه متن آن، استفاده کن. نام «مهدی» و داستان پرداخت و سبد خرید نمونه قبلی ممنوع؛"
        " هر روز یک موقعیت تازه با یک گره روشن، شاهد معتبر، کشف و تصمیم عملی."
        " شروع مخاطب‌محور یا ماجرایی را جایگزین شخصیت ثابت کن؛"
        " از جمله‌های مبهم، ادعاهای بدون شاهد و تغییر بی‌دلیل صحنه دوری کن."
        "\n تنوع سردبیری: موضوعات اقتصاد و معیشت ایران، برندها، مطالعات آزمایشی،"
        " فناوری، پلتفرم‌ها، تجربه مشتری، شبکه‌های اجتماعی، بازاریابی و رشد کسب‌وکار."
        " منبع علمی باید به قصه مربوط باشد؛ دو منبع نامرتبط را به زور یکی نکن."
        "\n پایان باید گره را ببندد، نه اینکه فقط بگوید «آکولاد کمک می‌کند»."
        "\n خروجی بصری با جمله‌های کوتاه و هر دو یا سه قاب یک زمینه مفهومی مناسب است."
        "\n برای هر ادعای مشخص source_ids بده؛ ادعای قطعی درباره ایران بدون سند ممنوع."
    )
    return opening

def story_is_distinct(story):
    frames=story.get("slides",[])
    if not isinstance(frames,list) or len(frames)<5:return False
    lead=" ".join(str(x.get("text") or "") for x in frames[:3] if isinstance(x,dict))
    repetitive=("مهدی" in lead or ("سبد خرید" in lead and "روش پرداخت" in lead))
    return not repetitive

def run_preview(day=None,budget_usd=0.018,output=OUT):
    date=day or local_day()
    output.mkdir(parents=True,exist_ok=True)
    style,hook=selected_style(date)
    orig_w,orig_e=news.WRITE_INSTRUCTION,news.EDIT_INSTRUCTION
    orig_select=news.SELECT_INSTRUCTION
    try:
        extra=narrative_prompts(date)
        news.WRITE_INSTRUCTION=orig_w+extra
        news.EDIT_INSTRUCTION=orig_e+extra
        news.SELECT_INSTRUCTION=orig_select+(
           "\nبرای سوژه امروز به‌جای داستان قدیمی پرداخت و سبد خرید، "
           "یک خبر تازه با شاهد واقعی و پرسش تازه انتخاب کن. فقط با منابع مرتبط.")
        code=news.main(["--focus","auto","--approval",news.APPROVAL,
            "--gift-confirmation",news.GIFT,"--budget-usd",str(budget_usd)])
    finally:
        news.WRITE_INSTRUCTION=orig_w
        news.EDIT_INSTRUCTION=orig_e
        news.SELECT_INSTRUCTION=orig_select
    source_status=RESEARCH_OUT/"status.json"
    if not source_status.is_file():
        status={"status":"RESEARCH_OUTPUT_MISSING","exit_code":code}
    else:status=json.loads(source_status.read_text(encoding="utf-8"))
    original=status.get("status","UNKNOWN")
    full=RESEARCH_OUT/"stories.json"
    good=original=="PREVIEW_NEEDS_HUMAN_REVIEW" and full.exists()
    story=(json.loads(full.read_text(encoding="utf-8")) if good else {})
    distinct=story_is_distinct(story) if good else False
    status["dynamic_story_ready_for_design"]=bool(good and distinct)
    status["narrative_style_today"]=style
    status["narrative_hook_direction"]=hook
    status["day_tehran"]=date.isoformat()
    status["repeated_legacy_story_blocked"]=good and not distinct
    status["image_api_calls"]=0
    status["drafts"]=0
    status["scheduled"]=0
    status["published"]=0
    status["editorial_permission"]="REVIEW_ONLY"
    (output/"preview_status.json").write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf-8")
    if good and distinct:
        (output/"current_story.json").write_text(json.dumps(story,ensure_ascii=False,indent=2),encoding="utf-8")
    print("DAILY_DYNAMIC_STORY "+json.dumps({
        "status":original,"ready":good and distinct,"hook":style,
        "model_calls":status.get("gapgpt_requests_sent"),"publication":"NEVER"},ensure_ascii=False))
    return good and distinct

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=("intake","preview"),required=True)
    ap.add_argument("--budget-usd",type=float,default=.018)
    ap.add_argument("--approval",default="")
    args=ap.parse_args()
    if args.mode=="intake":write_intake();return 0
    if args.approval!=PAID_APPROVAL:
        raise SystemExit("Paid dynamic preview requires explicit approval")
    if not .005<=args.budget_usd<=.02:
        raise SystemExit("Luna planning budget may not exceed 5000 toman")
    run_preview(budget_usd=args.budget_usd)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
