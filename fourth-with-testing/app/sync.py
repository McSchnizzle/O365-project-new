"""Sync module.
Handles calendar synchronization and email summary building.
"""

import os
import sqlite3
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import (SQLITE_DB_FILE, DELTA_LINK_FILE, GRAPH_DELTA_ENDPOINT, 
                        FUTURE_WINDOW_DAYS, SYNC_SCOPES, MAIL_SCOPES)
from app.auth import get_token
from app.database import init_db, upsert_event
from app.utils import parse_iso_time, convert_to_pacific, get_event_start_dt, should_ignore_event
from app.attendees_db import init_attendee_db, update_attendees_with_event, get_attendee_summary

# Global cache for series master subjects.
series_master_cache = {}

def get_series_master_subject(series_master_id):
    global series_master_cache
    if series_master_id in series_master_cache:
        return series_master_cache[series_master_id]
    token = get_token(SYNC_SCOPES)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.microsoft.com/v1.0/me/events/{series_master_id}?$select=subject"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        subject = data.get("subject", "").strip()
        series_master_cache[series_master_id] = subject
        return subject
    else:
        print("Failed to fetch series master event", series_master_id, response.status_code, response.text)
        series_master_cache[series_master_id] = ""
        return ""

def get_conflict_groups(events):
    groups = []
    current_group = []
    current_end = None
    for event in events:
        if event.get("isAllDay", False):
            continue
        end_str = event.get("end", {}).get("dateTime")
        if not end_str:
            continue
        try:
            end_dt = parse_iso_time(end_str).astimezone(ZoneInfo("America/Los_Angeles"))
        except Exception:
            end_dt = event.get("_start_pacific")
        if not current_group:
            current_group = [event]
            current_end = end_dt
        else:
            if event["_start_pacific"] < current_end:
                current_group.append(event)
                if end_dt > current_end:
                    current_end = end_dt
            else:
                if len(current_group) > 1:
                    groups.append(current_group)
                current_group = [event]
                current_end = end_dt
    if current_group and len(current_group) > 1:
        groups.append(current_group)
    return groups

def format_time(dt: datetime) -> str:
    formatted = dt.strftime("%I:%M %p")
    return formatted.lstrip("0") if formatted.startswith("0") else formatted

def sync_calendar():
    init_db()
    init_attendee_db()
    token = get_token(SYNC_SCOPES)
    headers = {
        "Authorization": f"Bearer {token}",
        "Prefer": 'outlook.timezone="Pacific Standard Time"'
    }
    if os.path.exists(DELTA_LINK_FILE):
        with open(DELTA_LINK_FILE, "r") as f:
            url = f.read().strip()
        print("Using stored deltaLink for incremental sync.")
    else:
        print("No deltaLink found; performing full sync.")
        start_date = datetime.now(ZoneInfo("UTC")) - timedelta(days=365)
        end_date = datetime.now(ZoneInfo("UTC")) + timedelta(days=FUTURE_WINDOW_DAYS)
        start_str = start_date.isoformat(timespec='seconds').replace('+00:00', 'Z')
        end_str = end_date.isoformat(timespec='seconds').replace('+00:00', 'Z')
        url = f"{GRAPH_DELTA_ENDPOINT}?$select=subject,start,end,location,attendees,isAllDay,organizer,seriesMasterId&startDateTime={start_str}&endDateTime={end_str}"
    
    total_events = 0
    while url:
        print("Requesting:", url)
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print("Error during sync:", response.status_code, response.text)
            return
        data = response.json()
        events = data.get("value", [])
        print(f"Retrieved {len(events)} events in this batch.")
        for event in events:
            if should_ignore_event(event):
                continue
            upsert_event(event)
            update_attendees_with_event(event)
            total_events += 1
        if "@odata.nextLink" in data:
            url = data["@odata.nextLink"]
        elif "@odata.deltaLink" in data:
            delta_link = data["@odata.deltaLink"]
            with open(DELTA_LINK_FILE, "w") as f:
                f.write(delta_link)
            print("Delta sync complete. DeltaLink updated.")
            url = None
        else:
            url = None
    print(f"Sync complete. Total events processed: {total_events}")

def get_today_events():
    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT raw_json FROM events WHERE raw_json IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    events = [json.loads(row[0]) for row in rows]
    events = [e for e in events if not should_ignore_event(e)]
    now_pacific = datetime.now(ZoneInfo("America/Los_Angeles"))
    today_midnight = now_pacific.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_midnight = today_midnight + timedelta(days=1)
    filtered = []
    for event in events:
        start_dt = get_event_start_dt(event)
        if not start_dt:
            continue
        start_pacific = start_dt.astimezone(ZoneInfo("America/Los_Angeles"))
        if today_midnight <= start_pacific < tomorrow_midnight:
            event["_start_pacific"] = start_pacific
            filtered.append(event)
    filtered.sort(key=lambda e: e["_start_pacific"])
    return filtered

def build_html_email(events):
    html = "<html><body>"
    html += "<h2>Today's Meetings</h2>"
    html += "<table border='1' cellspacing='0' cellpadding='5'>"
    html += "<tr><th>Time</th><th>Location</th><th>Subject</th></tr>"
    for event in events:
        start_info = event.get("start", {})
        if "date" in start_info:
            time_range = "All Day"
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

    # Attendee Summary: only top 5.
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

    # Stale Contacts for email (without action links)
    stale_list = []
    for row in attendee_summary:
        email, name, first_meeting, last_meeting, next_meeting, last_meeting_subject, times_met, ok_to_ignore, source = row
        try:
            dt = datetime.fromisoformat(last_meeting)
            stale_list.append((dt, name, email))
        except Exception:
            continue
    stale_list.sort(key=lambda x: x[0])
    stale_list = stale_list[:10]
    if stale_list:
        html += "<h2>Stale Contacts (Top 10)</h2>"
        html += "<table border='1' cellspacing='0' cellpadding='5'><tr><th>Name</th><th>Email</th><th>Last Meeting</th></tr>"
        for dt, name, email in stale_list:
            try:
                lm = dt.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%m/%d/%Y %I:%M %p")
            except Exception:
                lm = dt.isoformat()
            html += f"<tr><td>{name}</td><td>{email}</td><td>{lm}</td></tr>"
        html += "</table>"
    else:
        html += "<h2>No stale contacts available.</h2>"

    html += "</body></html>"
    return html

def send_email_via_graph(html_content):
    token = get_token(MAIL_SCOPES)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    message = {
        "message": {
            "subject": "Daily Calendar Summary",
            "body": {
                "contentType": "HTML",
                "content": html_content
            },
            "toRecipients": [
                {"emailAddress": {"address": "paul@teamcinder.com"}}
            ]
        },
        "saveToSentItems": "true"
    }
    response = requests.post("https://graph.microsoft.com/v1.0/me/sendMail", headers=headers, json=message)
    if response.status_code in (200, 202):
        print("Email sent successfully via Graph API.")
    else:
        print("Failed to send email:", response.status_code, response.text)

def main():
    print("Starting daily sync and email process...")
    sync_calendar()
    today_events = get_today_events()
    
    # Debug output: count events in the calendar database.
    conn = sqlite3.connect(SQLITE_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events")
    total_events = cursor.fetchone()[0]
    conn.close()
    print(f"Total events in calendar db: {total_events}")
    
    html_content = build_html_email(today_events)
    send_email_via_graph(html_content)

if __name__ == "__main__":
    main()
