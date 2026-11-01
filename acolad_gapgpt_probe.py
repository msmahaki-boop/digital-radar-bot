#!/usr/bin/env python3
"""Isolated GapGPT exploration for Acolad. Manual/read-only by default, no publishing.

offline: local check, no network; catalog: GET /v1/models; trial: ONE explicit POST
using only a user-confirmed free API credit, no auto-publish.
"""
from __future__ import annotations
import argparse
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request

BASE = "https://api.gapgpt.app/v1"
OUT = Path("gapgpt_lab_results")
APPROVAL = "GAPGPT_ONE_TRIAL_APPROVED"
FREE_CONFIRM = "I_CHECKED_FREE_API_CREDIT"
CASE = ("این سناریو کاملاً فرضی است: فروشگاهی اینترنتی در ایران با افزایش هزینه ارسال و بسته‌بندی "
        "روبه‌روست، اما هنوز حاشیه سود هر سفارش را اندازه نگرفته است. هیچ رقم، درصد، "
        "خبر یا قانون واقعی در داده ورودی تأیید نشده است.")
PROMPT = ("تو نویسنده ارشد آژانس دیجیتال مارکتینگ آکولاد هستی؛ شریک رشد دیجیتال کسب‌وکار. "
          "فارسی طبیعی، صمیمی، دقیق و مناسب مدیر یک کسب‌وکار ایرانی بنویس. "
          "با این سناریو فقط یک پیش‌نویس آزمایشی تولید کن. "
          "۵ استوری زنجیره‌ای، هرکدام با عنوان کوتاه و متن ۲۰ تا ۳۵ کلمه‌ای؛ "
          "سپس یک پیام تلگرام ۱۰۰ تا ۱۴۰ کلمه‌ای. "
          "واقعیت ورودی، تحلیل احتمالی و مثال کاملاً فرضی را جدا کن. "
          "هیچ افزایش تعرفه اعلام‌شده، قانون، آمار، تضمین فروش یا تجربه واقعی آکولاد را جعل نکن. "
          "در پایان یک آزمایش قابل سنجش برای صاحب فروشگاه پیشنهاد بده. "
          "از کلیشه و عبارت‌های پرطمطراق بپرهیز. خروجی فارسی ساده، بدون JSON بده.\n\nسناریو:\n" + CASE)


class SafeAPIError(Exception):
    def __init__(self, code, category, provider_code="", provider_param=""):
        self.code = code
        self.category = category
        self.provider_code = provider_code
        self.provider_param = provider_param
        super().__init__(f"HTTP {code if code is not None else 'network'}: {category}")


def safe_error_field(value):
    """Keep only compact provider code/parameter identifiers, never raw error bodies."""
    if not isinstance(value, str) or len(value) > 64:
        return ""
    if value.lower().startswith(("sk-", "bearer", "aiza", "api_key", "apikey")):
        return ""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", value):
        return value
    return ""


def build_trial_payload(model):
    payload = {"model": model, "messages": [
        {"role": "system", "content": "تو نویسنده حرفه‌ای فارسی هستی. ادعای واقعی بدون منبع نساز."},
        {"role": "user", "content": PROMPT}],
        "max_tokens": 1800, "stream": False}
    # GPT-6 Luna defaults to medium reasoning. With a small completion budget,
    # reasoning tokens can exhaust the limit before any visible text appears.
    # For this ONE editorial-writing probe, request no hidden reasoning tokens.
    # GapGPT is a proxy: support for this parameter must be checked in live trial.
    if model == "gpt-6-luna":
        payload["reasoning_effort"] = "none"
    else:
        payload["temperature"] = 0.5
    return payload


def fetch_json(path, key, *, payload=None, timeout=35):
    if path not in ("/models", "/chat/completions"):
        raise ValueError("Endpoint not allowlisted")
    headers = {"Authorization": "Bearer " + key, "Accept": "application/json",
               "User-Agent": "Acolad-GapGPT-ResearchProbe/1.0"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, headers=headers,
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(2_000_001)
            if len(raw) > 2_000_000:
                raise SafeAPIError(None, "response too large")
            try:
                return json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise SafeAPIError(None, "non-JSON provider response") from None
    except urllib.error.HTTPError as e:
        # Intentionally do NOT display response bodies, headers, or authorization values.
        classification = {400: "bad request", 401: "key not accepted", 402: "payment/credit required",
                          403: "access denied", 404: "endpoint or model not available",
                          408: "timeout", 429: "rate limit / quota", 500: "provider error",
                          502: "upstream error", 503: "provider unavailable"}.get(e.code, "provider HTTP error")
        # The gateway may provide structured error.code/error.param. Only keep
        # allowlisted identifiers. Never keep error.message, raw body or headers.
        provider_code = provider_param = ""
        try:
            error_response = json.loads(e.read(8192).decode("utf-8"))
            details = error_response.get("error", {}) if isinstance(error_response, dict) else {}
            if isinstance(details, dict):
                provider_code = safe_error_field(details.get("code"))
                provider_param = safe_error_field(details.get("param"))
        except (ValueError, UnicodeError, OSError, AttributeError):
            pass
        raise SafeAPIError(e.code, classification, provider_code, provider_param) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise SafeAPIError(None, "network timeout / connection error") from None


def parse_models(obj):
    if not isinstance(obj, dict):
        raise SafeAPIError(None, "unexpected model catalog schema")
    data = obj.get("data")
    if not isinstance(data, list):
        raise SafeAPIError(None, "no model list in catalog; check provider documentation")
    ids = sorted({m.get("id") for m in data if isinstance(m, dict) and isinstance(m.get("id"), str)})
    return ids


def response_text(obj):
    if not isinstance(obj, dict):
        raise SafeAPIError(None, "unexpected completion schema")
    choices = obj.get("choices")
    if not isinstance(choices, list) or not choices:
        raise SafeAPIError(None, "no choices in completion")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    body = message.get("content", "")
    if isinstance(body, list):
        body = "\n".join(v.get("text", "") for v in body if isinstance(v, dict) and isinstance(v.get("text"), str))
    if not isinstance(body, str):
        body = ""
    usage = obj.get("usage") if isinstance(obj.get("usage"), dict) else {}
    # Token usage is informational, not a confirmed price.
    usage_safe = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                  if isinstance(usage.get(k), (int, float))}
    return body.strip(), str(first.get("finish_reason", "unknown")), usage_safe


