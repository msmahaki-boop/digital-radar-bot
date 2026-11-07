#!/usr/bin/env python3
"""Acolad editorial safety contract. Conservative deterministic veto, NOT a quality score.

Pass means suitable for human evaluation, never authorization to publish.
Never fetches links, bills an AI model, or calls a social API.
"""
from __future__ import annotations
import json,re
from pathlib import Path
from urllib.parse import urlsplit

POLICY=Path(__file__).resolve().parent/"editorial"/"acolad_editorial_contract.json"
KNOWN_OFFICIAL={"anthropic.com","openai.com","developers.googleblog.com","developers.google.com","blog.google",
                "research.google","about.fb.com","shopify.com"}
SECONDARY={"digiato.com","zoomit.ir","peivast.com","dmboard.media",
           "way2pay.ir","techcrunch.com"}
LEAKS=[
    ("raw_link",re.compile(r"https?://|www[.]",re.I)),
    ("technical_marker",re.compile(r"\bACOLAD[-_][A-Z0-9_-]{5,}\b",re.I)),
    ("source_label",re.compile(r"(?:منبع(?: خبر)?\s*[:：]|خبر می.گ[وه]|طبق گزارش دیجیاتو)",re.I)),
    ("private_production_notes",re.compile(r"(?:source_ids|preview_only|QA_BLOCKED|پیشنهاد استیکر دستی)",re.I)),
]
def _host(url):
    try:return (urlsplit(str(url)).hostname or "").lower().removeprefix("www.")
    except (ValueError,TypeError):return ""

def _matches(host,domain):
    return bool(host and (host==domain or host.endswith("."+domain)))

def load_policy(path=POLICY):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def evaluate(story,evidence,policy=None):
    """Hard veto only; source list is internal and independent of shown captions."""
    policy=policy or load_policy()
    errors=[]
    if not isinstance(story,dict) or not isinstance(story.get("slides"),list):
        return {"passed":False,"hard_vetoes":["STORY_NOT_STRUCTURED"],"human_approved":False}
    evidence=evidence if isinstance(evidence,list) else []
    approved_hosts={x["domain"] for x in policy["source_policy"]["priority_sources"]}
    chosen=[s for s in evidence if isinstance(s,dict) and
            s.get("evidence_depth") in ("full_article","abstract") and
            str(s.get("url","")).startswith("https://")]
    if not chosen:errors.append("NO_SUBSTANTIVE_VERIFIED_ARTICLE")
    if not any(any(_matches(_host(s.get("url")),x) for x in approved_hosts|KNOWN_OFFICIAL) or
               s.get("source_type")=="academic_doi" for s in chosen):
        errors.append("NO_PRIMARY_OR_SPECIALIST_SOURCE")
    if chosen and all(any(_matches(_host(s.get("url")),x) for x in SECONDARY)
                      for s in chosen):
        errors.append("ONLY_SECONDARY_MEDIA")
    text=[str(story.get("topic") or "")]+[str(s.get("text") or "") for s in story["slides"]
          if isinstance(s,dict)]
    for index,segment in enumerate(text):
        for code,pattern in LEAKS:
            if pattern.search(segment):errors.append(f"PUBLIC_TEXT_{code.upper()}_{index}")
    frames=story["slides"]
    if len(frames)<4:errors.append("NOT_ENOUGH_NARRATIVE_PROGRESS")
    if sum("خبر می" in str(f.get("text") or "") for f in frames if isinstance(f,dict))>0:
        errors.append("REPORTED_HEADLINE_INSTEAD_OF_LIVED_STORY")
    if any("هنوز معلوم نیست" in str(f.get("text") or "") for f in frames[-2:] if isinstance(f,dict)):
        errors.append("UNRESOLVED_ENDING")
    if not story.get("resolution") or not (story.get("resolution") or {}).get("answer"):
        errors.append("NO_CONCRETE_RESOLUTION")
    # Deliberately DO NOT infer literary quality from passing these rules.
    # Required 100-point human rubric and two reviewers remain separate.
    errors=list(dict.fromkeys(errors))
    return {"passed":not errors,"hard_vetoes":errors,"human_approved":False,
            "publish_allowed":False,"quality_score":"UNASSESSED",
            "reason":"Passing mechanical checks cannot prove story quality."}

def check_public_copy(text):
    problems=[code for code,pattern in LEAKS if pattern.search(str(text))]
    return {"clean":not problems,"violations":problems}

def require_human_release(votes,policy=None):
    p=policy or load_policy()
    dimensions=p["approval_rubric"];limit=p["min_human_score"]
    if not isinstance(votes,list) or len(votes)<p["min_independent_human_reviewers"]:
        return False
    for vote in votes:
        if not isinstance(vote,dict) or vote.get("explicit_approve") is not True:
            return False
        if any(not isinstance(vote.get(k),int) or not (0<=vote[k]<=maximum)
               for k,maximum in dimensions.items()):
            return False
        if sum(vote[k] for k in dimensions)<limit:
            return False
    return True
