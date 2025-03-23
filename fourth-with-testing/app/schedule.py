"""Schedule module.
Provides functions to fetch events for a specific date and to build the HTML page for the website.
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta, time, date
from zoneinfo import ZoneInfo
from typing import List
from app.config import Config
from app.utils import parse_iso_time, get_event_start_dt, convert_to_pacific

def format_time(dt: datetime) -> str:
    formatted = dt.strftime("%I:%M %p")
    return formatted.lstrip("0") if formatted.startswith("0") else formatted

def get_events_for_date(selected_date: date) -> List[dict]:
    events = []
    SQLITE_DB_FILE = Config.SQLITE_DB_FILE
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT raw_json FROM events WHERE raw_json IS NOT NULL")
        rows = cursor.fetchall()
    for row in rows:
        try:
            event = json.loads(row[0])
            start_dt = get_event_start_dt(event)
            if start_dt is None:
                continue
            local_start = start_dt.astimezone(ZoneInfo("America/Los_Angeles"))
            end_obj = event.get("end", {})
            if "dateTime" in end_obj:
                end_dt = parse_iso_time(end_obj["dateTime"])
            elif "date" in end_obj:
                end_dt = datetime.fromisoformat(end_obj["date"] + "T00:00:00+00:00")
            else:
                end_dt = start_dt
            local_end = end_dt.astimezone(ZoneInfo("America/Los_Angeles"))
            if local_start.date() <= selected_date <= local_end.date():
                event["_start_pacific"] = local_start
                event["_end_pacific"] = local_end
                events.append(event)
        except Exception:
            continue
    return events

def get_open_happy_hours() -> List[date]:
    open_dates = []
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    end_date = today + timedelta(weeks=3)
    SQLITE_DB_FILE = Config.SQLITE_DB_FILE
    events = []
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT raw_json FROM events WHERE raw_json IS NOT NULL")
        rows = cursor.fetchall()
    for row in rows:
        try:
            event = json.loads(row[0])
            start_dt = get_event_start_dt(event)
            if start_dt is None:
                continue
            local_dt = start_dt.astimezone(ZoneInfo("America/Los_Angeles"))
            if today <= local_dt.date() <= end_date:
                event["_start_pacific"] = local_dt
                events.append(event)
        except Exception:
            continue
    current_date = today
    while current_date <= end_date:
        if current_date.weekday() < 5:
            window_start = datetime.combine(current_date, time(16, 0), tzinfo=ZoneInfo("America/Los_Angeles"))
            window_end = datetime.combine(current_date, time(18, 0), tzinfo=ZoneInfo("America/Los_Angeles"))
            if not any(window_start <= e["_start_pacific"] < window_end for e in events):
                open_dates.append(current_date)
        current_date += timedelta(days=1)
    return open_dates

def build_schedule_html(selected_date: date) -> str:
    try:
        today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
        html = "<html><body>"
        html += f"<h1>Calendar for {selected_date.strftime('%A, %B %d, %Y')}</h1>"
        html += "<form method='get'>Select Date: <input type='date' name='date' value='" + selected_date.isoformat() + "' />"
        html += "<input type='submit' value='Go' /></form>"

        open_dates = get_open_happy_hours()
        if open_dates:
            html += "<h2>Open Happy Hours (Next 3 Weeks)</h2><ul>"
            for d in open_dates:
                html += f"<li>{d.strftime('%A, %B %d, %Y')}</li>"
            html += "</ul>"
        else:
            html += "<h2>No open happy hours found in the next 3 weeks.</h2>"

        events = get_events_for_date(selected_date)
        if events:
            html += "<h2>Events for the Day</h2>"
            html += "<table border='1' cellspacing='0' cellpadding='5'><tr><th>Time</th><th>Location</th><th>Subject</th></tr>"
            for event in events:
                start_info = event.get("start", {})
                if "date" in start_info:
                    time_range = "All Day"
                else:
                    local_start = event.get("_start_pacific")
                    local_end = event.get("_end_pacific")
                    if local_start and local_end and local_start.date() != local_end.date():
                        time_range = "All Day / Multi-Day Event"
                    else:
                        start = start_info.get("dateTime", "TBD")
                        end = event.get("end", {}).get("dateTime", "TBD")
                        formatted_start = convert_to_pacific(start) if start != "TBD" else "TBD"
                        formatted_end = convert_to_pacific(end) if end != "TBD" else "TBD"
                        time_range = f"{formatted_start} - {formatted_end}" if formatted_start != "TBD" and formatted_end != "TBD" else "TBD"
                subject = event.get("subject", "").strip() or "(No Subject)"
                location = event.get("location", {}).get("displayName", "")
                html += f"<tr><td>{time_range}</td><td>{location}</td><td>{subject}</td></tr>"
            html += "</table>"
        else:
            day_name = selected_date.strftime("%A")
            html += f"<h1>Congratulations, you have a free {day_name}!</h1>"

        if events:
            from app.sync import get_conflict_groups, format_time, parse_iso_time
            conflict_groups = get_conflict_groups(events)
            if conflict_groups:
                html += "<h2>Meeting Conflicts</h2>"
                html += "<table border='1' cellspacing='0' cellpadding='5'><tr><th>Time Slot</th><th>Meetings</th></tr>"
                for group in conflict_groups:
                    group_starts = [e["_start_pacific"] for e in group if "_start_pacific" in e]
                    group_ends = []
                    for e in group:
                        end_str = e.get("end", {}).get("dateTime")
                        try:
                            end_dt = parse_iso_time(end_str).astimezone(ZoneInfo("America/Los_Angeles"))
                        except Exception:
                            end_dt = e.get("_start_pacific")
                        if end_dt:
                            group_ends.append(end_dt)
                    if group_starts and group_ends:
                        slot_start = min(group_starts)
                        slot_end = max(group_ends)
                        time_slot = f"{format_time(slot_start)} - {format_time(slot_end)}"
                        meetings_details = "<br>".join(
                            f"{e.get('subject', '').strip() or '(No Subject)'} (Organizer: {e.get('organizer', {}).get('emailAddress', {}).get('name', 'Unknown')})"
                            for e in group)
                        html += f"<tr><td>{time_slot}</td><td>{meetings_details}</td></tr>"
                html += "</table>"
        # Attendee Summary (Top 5) for website.
        from app.attendees_db import get_attendee_summary
        attendee_summary = get_attendee_summary()
        if attendee_summary:
            sorted_attendees = sorted(attendee_summary, key=lambda row: row[6] if row[6] is not None else 0, reverse=True)[:5]
            html += "<h2>Attendee Summary (Top 5)</h2>"
            html += ("<table border='1' cellspacing='0' cellpadding='5'>"
                     "<tr><th>Name</th><th>Email</th><th>First Meeting</th><th>Last Meeting</th>"
                     "<th>Next Meeting</th><th>Last Meeting Subject</th><th>Times Met</th><th>Ok To Ignore</th><th>Source</th></tr>")
            for row in sorted_attendees:
                email, name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, ok_to_ignore, source = row
                try:
                    fm = datetime.fromisoformat(first_meeting).astimezone(ZoneInfo("America/Los_Angeles")).strftime("%m/%d/%Y %I:%M %p")
                except Exception:
                    fm = first_meeting or ""
                try:
                    lm = datetime.fromisoformat(last_meeting).astimezone(ZoneInfo("America/Los_Angeles")).strftime("%m/%d/%Y %I:%M %p")
                except Exception:
                    lm = last_meeting or ""
                try:
                    nm = datetime.fromisoformat(next_meeting).astimezone(ZoneInfo("America/Los_Angeles")).strftime("%m/%d/%Y %I:%M %p")
                except Exception:
                    nm = next_meeting or ""
                html += f"<tr><td>{name}</td><td>{email}</td><td>{fm}</td><td>{lm}</td><td>{nm}</td><td>{last_meeting_subject}</td><td>{times_met}</td><td>{ok_to_ignore}</td><td>{source}</td></tr>"
            html += "</table>"
        else:
            html += "<h2>No attendee summary available.</h2>"

        # Stale Contacts for website include an action link.
        stale_list = []
        for row in attendee_summary:
            email, name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, ok_to_ignore, source = row
            if last_meeting and ok_to_ignore.lower() != "yes":
                try:
                    dt = datetime.fromisoformat(last_meeting)
                    stale_list.append((dt, name, email))
                except Exception:
                    continue
        stale_list.sort(key=lambda x: x[0])
        stale_list = stale_list[:10]
        if stale_list:
            html += "<h2>Stale Contacts (Top 10 - Click 'ok to ignore?' to mark)</h2>"
            html += "<table border='1' cellspacing='0' cellpadding='5'><tr><th>Name</th><th>Email</th><th>Last Meeting</th><th>Action</th></tr>"
            for dt, name, email in stale_list:
                try:
                    lm = dt.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%m/%d/%Y %I:%M %p")
                except Exception:
                    lm = dt.isoformat()
                html += f"<tr><td>{name}</td><td>{email}</td><td>{lm}</td><td><a href='/ignore_attendee?email={email}'>ok to ignore?</a></td></tr>"
            html += "</table>"
        else:
            html += "<h2>No stale contacts available.</h2>"

        html += "</body></html>"
        return html
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Error building schedule HTML: %s", e)
        return "<html><body><h1>Error building schedule.</h1></body></html>"
