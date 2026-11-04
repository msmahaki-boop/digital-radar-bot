#!/usr/bin/env python3
"""One single NovinHub file upload response schema probe. No public post/draft creation."""
from pathlib import Path
import json,requests
from acolad_novinhub_bridge import token,headers,API
p=Path("stories_output/01_intro.png")
assert p.is_file()
with p.open("rb") as f:
    res=requests.post(API+"/file",headers=headers(token()),
        files={"file":(p.name,f,"image/png")},timeout=100)
report={"status":"SCHEMA_DIAGNOSTIC_ONLY","http_status":res.status_code,"social_posts":0}
if res.status_code in (200,201):
    try:
        obj=res.json()
        report["top_type"]=type(obj).__name__
        if isinstance(obj,dict):
            report["top_keys"]=sorted(obj.keys())[:20]
            d=obj.get("data")
            report["data_type"]=type(d).__name__
            if isinstance(d,dict):
                report["data_keys"]=sorted(d.keys())[:30]
                report["data_id_type"]=type(d.get("id")).__name__
                if isinstance(d.get("file"),dict):
                    report["nested_file_keys"]=sorted(d["file"].keys())[:30]
                    report["nested_file_id_type"]=type(d["file"].get("id")).__name__
            elif isinstance(d,list):
                report["data_length"]=len(d)
                if d and isinstance(d[0],dict):
                    report["data_first_keys"]=sorted(d[0].keys())[:30]
                    report["first_id_type"]=type(d[0].get("id")).__name__
        elif isinstance(obj,list):
            report["root_list_length"]=len(obj)
    except ValueError: report["json"]="INVALID"
print("SAFE_NOVINHUB_SINGLE_UPLOAD_SCHEMA "+json.dumps(report,ensure_ascii=False))
