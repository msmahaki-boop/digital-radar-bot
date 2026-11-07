#!/usr/bin/env python3
"""Bounded direct-Google text fallback ONLY after GapGPT key quota refusal.

All source selection and QA remain in callers. This module handles model
transport, never posts to social platforms and never logs API credentials.
"""
from __future__ import annotations
import os
import time
import requests

MODEL = "gemini-3-flash-preview"
API = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
MAX_TOTAL_FALLBACK_CALLS = 12
_fallback_calls = 0


def generate_json(system: str, user: str, max_tokens: int, parser, usage: dict, session=requests):
    global _fallback_calls
    if _fallback_calls >= MAX_TOTAL_FALLBACK_CALLS:
        raise RuntimeError("GEMINI_FALLBACK_DAILY_CALL_LIMIT")
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_FALLBACK_SECRET_MISSING")
    if max_tokens < 100 or max_tokens > 6000:
        raise RuntimeError("GEMINI_FALLBACK_TOKEN_ALLOWANCE_INVALID")
    _fallback_calls += 1
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.55,
            "maxOutputTokens": max_tokens,
        },
    }
    t0 = time.monotonic()
    try:
        response = session.post(API, headers={"x-goog-api-key":key,
                              "Content-Type":"application/json"},
                                json=payload,timeout=145)
    except requests.RequestException as exc:
        raise RuntimeError("GEMINI_FALLBACK_NETWORK_"+type(exc).__name__) from None
    if response.status_code != 200:
        raise RuntimeError("GEMINI_FALLBACK_HTTP_"+str(response.status_code))
    try:
        body = response.json()
        candidates = body.get("candidates") or []
        if not candidates:
            raise ValueError("NO_CANDIDATE")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        content = "".join(p.get("text","") for p in parts if isinstance(p,dict))
        if not content.strip():
            raise ValueError("NO_VISIBLE_TEXT")
        result=parser(content)
        meta=body.get("usageMetadata") or {}
        usage.setdefault("stages",[]).append({
            "provider": MODEL,
            "route":"GAPGPT_PRECONSUME_KEY_QUOTA_FALLBACK",
            "elapsed_sec":round(time.monotonic()-t0,2),
            "prompt_tokens":meta.get("promptTokenCount"),
            "completion_tokens":meta.get("candidatesTokenCount"),
            "cost_usd":"NOT_VERIFIED_FROM_PROVIDER",
        })
        usage["gemini_fallback_calls"]=usage.get("gemini_fallback_calls",0)+1
        return result
    except (ValueError,TypeError,KeyError,IndexError) as exc:
        raise RuntimeError("GEMINI_FALLBACK_INVALID_JSON_"+type(exc).__name__) from None
