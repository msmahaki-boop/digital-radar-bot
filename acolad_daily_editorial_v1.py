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
HISTORY=Path("acolad_daily_editorial_history.json")
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

def repair_all_new_scenes(story:dict)->tuple[dict,bool]:
    """Deterministic editorial continuity fix, not a claim rewrite.

    If model puts every short frame on a new background, regroup consecutive
    beats in pairs without changing a single word, source ID or research fact.
    """
    import copy
    slides=story.get("slides") if isinstance(story,dict) else None
    if not isinstance(slides,list) or len(slides)<2:return story,False
    if any(x.get("visual_action")=="add_text" for x in slides):
        return story,False
    result=copy.deepcopy(story)
    scene=0
    i=0
    while i<len(slides):
        scene+=1
        current=slides[i]
        upcoming=slides[i+1] if i+1<len(slides) else None
        total_words=len(str(current.get("text","")).replace("**","").split())
        partner_words=(len(str(upcoming.get("text","")).replace("**","").split())
                       if upcoming else 0)
        can_pair=(upcoming is not None and total_words+partner_words<=43)
        target=result["slides"][i]
        target["scene_id"]=scene
        target["visual_action"]="new_scene"
        if can_pair:
            next_frame=result["slides"][i+1]
            next_frame["scene_id"]=scene
            next_frame["visual_action"]="add_text"
            next_frame["visual_idea"]=target.get("visual_idea","")
            i+=2
        else:i+=1
    return result,True

def repair_colloquial_passive_without_new_claims(story:dict)->tuple[dict,bool]:
    """Rewrite only the five known formal passive verb phrases, with no new facts.

    Deliberately cannot rewrite numbers, names, evidence references, scene metadata,
    causality or arguments. All independent fact/cinema/voice guards run afterward.
    """
    import copy
    substitutions={
        "دیده شد":"به چشم اومد",
        "دیده شده":"به چشم اومده",
        "مشاهده شد":"به چشم اومد",
        "مشاهده شده":"به چشم اومده",
        "بررسی شد":"بررسیش کردن",
        "بررسی شده":"بررسیش کردن",
        "انجام شد":"انجامش دادن",
        "انجام شده":"انجامش دادن",
        "ارائه شد":"ارائه‌اش کردن",
        "ارائه شده":"ارائه‌اش کردن",
    }
    result=copy.deepcopy(story)
    changed=False
    for slide in result.get("slides",[]):
        before=str(slide.get("text") or "")
        after=re.sub(r"(?:دیده|مشاهده|بررسی|انجام|ارائه)\\s+شد(?:ه)?\\b",
          lambda m:substitutions.get(m.group(0),m.group(0)),before)
        if before!=after:
            slide["text"]=after
            changed=True
    return result,changed


def repair_excess_terminal_dots(story:dict)->tuple[dict,bool]:
    """Remove ONLY redundant final full stops; no facts or figures changed."""
    import copy
    out=copy.deepcopy(story)
    changed=False
    for frame in out.get("slides",[]):
        text=str(frame.get("text",""))
        trimmed=text.rstrip().rstrip(" .۔").strip()
        if trimmed!=text and text.rstrip().endswith((".", "۔")):
            frame["text"]=trimmed
            changed=True
    return out,changed

def repair_unnecessary_publisher_mentions(story:dict)->tuple[dict,bool]:
    """Remove outlet name-dropping without altering real claim or source IDs."""
    import copy
    out=copy.deepcopy(story)
    changed=False
    substitutions=(
        ("گزارش دیجیاتو می‌گه", "در گزارش منتشرشده اومده که"),
        ("گزارش دیجیاتو میگه", "در گزارش منتشرشده اومده که"),
        ("دی‌ام‌بورد می‌گه", "در گزارش منتشرشده اومده که"),
        ("دی ام بورد میگه", "در گزارش منتشرشده اومده که"),
    )
    for slide in out.get("slides",[]):
        text=str(slide.get("text",""))
        for before,after in substitutions:
            if before in text:
                text=text.replace(before,after)
                changed=True
        slide["text"]=text
    return out,changed

