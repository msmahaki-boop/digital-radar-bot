#!/usr/bin/env python3
"""Mechanical veto for known Acolad story failures; NEVER a literary score or publish license."""
from __future__ import annotations
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parent/"editorial"
BEATS=("hook","search","search_policy","cause_reveal","reader_perspective",
       "business_implication","testable_actions","comparison","payoff")
BOOKISH={
 "translated":r"(?:در دنیای امروز|در نهایت|شایان ذکر|این صحنه|از نگاه سیستم|از نظر معنایی|مورد بررسی قرار|در این راستا)",
 "formal_passive":r"(?:دیده|مشاهده|بررسی|حذف|انجام|ارائه)\s+شد(?:ه)?\b",
 "formal_verb":r"(?:می[‌ ](?:شود|کنند|تواند|گردد|باشد)|نمی[‌ ](?:شود|تواند))",
}
LEAK={
 "source_url":r"https?://|www\.",
 "technical_marker":r"ACOLAD[-_][A-Z0-9_-]+",
 "source_footer":r"(?:منبع(?: خبر)?\s*[:：]|طبق گزارش دیجیاتو)",
}
UNVERIFIED={
 "duration_15min":r"(?:۱۵|15|پونزده)\s*دقیقه",
 "return_7days":r"(?:۷|7|هفت)\s*روز(?:ه)?",
 "definite_cheated_feeling":r"(?:مشتری|کاربر|شرکت[‌ ]کننده)\s+(?:حس\s+کرد|فکر\s+کرد)\s+(?:سرش\s+کلاه|فریب\s+خورده)",
 "programmer_action":r"برنامه[‌ ]نویس(?:\s+سایت)?\s+دکمه(?:\s+رو|\s+را)\s+(?:غیب|حذف)",
}
def audience_errors(text:str):
 out=[]
 for prefix,group in (("BOOKISH",BOOKISH),("LEAK",LEAK),("INVENTED_FACT",UNVERIFIED)):
  for name,pat in group.items():
   if re.search(pat,str(text),flags=re.I):out.append(prefix+"_"+name.upper())
 return out

def check_carousel(doc:dict):
 errs=[]
 s=doc.get("slides") or []
 if len(s)!=9:return {"passed":False,"issues":["NINE_INDEPENDENT_SLIDES_REQUIRED"],
                         "human_score":"UNASSESSED","publish_allowed":False}
 if doc.get("publication")!="PREVIEW_ONLY_NOT_APPROVED":errs.append("UNSAFE_PUBLICATION_STATUS")
 if doc.get("human_score") is not None:errs.append("HUMAN_SCORE_WAS_NOT_VERIFIED")
 if tuple(f.get("beat_id") for f in s)!=BEATS:errs.append("BROKEN_CAUSE_AND_EFFECT_BEATS")
 for i,frame in enumerate(s,1):
  text=str(frame.get("text") or "")
  wc=len(text.split())
  if not 35<=wc<=65:errs.append(f"SLIDE_{i}_WORD_COUNT_{wc}")
  if i==1:
   if not text.startswith("💭") or "\n\n📌" not in text:errs.append("HOOK_MISSING")
  elif not text.startswith("📌"):errs.append(f"SLIDE_{i}_PARAGRAPH_MISSING")
  errs.extend(f"SLIDE_{i}_{x}" for x in audience_errors(text))
  if wc!=frame.get("words"):errs.append(f"SLIDE_{i}_WORDCOUNT_METADATA_STALE")
 first=s[0]["text"]
 action=re.search(r"سفارش(?:ت|ش)?\s+رو\s+(?:پیدا|باز)",first)
 discovery=re.search(r"دکمه.{0,45}(?:نبود|ندیدی|ندید|نیست)",first)
 if discovery and (not action or discovery.start()<action.start()):
  errs.append("CHRONOLOGY_RESULT_BEFORE_ACTION")
 if "تموم" not in s[3]["text"] and "گذشته" not in s[3]["text"]:
  errs.append("NO_SOURCE_BASED_REVEAL")
 if len(re.findall(r"^\+\s",s[6]["text"],flags=re.M))<4:
  errs.append("FOUR_CONCRETE_ACTIONS_MISSING")
 if not any(x in s[8]["text"] for x in ("دکمه","مرجوعی","توضیح")):
  errs.append("ENDING_NOT_LINKED_TO_OPENING")
 ev=doc.get("evidence") or {}
 if ev.get("source_type")!="firsthand_research" or not str(ev.get("url") or "").startswith("https://"):
  errs.append("FIRST_PARTY_EVIDENCE_MISSING")
 if not ev.get("caveats"):errs.append("SOURCE_SCOPE_NOT_RECORDED")
 return {"passed":not errs,"issues":list(dict.fromkeys(errs)),
         "human_score":"UNASSESSED","publish_allowed":False}

def check_progressive(doc):
 frames=doc.get("frames") or []
 errs=[]
 if len(frames)!=9:errs.append("NINE_PROGRESSIVE_FRAMES_REQUIRED")
 else:
  for i,frame in enumerate(frames):
   n=i+1
   if frame.get("n")!=n or frame.get("scene_id")!=i//3+1:
    errs.append(f"FRAME_{n}_SCENE_OR_ORDER")
   if frame.get("action")!=("new_scene" if i%3==0 else "add_text"):
    errs.append(f"FRAME_{n}_ACTION_INVALID")
   text=str(frame.get("added_text") or "")
   if not 6<=len(text.split())<=30:errs.append(f"FRAME_{n}_TEXT_LENGTH")
   errs.extend(f"FRAME_{n}_{x}" for x in audience_errors(text))
  if "سفارش" not in frames[0]["added_text"] or "باز" not in frames[0]["added_text"]:
   errs.append("PROGRESSIVE_FIRST_FRAME_NOT_ACTION")
  if "دکمه" not in frames[1]["added_text"] or "ندید" not in frames[1]["added_text"]:
   errs.append("PROGRESSIVE_SECOND_FRAME_NO_CONFLICT")
 if doc.get("draft_only") is not True:errs.append("NOT_LOCKED_TO_DRAFT_ONLY")
 return {"passed":not errs,"issues":list(dict.fromkeys(errs)),
         "human_score":"UNASSESSED","publish_allowed":False}

def main():
 a=json.loads((ROOT/"voice_v3_return_button_carousel.json").read_text(encoding="utf-8"))
 b=json.loads((ROOT/"voice_v3_return_button_progressive.json").read_text(encoding="utf-8"))
 x=check_carousel(a);y=check_progressive(b)
 print("ACOLAD_VOICE_V3_CAROUSEL "+json.dumps(x,ensure_ascii=False))
 print("ACOLAD_VOICE_V3_STORY "+json.dumps(y,ensure_ascii=False))
 return 0 if x["passed"] and y["passed"] else 2

if __name__=="__main__":
 raise SystemExit(main())
