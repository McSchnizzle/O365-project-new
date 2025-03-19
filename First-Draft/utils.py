from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os

def parse_iso_time(iso_str):
    """
    Parse an ISO datetime string.
    If it ends with 'Z', replace it with '+00:00' so that datetime.fromisoformat() treats it as UTC.
    """
    s = iso_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception as e:
        raise ValueError(f"Could not parse datetime '{iso_str}': {e}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    return dt

def convert_to_pacific(iso_time_str):
    """
    Convert an ISO datetime string to America/Los_Angeles time in 12‑hour format.
    """
    dt = parse_iso_time(iso_time_str)
    dt_pacific = dt.astimezone(ZoneInfo("America/Los_Angeles"))
    if os.name != 'nt':
        return dt_pacific.strftime("%-I:%M %p")
    else:
        return dt_pacific.strftime("%#I:%M %p")

def get_event_start_dt(event):
    """
    Return the event’s start datetime as a timezone-aware datetime.
    If the event's start includes a timeZone of 'Pacific Standard Time' or 'Pacific Daylight Time',
    assume the provided dateTime is already in Pacific.
    """
    start_obj = event.get("start", {})
    dt_str = start_obj.get("dateTime")
    tz_str = start_obj.get("timeZone")
    if dt_str:
        if tz_str in ["Pacific Standard Time", "Pacific Daylight Time"]:
            try:
                dt = datetime.fromisoformat(dt_str)
            except Exception:
                dt = parse_iso_time(dt_str)
            return dt.replace(tzinfo=ZoneInfo("America/Los_Angeles"))
        else:
            return parse_iso_time(dt_str)
    elif "date" in start_obj:
        dt_str = start_obj["date"] + "T00:00:00+00:00"
        return datetime.fromisoformat(dt_str)
    return None

def should_ignore_event(event):
    """
    Return True if the event should be ignored.
    For example, if the organizer is sjb@silvix.org and the subject contains 'reservation confirmed'.
    """
    if not event:
        return True
    subject = event.get("subject") or ""
    organizer = event.get("organizer", {}).get("emailAddress", {}).get("address", "").lower()
    return organizer == "sjb@silvix.org" and "reservation confirmed" in subject.lower()
