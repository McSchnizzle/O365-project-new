"""Utility functions for date/time conversion and parsing.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

def parse_iso_time(iso_str: str) -> datetime:
    s = iso_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    return dt

def convert_to_pacific(iso_time_str: str) -> str:
    """
    Convert an ISO datetime string to Pacific time in 12‑hour format.
    This version uses "%I:%M %p" and then strips any leading zero.
    """
    dt = parse_iso_time(iso_time_str)
    dt_pacific = dt.astimezone(ZoneInfo("America/Los_Angeles"))
    formatted = dt_pacific.strftime("%I:%M %p")
    if formatted.startswith("0"):
        formatted = formatted[1:]
    return formatted

def get_event_start_dt(event: dict) -> Optional[datetime]:
    start_obj = event.get("start", {})
    dt_str = start_obj.get("dateTime")
    if dt_str:
        try:
            dt = datetime.fromisoformat(dt_str)
        except Exception:
            dt = parse_iso_time(dt_str)
        return dt
    elif "date" in start_obj:
        return datetime.fromisoformat(start_obj["date"] + "T00:00:00+00:00")
    return None

def should_ignore_event(event: dict) -> bool:
    """
    Return True if the event should be ignored.
    For example, if the organizer is sjb@silvix.org and the subject contains "reservation confirmed".
    """
    subject = (event.get("subject") or "").lower()
    organizer = (event.get("organizer", {}).get("emailAddress", {}).get("address") or "").lower()
    return organizer == "sjb@silvix.org" and "reservation confirmed" in subject