def repair_overlong_progressive_scene(story, issues):
    """Split an already-written scene BEFORE its overflowing frame.

    Only visual metadata changes; the words, claims, IDs, evidence, and
    semantic beat order remain byte-for-byte unchanged.
    """
    import copy
    out=copy.deepcopy(story)
    frames=out.get("slides") or []
    indexes=set()
    for issue in issues:
        match=re.fullmatch(
            r"frame (\d+): accumulated scene text \d+ words, change background sooner",
            str(issue))
        if match:
            index=int(match.group(1))-1
            if 0<index<len(frames):
                indexes.add(index)
    if not indexes:
        return story,False
    original_texts=[(f.get("text"),f.get("source_ids"),f.get("beat")) for f in frames]
    scene=0
    prev_id=None
    for i,frame in enumerate(frames):
        prev_original=story["slides"][i].get("scene_id")
        fresh=(i==0 or i in indexes or frame.get("visual_action")=="new_scene"
               or prev_original!=prev_id)
        if fresh:
            scene+=1
            frame["visual_action"]="new_scene"
        else:
            frame["visual_action"]="add_text"
        frame["scene_id"]=scene
        prev_id=prev_original
    if original_texts!=[(f.get("text"),f.get("source_ids"),f.get("beat")) for f in frames]:
        raise ValueError("A visual-only scene repair unexpectedly changed editorial content")
    return out,True


def read_history(day)->list[dict]:
    if not HISTORY.is_file():return []
    try:
        raw=json.loads(HISTORY.read_text(encoding="utf-8"))
        if not isinstance(raw,list):return []
        return [x for x in raw
                if isinstance(x,dict)
                and isinstance(x.get("url"),str)
                and isinstance(x.get("date"),str)
                and 0<=(day-dt.date.fromisoformat(x["date"])).days<=14]
    except (ValueError,TypeError,OverflowError):
        return []

def is_promotional_source(source):
    """Do not turn an advertorial or brand's campaign recap into independent news."""
    url=str(source.get("url","")).casefold()
    title=str(source.get("title","")).casefold()
    excerpt=str(source.get("excerpt","")).casefold()
    if any(x in url for x in ("/promoted/","/advertorial/","/sponsored/")):
        return True
    if any(x in excerpt for x in (
        "متن تبلیغاتی","رپورتاژ آگهی","سلب مسئولیت:","sponsored content",
        "advertorial","paid partnership")):
        return True
    if any(x in title for x in ("رپورتاژ","تبلیغات همسان","آگهی تبلیغاتی")):
        return True
    if ("کمپین" in title or "campaign" in title) and not any(
        term in excerpt for term in ("آزمایش مستقل","independent study",
                                    "مطالعه مستقل","randomized trial")):
        return True
    return False

def repair_missing_conflict_beat(story):
    """Relabel an EXISTING explicit obstacle, without adding facts or words."""
    import copy
    slides=story.get("slides") if isinstance(story,dict) else None
    if not isinstance(slides,list) or any(f.get("beat")=="conflict" for f in slides):
        return story,False
    out=copy.deepcopy(story)
    for frame in out["slides"][1:-1]:
        if frame.get("beat") not in ("discovery","setup","evidence"):
            continue
        t=str(frame.get("text",""))
        if any(x in t for x in ("اما","ولی","مشکل","چرا","مانع","مجبور",
                                 "نمی‌شه","نمی‌کنه","نگران","ترس","هزینه")):
            frame["beat"]="conflict"
            return out,True
    return story,False

def unseen_recent_articles(sources,history,diagnostic):
    banned={x["url"] for x in history}
    # News publication is not an evergreen educational slot: a months-old
    # DOI abstract cannot be silently reused as today's fresh update.
    def current_substantive(x):
        try:
            age=(local_day()-dt.date.fromisoformat(str(x.get("date") or ""))).days
            return (0<=age<=21 and
                    x.get("evidence_depth") in ("full_article","abstract"))
        except (ValueError,TypeError):
            return False
    fresh=[x for x in sources if x.get("url") not in banned and not
           is_promotional_source(x) and current_substantive(x)]
    diagnostic.append("Current substantive <=21d sources available: "+str(len(fresh)))
    diagnostic.append("Self-promotional/advertorial candidate sources excluded: "+
                      str(sum(is_promotional_source(x) for x in sources)))
    candidate_news=[x for x in fresh if x.get("source_type")!="academic_doi"
                    and x.get("evidence_depth")=="full_article"]
    if not candidate_news:
        # An advertorial is never restored merely to avoid an empty output.
        # Research will use authoritative abstracts or report no defensible
        # claim; it must not convert promotion into independent evidence.
        diagnostic.append("No independent full-article story after exclusions; advertorials remain excluded.")
    for i,item in enumerate(fresh,1):
        item["id"]="S"+str(i).zfill(2)
    diagnostic.append("Editorial duplicate URLs excluded: "+str(len(sources)-len(fresh)))
    return fresh

