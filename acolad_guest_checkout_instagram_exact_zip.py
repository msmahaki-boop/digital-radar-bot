#!/usr/bin/env python3
"""Upload the exact 9-frame ZIP to NovinHub as ONE Instagram DRAFT, never publish.

Requires a human to upload the previously reviewed ZIP to the review-only
feature branch. The content digest is pinned so unexpected images fail closed.
"""
from __future__ import annotations
import argparse,hashlib,json,re,sys,tempfile,zipfile
from pathlib import Path
import requests
from PIL import Image
from acolad_novinhub_bridge import API,token,accounts,headers,as_items,create_post,upload_file

ZIP=Path("assets/reviews/Acolad_Guest_Checkout_V4_Preview_20261104.zip")
EXPECTED_SHA256="4d3debc899a0d7991ca427db03c1119756e93c5b884f3df4f946331b40715c4d"
STORY=Path("editorial/previews/acolad_guest_checkout_v4_20261104.json")
OUTPUT=Path("acolad_guest_checkout_instagram_draft_receipt")
ACCOUNT_ID=230527
PREFIX="Instagram_Stories/"
FILES=[PREFIX+f"ACOLAD_Story_{i:02d}.png" for i in range(1,10)]

def get_drafts(key):
    res=requests.get(API+"/post/draft",headers=headers(key),timeout=40)
    if res.status_code!=200:raise RuntimeError("NovinHub drafts unavailable")
    obj=res.json(); rows=as_items(obj)
    if rows is None or len(rows)>=100:raise RuntimeError("Draft list ambiguous or paginated")
    return rows

def run():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    report={"type":"EXACT_9_FRAME_INSTAGRAM_STORY_DRAFT","published":0,"scheduled":0,
            "queued":0,"complete_frame_count":0,"source_file":str(ZIP)}
    try:
        if not ZIP.is_file():raise FileNotFoundError("Exact previously approved review ZIP missing from GitHub")
        data=ZIP.read_bytes()
        if hashlib.sha256(data).hexdigest()!=EXPECTED_SHA256:
            raise RuntimeError("ZIP SHA-256 does not match user's reviewed preview package")
        if not zipfile.is_zipfile(ZIP):raise RuntimeError("Invalid ZIP")
        meta=json.loads(STORY.read_text(encoding="utf-8"))
        if meta.get("publication_allowed") is not False:
            raise RuntimeError("Editorial preview lock absent")
        caption=meta["captions"]["instagram"]
        if not caption.strip() or "baymard.com" in caption.lower():raise RuntimeError("Unexpected caption")
        with zipfile.ZipFile(ZIP) as zipfile_obj:
            names=set(zipfile_obj.namelist())
            if not all(f in names for f in FILES):raise RuntimeError("Missing approved frames")
            if any(".." in Path(f).parts for f in names):raise RuntimeError("ZIP unsafe path")
            with tempfile.TemporaryDirectory(prefix="acolad_guest_review_") as tmp:
                paths=[]
                for filename in FILES:
                    raw=zipfile_obj.read(filename)
                    if not 5000<len(raw)<18_000_000:raise RuntimeError("Unexpected frame size")
                    p=Path(tmp)/Path(filename).name
                    p.write_bytes(raw)
                    with Image.open(p) as im:
                        if im.format!="PNG" or im.size!=(1080,1920):
                            raise RuntimeError("Frame geometry or encoding invalid")
                        im.verify()
                    paths.append(p)
                report["complete_frame_count"]=len(paths)
                k=token()
                live=accounts(k)
                if live["instagram"]!=ACCOUNT_ID:raise RuntimeError("Instagram account id mismatch")
                existing=[p for p in get_drafts(k) if isinstance(p,dict)
                          and str(p.get("caption") or "")==caption]
                if len(existing)>1:raise RuntimeError("Multiple identical drafts detected")
                if existing:
                    report["status"]="EXISTING_IDENTICAL_DRAFT_NOT_DUPLICATED"
                    report["post_id"]=existing[0].get("id")
                    return report
                media_ids=[upload_file(k,p) for p in paths]
                if len(media_ids)!=9:raise RuntimeError("Incomplete media uploads")
                response=create_post(k,"instagram",caption,media_ids,draft=True)
                report["post_id"]=response["post_id"]
                report["status"]="CREATED_NEEDS_READBACK"
                (OUTPUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
                verified=[p for p in get_drafts(k) if isinstance(p,dict)
                          and str(p.get("id"))==str(response["post_id"])
                          and str(p.get("caption") or "")==caption]
                if not verified:raise RuntimeError("Post ID not found in NovinHub drafts")
                if any(str(x.get("is_scheduled")).lower() not in ("0","false","none","") for x in verified):
                    raise RuntimeError("Unexpected scheduling state: must review manually")
                report["status"]="INSTAGRAM_DRAFT_READBACK_VERIFIED"
    except Exception as exc:
        report["status"]="BLOCKED_"+type(exc).__name__
        report["error_class"]=str(exc)[:150]
    finally:
        (OUTPUT/"status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("ACOLAD_GUEST_IG_DRAFT "+json.dumps(report,ensure_ascii=False),flush=True)
    return report

if __name__=="__main__":
    result=run()
    sys.exit(0 if result["status"] in
            ("INSTAGRAM_DRAFT_READBACK_VERIFIED","EXISTING_IDENTICAL_DRAFT_NOT_DUPLICATED") else 2)
