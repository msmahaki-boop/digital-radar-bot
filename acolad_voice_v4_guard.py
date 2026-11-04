#!/usr/bin/env python3
"""Acolad V4 deterministic editorial veto. Human literary judgment remains mandatory."""
from __future__ import annotations
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parent/"editorial"
BEATS=("wants_return","opens_order","checks_policy","reveals_cause",
       "hypothetical_emotion","business_tension","testable_actions",
       "compare_experiences","payoff")
EMOTIONS=("😕","😤","😳","🔎","💡","🛠️","❤️‍🔥","💥","🤔","🌱","😮‍💨","😔","😲")
FORMAL=(r"می[‌ ](?:شود|کنند|گردد|باشد|تواند)\b",
        r"(?:دیده|مشاهده|بررسی|انجام|ارائه)\s+شد(?:ه)?\b",
        r"این صحنه در یک آزمون واقعی",
        r"از نگاه سیستم|در دنیای امروز|در نهایت|شایان ذکر است")
UNSUPPORTED=(r"(?:(?:۱۵|15|پونزده)\s*دقیقه)",
             r"(?:(?:۷|7|هفت)\s*روز(?:ه)?)",
             r"مشتری\s+حس\s+کرد\s+سرش\s+کلاه",
             r"برنامه[‌ ]نویس(?:\s+سایت)?\s+دکمه\s+رو\s+حذف")
LEAKS=(r"📌",r"https?://|www[.]",r"\bACOLAD[-_][A-Z0-9_-]+\b",
       r"(?:منبع\s*[:：]|طبق\s+گزارش\s+دیجیاتو)")
def audience_issues(text):
    issues=[]
    for label,groups in (("FORMAL",FORMAL),("UNSUPPORTED",UNSUPPORTED),("LEAK",LEAKS)):
        for j,pattern in enumerate(groups):
            if re.search(pattern,str(text),re.I):issues.append(label+"_"+str(j))
    return issues

def check_carousel(doc):
    issues=[]
    slides=doc.get("slides") or []
    if doc.get("status")!="PREVIEW_ONLY" or doc.get("approved_by_owner") is not False:
        issues.append("PUBLICATION_NOT_GATED")
    if doc.get("editorial_score") is not None:
        issues.append("UNVERIFIED_HUMAN_SCORE")
    character=doc.get("character") or {}
    if character.get("name")=="محمد" and not character.get("fictional"):
        issues.append("FICTIONAL_CHARACTER_NOT_LABELED")
    if len(slides)!=9:
        issues.append("EXPECTED_NINE_SLIDE_REFERENCE")
    else:
        if tuple(s.get("beat") for s in slides)!=BEATS:
            issues.append("BROKEN_CHRONOLOGY")
        for slide in slides:
            n=slide["n"]
            head=str(slide.get("headline") or "")
            body=str(slide.get("body") or "")
            if n<1 or n>9:issues.append("BAD_FRAME_NUMBER")
            if not 2<=len(head.split())<=16:issues.append("BAD_HEADLINE_LENGTH_"+str(n))
            if not 10<=len(body.split())<=90:issues.append("BAD_PARAGRAPH_LENGTH_"+str(n))
            if body.count("📌") or head.count("📌"):issues.append("NO_PUSH_PIN_"+str(n))
            for problem in audience_issues(head+"\n"+body):
                issues.append(problem+"_SLIDE_"+str(n))
            num_emojis=sum(head.count(e)+body.count(e) for e in EMOTIONS)
            if num_emojis>2:issues.append("EMOJI_NOISE_"+str(n))
        if "تموم" not in slides[3].get("body",""):
            issues.append("CAUSE_NOT_REVEALED")
        if "شاید" not in slides[4].get("body",""):
            issues.append("HYPOTHETICAL_FEELING_UNLABELED")
        if "ممکنه" not in slides[5].get("body",""):
            issues.append("UNVERIFIED_BUSINESS_IMPACT_NOT_HEDGED")
        if "دکمه" not in slides[-1].get("body",""):
            issues.append("PAYOFF_NOT_RETURNED_TO_PROBLEM")
    evidence=doc.get("evidence") or {}
    if not str(evidence.get("url","")).startswith("https://"):
        issues.append("PRIMARY_EVIDENCE_MISSING")
    if not evidence.get("unsupported_as_fact"):
        issues.append("FACT_LIMITS_MISSING")
    return {"passed":not issues,"issues":list(dict.fromkeys(issues)),
            "human_score":"UNASSESSED","publication_allowed":False}

def check_progressive(doc):
    issues=[]
    frames=doc.get("frames") or []
    if doc.get("status")!="PREVIEW_ONLY" or doc.get("approved_by_owner") is not False:
        issues.append("PUBLICATION_NOT_GATED")
    if len(frames)!=9:
        issues.append("EXPECTED_NINE_PROGRESSIVE_FRAMES")
    else:
        for index,frame in enumerate(frames):
            n=index+1
            if frame.get("n")!=n or frame.get("scene_id")!=1+index//3:
                issues.append("PROGRESSIVE_SCENE_ORDER_"+str(n))
            if frame.get("action")!=("new_scene" if index%3==0 else "add_text"):
                issues.append("PROGRESSIVE_ACTION_"+str(n))
            text=str(frame.get("added_text") or "")
            if len(text.split())>35 or len(text.split())<4:
                issues.append("PROGRESSIVE_TEXT_LENGTH_"+str(n))
            for problem in audience_issues(text):
                issues.append(problem+"_FRAME_"+str(n))
    if not (doc.get("character") or {}).get("fictional"):
        issues.append("PROGRESSIVE_CHARACTER_NOT_LABELED")
    return {"passed":not issues,"issues":list(dict.fromkeys(issues)),
            "human_score":"UNASSESSED","publication_allowed":False}

def main():
    c=json.loads((ROOT/"voice_v4_return_button_carousel.json").read_text(encoding="utf-8"))
    s=json.loads((ROOT/"voice_v4_return_button_progressive.json").read_text(encoding="utf-8"))
    a=check_carousel(c);b=check_progressive(s)
    print("ACOLAD_V4_CAROUSEL "+json.dumps(a,ensure_ascii=False))
    print("ACOLAD_V4_STORY "+json.dumps(b,ensure_ascii=False))
    return 0 if a["passed"] and b["passed"] else 2
if __name__=="__main__":
    raise SystemExit(main())