def first_party_expert_sources(raw, diagnostic):
    """Choose only primary research, expert blogs and official documents BEFORE Luna.

    Never promote a secondary news site into a primary source simply because
    the news article itself has full text. Retain genuine DOI abstracts.
    """
    from acolad_editorial_trust_gate import KNOWN_OFFICIAL,load_policy,_host,_matches
    domains={x["domain"] for x in load_policy()["source_policy"]["priority_sources"]}
    domains.update(KNOWN_OFFICIAL)
    vetted=[src for src in raw if isinstance(src,dict) and (
        src.get("source_type")=="academic_doi" or
        any(_matches(_host(src.get("url")),domain) for domain in domains))]
    for i,source in enumerate(vetted,1):
        source["id"]="S"+str(i).zfill(2)
    diagnostic.append("PRIMARY_EXPERT_ONLY_BEFORE_LUNA "+
                      str(len(vetted))+"/"+str(len(raw)))
    return vetted


def run_preview(day=None,budget_usd=0.018,output=OUT):
    date=day or local_day()
    output.mkdir(parents=True,exist_ok=True)
    style,hook=selected_style(date)
    pillar=assigned_focus(date)
    focus={
       "iran_economy":"iran_economy",
       "iran_platforms":"iran_platforms",
       "ai":"tech","tech":"tech",
       "marketing":"marketing","social":"marketing",
       "small_business_growth":"marketing",
    }[pillar]
    orig_w,orig_e=news.WRITE_INSTRUCTION,news.EDIT_INSTRUCTION
    orig_select=news.SELECT_INSTRUCTION
    orig_collect=news.collect_sources
    history=read_history(date)
    def _dedup_sources(focus,diagnostic):
        fresh=unseen_recent_articles(orig_collect(focus,diagnostic),history,diagnostic)
        return first_party_expert_sources(fresh,diagnostic)
    try:
        news.collect_sources=_dedup_sources
        extra=narrative_prompts(date)
        news.WRITE_INSTRUCTION=orig_w+extra
        news.EDIT_INSTRUCTION=orig_e+extra
        news.SELECT_INSTRUCTION=orig_select+(
           "\nمحور اولویت سردبیری امروز: "+TOPICS[pillar][0]+
           ". اگر در این محور منبع دارای بدنه و شاهد معتبر نیست، سراغ محور دیگر برو، نه ادعای ساختگی. "
           "\nبرای سوژه امروز به‌جای داستان قدیمی پرداخت و سبد خرید، "
           "یک خبر تازه با شاهد واقعی و پرسش تازه انتخاب کن. فقط با منابع مرتبط.")
        code=news.main(["--focus",focus,"--approval",news.APPROVAL,
            "--gift-confirmation",news.GIFT,"--budget-usd",str(budget_usd)])
    finally:
        news.WRITE_INSTRUCTION=orig_w
        news.EDIT_INSTRUCTION=orig_e
        news.SELECT_INSTRUCTION=orig_select
        news.collect_sources=orig_collect
    source_status=RESEARCH_OUT/"status.json"
    if not source_status.is_file():
        status={"status":"RESEARCH_OUTPUT_MISSING","exit_code":code}
    else:status=json.loads(source_status.read_text(encoding="utf-8"))
    original=status.get("status","UNKNOWN")
    full=RESEARCH_OUT/"stories.json"
    good=original=="PREVIEW_NEEDS_HUMAN_REVIEW" and full.exists()
    possible_cosmetic_issues=(status.get("issues") or [])
    allowed_cosmetic_problem=(
        original=="QA_BLOCKED_HUMAN_REVIEW_REQUIRED"
        and bool(possible_cosmetic_issues)
        and all(x=="story lacks at least one progressive same-background reveal"
                or x=="cinema: too many final periods"
                or x=="cinema: missing conflict beat"
                or re.fullmatch(r"frame \d+: accumulated scene text \d+ words, change background sooner",x)
                or (x.startswith("cinema: frame ")
                    and x.endswith(" unnecessary publisher mention"))
                for x in possible_cosmetic_issues)
        and full.exists())
    story=(json.loads(full.read_text(encoding="utf-8")) if
           (good or allowed_cosmetic_problem) else {})
    if allowed_cosmetic_problem:
        revised,copy_repaired=repair_unnecessary_publisher_mentions(story)
        if "cinema: too many final periods" in possible_cosmetic_issues:
            revised,period_repaired=repair_excess_terminal_dots(revised)
        else:period_repaired=False
        if "story lacks at least one progressive same-background reveal" in possible_cosmetic_issues:
            revised,scene_repaired=repair_all_new_scenes(revised)
        else:scene_repaired=False
        selected_path=RESEARCH_OUT/"selected_evidence.json"
        chosen=(json.loads(selected_path.read_text(encoding="utf-8"))
                if selected_path.exists() else [])
        fresh_issues=news.story_quality(revised,chosen)+news.cinematic_quality(revised,chosen)
        if not fresh_issues:
            story=revised
            good=True
            status["status"]="PREVIEW_NEEDS_HUMAN_REVIEW"
            status["issues"]=[]
            status["editorial_scene_lock_repaired_without_text_changes"]=scene_repaired
            status["publisher_name_dropped_without_changing_source"]=copy_repaired
            status["trailing_punctuation_repaired"]=period_repaired
            status["prior_machine_status"]=original
            status["story_scenes"]=len({s.get("scene_id") for s in story["slides"]})
            (output/"editorially_repaired_story.json").write_text(
                json.dumps(story,ensure_ascii=False,indent=2),encoding="utf-8")
        else:
            status["cosmetic_repair_issues"]=fresh_issues
    # One remaining purely structural failure need not waste a new API call.
    # Relabel an actual, explicitly written obstacle; never synthesize conflict.
    if not good and story and "cinema: missing conflict beat" in (
            status.get("issues") or []):
        from pathlib import Path
        selected_path=RESEARCH_OUT/"selected_evidence.json"
        selected=(json.loads(selected_path.read_text(encoding="utf-8"))
                  if selected_path.exists() else [])
        tentative,relabeled=repair_missing_conflict_beat(story)
        if relabeled:
            fresh_issues=news.story_quality(tentative,selected)+news.cinematic_quality(tentative,selected)
            if not fresh_issues:
                story=tentative
                good=True
                status["status"]="PREVIEW_NEEDS_HUMAN_REVIEW"
                status["issues"]=[]
                status["beat_label_repair_without_text_changes"]=True
                (output/"editorially_repaired_story.json").write_text(
                    json.dumps(story,ensure_ascii=False,indent=2),encoding="utf-8")
    if not good and story and any(re.fullmatch(
            r"frame \d+: accumulated scene text \d+ words, change background sooner",str(i))
            for i in status.get("issues",[])):
        selected_path=RESEARCH_OUT/"selected_evidence.json"
        chosen=(json.loads(selected_path.read_text(encoding="utf-8"))
                if selected_path.exists() else [])
        candidate,repaired=repair_overlong_progressive_scene(story,status.get("issues",[]))
        if repaired:
            fresh_issues=news.story_quality(candidate,chosen)+news.cinematic_quality(candidate,chosen)
            if not fresh_issues:
                story=candidate
                good=True
                status["status"]="PREVIEW_NEEDS_HUMAN_REVIEW"
                status["issues"]=[]
                status["scene_split_without_text_changes"]=True
                (output/"editorially_repaired_story.json").write_text(
                    json.dumps(story,ensure_ascii=False,indent=2),encoding="utf-8")
            else:
                status["structural_repair_issues"]=fresh_issues
    distinct=story_is_distinct(story) if good else False
    # A "good" JSON/beat structure is not a good editorial story.
    # Fail closed when only secondary reportage is selected, or the audience
    # copy leaks source links or is plain boilerplate.
    from acolad_editorial_trust_gate import evaluate
    selected_path=RESEARCH_OUT/"selected_evidence.json"
    evidence=(json.loads(selected_path.read_text(encoding="utf-8"))
              if selected_path.exists() else [])
    editorial_gate=evaluate(story,evidence) if good and distinct else {
       "passed":False,"hard_vetoes":["UPSTREAM_RESEARCH_OR_STORY_FAILED"],
       "human_approved":False,"publish_allowed":False}
    status["independent_editorial_gate"]=editorial_gate
    # A sole FORMAL_1 issue is a grammatical style flaw, not permission
    # to invent a new story or lower editorial thresholds. Repair only fixed
    # passive-verb forms, then rerun all independent gates on the same facts.
    from acolad_voice_v4_guard import audience_issues
    if good and distinct and editorial_gate["passed"] and isinstance(story,dict):
        initial_voice=[p for frame in story.get("slides",[]) for p in audience_issues(frame.get("text",""))]
        if initial_voice and set(initial_voice)=={"FORMAL_1"}:
            candidate,changed=repair_colloquial_passive_without_new_claims(story)
            if changed:
                source_ok=evaluate(candidate,evidence).get("passed") is True
                factual_issues=news.story_quality(candidate,evidence)
                cinema_issues=news.cinematic_quality(candidate,evidence)
                still_formal=[p for frame in candidate.get("slides",[])
                              for p in audience_issues(frame.get("text",""))]
                if source_ok and not factual_issues and not cinema_issues and not still_formal:
                    story=candidate
                    status["voice_grammar_only_repaired"]=True
                    (output/"editorially_repaired_story.json").write_text(
                        json.dumps(story,ensure_ascii=False,indent=2),encoding="utf8")
    # Voice V4 remains a hard veto. No content is publishable without passing.
    voice_issues=[]
    if good and distinct and editorial_gate["passed"] and isinstance(story,dict):
        for slide in story.get("slides") or []:
            if not isinstance(slide,dict):
                voice_issues.append("INVALID_SLIDE")
                continue
            n=slide.get("n")
            voice_issues.extend(f"SLIDE_{n}_{x}" for x in audience_issues(slide.get("text","")))
    else:
        voice_issues=["UPSTREAM_EDITORIAL_GATE_FAILED"]
    status["voice_v4_gate"]={
        "passed":not voice_issues,
        "issues":voice_issues,
        "quality_score":"UNASSESSED",
        "human_approved":False,
        "publish_allowed":False,
    }
    status["dynamic_story_ready_for_design"]=bool(
        good and distinct and editorial_gate["passed"] and not voice_issues)
    status["editorial_result"]=(
        "VETO" if not status["dynamic_story_ready_for_design"]
        else "NEEDS_HUMAN_QUALITY_REVIEW")
    status["publish_allowed"]=False
    status["daily_editorial_pillar"]=pillar
    status["research_focus_today"]=focus
    status["narrative_style_today"]=style
    status["narrative_hook_direction"]=hook
    status["day_tehran"]=date.isoformat()
    status["history_urls_excluded_count"]=len(history)
    status["repeated_legacy_story_blocked"]=good and not distinct
    status["image_api_calls"]=0
    status["drafts"]=0
    status["scheduled"]=0
    status["published"]=0
    status["editorial_permission"]="REVIEW_ONLY"
    (output/"preview_status.json").write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf-8")
    if status["dynamic_story_ready_for_design"]:
        (output/"current_story.json").write_text(json.dumps(story,ensure_ascii=False,indent=2),encoding="utf-8")
        selected_path=RESEARCH_OUT/"selected_evidence.json"
        selected=json.loads(selected_path.read_text(encoding="utf-8")) if selected_path.exists() else []
        for item in selected:
            if item.get("url") and not any(x.get("url")==item["url"] for x in history):
                history.append({"url":item["url"],"title":item.get("title",""),
                                "date":date.isoformat()})
    # Do not keep a stale successful story if today's topic was vetoed.
    if not status["dynamic_story_ready_for_design"]:
        (output/"current_story.json").unlink(missing_ok=True)
    HISTORY.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding="utf-8")
    print("DAILY_DYNAMIC_STORY "+json.dumps({
        "status":original,"ready":status["dynamic_story_ready_for_design"],"hook":style,
        "model_calls":status.get("gapgpt_requests_sent"),"publication":"NEVER"},ensure_ascii=False))
    return status["dynamic_story_ready_for_design"]

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
