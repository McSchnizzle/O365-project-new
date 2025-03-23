# utils.py
from datetime import datetime
import pytz
from dateutil import parser
from config import PACIFIC_TIMEZONE

def parse_datetime(dt_str):
    """
    Parses a datetime string into a datetime object.
    Supports ISO strings (with or without trailing 'Z') and other common formats.
    """
    try:
        dt = parser.parse(dt_str)
        return dt
    except Exception as e:
        print(f"Error parsing datetime string '{dt_str}': {e}")
        return None

def to_pacific(dt):
    """
    Converts a datetime object to Pacific Time.
    If the datetime is naive (no timezone info), it assumes UTC.
    """
    pacific = pytz.timezone(PACIFIC_TIMEZONE)
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pacific)

def format_datetime(dt, fmt='%Y-%m-%d %I:%M %p'):
    """
    Converts a datetime object to a formatted string in Pacific Time.
    """
    dt_pacific = to_pacific(dt)
    return dt_pacific.strftime(fmt)

def is_all_day(event):
    """
    Determines if an event is an all‑day event.
    Here, we assume that if the datetime string does not include a 'T', it's an all‑day event.
    """
    return 'T' not in event
