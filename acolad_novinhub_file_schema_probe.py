#!/usr/bin/env python3
"""Read-only NovinHub file manager response-shape diagnostic. Never prints URLs, names or tokens."""
import json,os,requests
from acolad_novinhub_bridge import token,API,headers
try:
    r=requests.get(API+"/file",headers=headers(token()),params={"page":1},timeout=30)
    report={"status":"FILE_LIST_HTTP","http_status":r.status_code}
    if r.status_code==200:
        obj=r.json()
        report["top_level_type"]=type(obj).__name__
        if isinstance(obj,dict):
            report["top_level_keys"]=sorted(obj.keys())[:20]
            data=obj.get("data")
            report["data_type"]=type(data).__name__
            rows=data if isinstance(data,list) else data.get("data") if isinstance(data,dict) else []
        else:rows=obj if isinstance(obj,list) else []
        if isinstance(rows,list):
            report["count"]=len(rows)
            if rows:
                item=rows[0]
                if isinstance(item,dict):
                    report["item_keys"]=sorted(item.keys())[:30]
                    report["id_type"]=type(item.get("id")).__name__
                    report["id_is_int_or_digit"]=isinstance(item.get("id"),int) or str(item.get("id","")).isdigit()
    print("SAFE_NOVINHUB_FILE_SCHEMA "+json.dumps(report,ensure_ascii=False))
except Exception as e:
    print("SAFE_NOVINHUB_FILE_SCHEMA "+json.dumps({"status":"ERROR","type":type(e).__name__}))
