#!/usr/bin/env python3
"""Flexible *Tehran-local* NovinHub slot planner.

Do not publish in the past. Delayed jobs slide all three times forward
together, or safely schedule the next day's default times near midnight.
It never bypasses source QA, account checks, or duplicate prevention.
"""
from __future__ import annotations
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TEHRAN=ZoneInfo("Asia/Tehran")
OFFSETS={"telegram":0, "bale":5, "instagram":30}
DEFAULT= (17,30)
MIN_LEAD=timedelta(minutes=50)
LAST_STORY=time(23,40)

def plan_release(content_day:date, now:datetime)->tuple[dict[str,datetime],str]:
    if not isinstance(content_day,date) or not isinstance(now,datetime) or now.tzinfo is None:
        raise ValueError("Expected a date and an aware datetime")
    local=now.astimezone(TEHRAN)
    if local.date()<content_day or local.date()>content_day+timedelta(days=1):
        raise ValueError("Content day is too stale for safe daily posting")
    base=datetime(content_day.year,content_day.month,content_day.day,*DEFAULT,tzinfo=TEHRAN)
    first=max(base,local+MIN_LEAD)
    slots={network:first+timedelta(minutes=offset) for network,offset in OFFSETS.items()}
    if slots["instagram"].date()==content_day and slots["instagram"].time()<=LAST_STORY:
        return slots,("NORMAL" if first==base else "DELAYED_SAME_DAY")
    # Too late today. Do not put a past timestamp into NovinHub.
    tomorrow=content_day+timedelta(days=1)
    base=datetime(tomorrow.year,tomorrow.month,tomorrow.day,*DEFAULT,tzinfo=TEHRAN)
    first=max(base,local+MIN_LEAD)
    slots={network:first+timedelta(minutes=offset) for network,offset in OFFSETS.items()}
    if slots["instagram"].date()!=tomorrow or slots["instagram"].time()>LAST_STORY:
        raise RuntimeError("NEXT_DAY_SLOT_UNSAFE")
    return slots,"NEXT_DAY_ROLLOVER"
