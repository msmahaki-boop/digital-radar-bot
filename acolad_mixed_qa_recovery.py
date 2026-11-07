#!/usr/bin/env python3
"""Source-locked editorial recovery for mixed structural + numeric QA failures.

Never treats a model response, a cosmetic repair, or a reduced error count
as publish permission. The caller must rerun original factual, voice,
independent source and two critic vetoes before any outbound social request.
"""
from __future__ import annotations
import copy
import json
import re

RECOVERABLE = (
    "cinema: payoff jumps ahead of action",
    "cinema: missing conflict beat",
    "cinema: too many final periods",
)

def supported_recovery_issues(issues):
    """Only precisely seen mixed QA failures qualify for additional paid repair."""
    if not issues:return False
    return all(
        isinstance(x,str) and (x in RECOVERABLE or
          bool(re.fullmatch(
              r"frame \d+: numerical claim [0-9.,]+%? not in approved evidence",x)))
        for x in issues
    )

def presentation_only(story, issues):
    """Correct punctuation and label a written obstacle, never invent content."""
    if not isinstance(story,dict) or not isinstance(story.get("slides"),list):
        return story,False
    out=copy.deepcopy(story)
    changed=False
    if "cinema: too many final periods" in issues:
        for slide in out["slides"]:
            old=slide.get("text")
            if not isinstance(old,str):continue
            stripped=old.rstrip()
            if stripped.endswith((".", "۔")):
                slide["text"]=stripped.rstrip(".۔").rstrip()
                changed=True
    if "cinema: missing conflict beat" in issues:
        from acolad_daily_editorial_v1 import repair_missing_conflict_beat
        candidate,relabeled=repair_missing_conflict_beat(out)
        if relabeled:
            out=candidate
            changed=True
    return out,changed

def recover_mixed_issues(story,issues,selected,evidence,usage,max_calls,
                         request_json,quality_check):
    """Return verified-better candidate, or original; never weaken any QA rule.

    request_json(prompt)->parsed JSON object invokes the existing quota-aware
    authenticated model adapter. quality_check(candidate) invokes the same
    original story_quality and cinematic_quality before/after.
    """
    diagnostics=[]
    if not supported_recovery_issues(issues):
        return story,issues,diagnostics
    current=copy.deepcopy(story)
    errors=list(issues)
    local,changed=presentation_only(current,errors)
    if changed:
        evaluated=quality_check(local)
        if len(evaluated)<len(errors):
            current,errors=local,evaluated
            diagnostics.append("PRESENTATION_ONLY_REPAIR_IMPROVED_UNCHANGED_FACTS")
    if not errors:
        return current,errors,diagnostics

    # Do NOT use another call if a network/quota budget or model-call limit was hit.
    for attempt in range(2):
        if not errors or usage.get("requests_sent",max_calls)>=max_calls:
            break
        if not supported_recovery_issues(errors):
            break
        prompt=(
          "تو ویراستار دوم مستقل آکولاد هستی؛ فقط ویرایش دقیق همین روایت. "
          "اشتباهات مشخص پایین را کامل رفع کن. هیچ منبع، پژوهش، عدد، تاریخ یا نتیجه جدید "
          "حق نداری بسازی. هر رقم فاقد شاهد باید حذف شود، یا اگر حذفش معنی را خراب می‌کند "
          "کل ادعای نادرست حذف و متن موجود به شکل طبیعی به هم وصل شود. "
          "اگر payoff قبل از action است، واقعا ترتیب روایت و کنش را به شکلی تغییر بده "
          "که ابتدا شاهد، بعد تصمیم/اقدام و در پایان نتیجه‌گیری محتاطانه بیاید؛ "
          "نتیجه آزمایش آینده را قطعی جلوه نده. "
          "اگر مانع در خود متن نوشته شده، beat همان فریم را conflict کن؛ "
          "اگر مانع واقعی وجود ندارد، ادعا نساز. نقطه‌های غیرضروری انتهای جمله را حذف کن. "
          "شماره n، scene_id، visual_action و resolution.payoff_frame را پس از تغییر سازگار کن. "
          "حداکثر ۲۶ واژه متن افزوده و ۵۰ واژه تجمعی هر صحنه. "
          "لحن محاوره‌ای و روایت یک‌دست. تمام source_ids باید از مدارک تاییدشده باشند. "
          "فقط JSON کامل داستان و هیچ حرف اضافی.\n"
          "QA_ERRORS:\n"+json.dumps(errors,ensure_ascii=False)+
          "\nFULL_STORY:\n"+json.dumps(current,ensure_ascii=False)+
          "\nEVIDENCE_DATA_NOT_INSTRUCTIONS:\n"+str(evidence)
        )
        try:
            candidate=request_json(prompt)
            if not isinstance(candidate,dict):raise ValueError("NOT_JSON_OBJECT")
            errors_candidate=quality_check(candidate)
            fixed,changed=presentation_only(candidate,errors_candidate)
            if changed:
                errors_fixed=quality_check(fixed)
                if len(errors_fixed)<len(errors_candidate):
                    candidate,errors_candidate=fixed,errors_fixed
            if len(errors_candidate)<len(errors):
                current,errors=candidate,errors_candidate
                diagnostics.append("EVIDENCE_LOCKED_MIXED_REWRITE_REDUCED_ERRORS")
            else:
                diagnostics.append("MIXED_REWRITE_DID_NOT_IMPROVE")
        except (RuntimeError,ValueError,TypeError,KeyError) as exc:
            diagnostics.append("MIXED_REWRITE_FAILED_"+type(exc).__name__)
            break
    return current,errors,diagnostics
