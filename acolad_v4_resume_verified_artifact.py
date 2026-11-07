#!/usr/bin/env python3
"""Restore ONE previously approved same-day source-backed story from a private
GitHub Actions artifact; no social writes, never trusts green-run status."""
import argparse,json
from datetime import date
from pathlib import Path
from acolad_v4_hourly_publish import (
    check_verified_editorial,save_editorial,EDITORIAL_CACHE)

def unique_file(root,name,folder):
    files=[p for p in root.rglob(name) if p.parent.name==folder]
    if len(files)!=1:
        raise RuntimeError("ARTIFACT_FILE_NOT_UNIQUE_"+folder+"_"+name)
    return files[0]

def restore_from_artifact(root:Path,day:date):
    source_status=json.loads(unique_file(root,"status.json","acolad_luna_research_preview").read_text(encoding="utf8"))
    preview=json.loads(unique_file(root,"preview_status.json","acolad_daily_editorial_output").read_text(encoding="utf8"))
    required={
        "source_status":source_status.get("status")=="PREVIEW_NEEDS_HUMAN_REVIEW",
        "source_issues":not source_status.get("issues"),
        "editorial_ready":preview.get("dynamic_story_ready_for_design") is True,
        "voice":(preview.get("voice_v4_gate") or {}).get("passed") is True,
        "independent":(preview.get("independent_editorial_gate") or {}).get("passed") is True,
        "date":preview.get("day_tehran")==day.isoformat(),
        "no_prior_social":source_status.get("novinhub_api_calls")==0,
    }
    if not all(required.values()):
        raise RuntimeError("HISTORIC_ARTIFACT_NOT_VALIDATED:"+",".join(k for k,v in required.items() if not v))
    story=json.loads(unique_file(root,"stories.json","acolad_luna_research_preview").read_text(encoding="utf8"))
    evidence=json.loads(unique_file(root,"selected_evidence.json","acolad_luna_research_preview").read_text(encoding="utf8"))
    check_verified_editorial(story,evidence)
    save_editorial(day,story,evidence)
    print("RESTORED_VERIFIED_STORY_PRIVATE",
          json.dumps({"day":day.isoformat(),
                      "story_frames":len(story["slides"]),
                      "sources":len(evidence),
                      "checkpoint":str(EDITORIAL_CACHE),
                      "social_posts_created":0}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--artifact-directory",required=True)
    p.add_argument("--tehran-date",required=True)
    a=p.parse_args()
    restore_from_artifact(Path(a.artifact_directory),date.fromisoformat(a.tehran_date))
