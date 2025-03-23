from flask import Flask, request, redirect, url_for
from app.sync import build_html_email  # if used for sending emails
from app.schedule import build_schedule_html
from app.attendees_db import mark_attendee_ok_to_ignore
from datetime import date

app = Flask(__name__)

@app.route("/")
def index():
    # Render the schedule webpage using today's date.
    today = date.today()
    html = build_schedule_html(today)
    return html

@app.route("/ignore_attendee")
def ignore_attendee():
    email = request.args.get("email")
    if email:
        mark_attendee_ok_to_ignore(email)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