def save_report(report, model_text=""):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "status.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if model_text:
        (OUT / "draft.txt").write_text(model_text[:40000], encoding="utf-8")
    lines = ["<!doctype html><html lang='fa' dir='rtl'><meta charset='utf-8'>",
             "<title>آزمایش مستقل اتصال گپ‌جی‌پی‌تی به آکولاد</title>",
             "<style>body{font:16px/2 Tahoma,Arial;max-width:900px;margin:auto;background:#f5f2eb;padding:24px;color:#172036}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:20px;border-radius:12px}</style>",
             "<h2>آزمایش مستقل GapGPT — بدون انتشار</h2>",
             "<p>خروجی فقط آزمایشی است؛ تأیید انسانی برای صحت و انتشار لازم است.</p>",
             "<pre>" + html.escape(json.dumps(report, ensure_ascii=False, indent=2)) + "</pre>"]
    if model_text:
        lines.append("<h3>متن تولیدشده</h3><pre>" + html.escape(model_text[:40000]) + "</pre>")
    lines.append("</html>")
    (OUT / "report.html").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "README_FA.txt").write_text(
        "آزمایش مستقل GapGPT آکولاد. هیچ چیزی منتشر نشده است. "
        "حالت catalog فقط فهرست مدل‌ها را درخواست می‌کند و پاسخ هزینه/سهمیه نیست. "
        "حالت trial یک درخواست تولید متن دارد و فقط پس از تأیید اعتبار API رایگان اجرا می‌شود.\n", encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("offline", "catalog", "trial"), default="offline")
    p.add_argument("--approval", default="")
    p.add_argument("--free-credit-confirmation", default="")
    a = p.parse_args(argv)
    report = {"project": "Acolad GapGPT standalone research", "mode": a.mode,
              "run_status": "NOT_RUN", "publication": "NEVER",
              "generated_utc": datetime.now(timezone.utc).isoformat(),
              "money_cost_verified": False,
              "notes": "This script neither publishes nor schedules any social content."}
    if a.mode == "offline":
        ids = parse_models({"data": [{"id": "fictional-A"}, {"id": "fictional-B"}]})
        assert len(ids) == 2
        report.update(run_status="OFFLINE_OK", fixture_models_count=2,
                      notes="Synthetic local test. No network calls, no API key used.")
        save_report(report)
        print("OFFLINE_OK | no API call | NO PUBLICATION")
        return 0

    key = os.getenv("GAPGPT_API_KEY", "").strip()
    if not key:
        report.update(run_status="MISSING_SECRET", error="Set GAPGPT_API_KEY in GitHub Actions Secrets")
        save_report(report)
        print("MISSING_SECRET: GAPGPT_API_KEY")
        return 0
    try:
        if a.mode == "catalog":
            ids = parse_models(fetch_json("/models", key, timeout=25))
            report.update(run_status="CATALOG_OK", models_count=len(ids),
                          model_ids=ids[:100],
                          notes="Model IDs are not free-price guarantees. Confirm API credit and model costs in provider dashboard.")
        else:
            model = os.getenv("ACOLAD_GAPGPT_MODEL_ID", "").strip()
            if a.approval != APPROVAL or a.free_credit_confirmation != FREE_CONFIRM:
                report.update(run_status="TRIAL_BLOCKED", reason="Explicit one-request approval and free API credit confirmation required")
            elif not model or not re.fullmatch(r"[\w./:-]{2,150}", model):
                report.update(run_status="TRIAL_BLOCKED", reason="Set an exact permitted model ID in ACOLAD_GAPGPT_MODEL_ID")
            else:
                t = time.monotonic()
                payload = build_trial_payload(model)
                obj = fetch_json("/chat/completions", key, payload=payload, timeout=95)
                text, finish, usage = response_text(obj)
                report.update(run_status="RESPONSE_RECEIVED_NEEDS_HUMAN_REVIEW" if text else "EMPTY_RESPONSE",
                              model_requested=model, response_seconds=round(time.monotonic()-t, 1),
                              response_characters=len(text), finish_reason=finish,
                              usage_tokens=usage,
                              notes="One provider completion; may spend gifted API credit. No price verification by this code.")
                save_report(report, text)
                print(report["run_status"], "| NO PUBLICATION")
                return 0
    except SafeAPIError as e:
        report.update(run_status="API_ERROR", http_status=e.code, error_category=e.category,
                      notes="Only safe provider error identifiers are recorded; no raw error, prompt or API key saved.")
        if e.provider_code:
            report["provider_error_code"] = e.provider_code
        if e.provider_param:
            report["provider_error_param"] = e.provider_param
    save_report(report)
    print(report["run_status"], "| NO PUBLICATION")
    return 0

if __name__ == "__main__":
    sys.exit(main())
