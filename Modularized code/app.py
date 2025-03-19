from flask import Flask
from sync_email import get_today_events, build_html_email, sync_calendar

app = Flask(__name__)

@app.route("/")
def index():
    # Optionally, you can sync the calendar before generating the page.
    # Be cautious: if your sync takes too long, you might want to run it periodically instead.
    sync_calendar()
    events = get_today_events()
    html_content = build_html_email(events)
    return html_content

if __name__ == "__main__":
    # Run the Flask app on http://127.0.0.1:5000/
    app.run(debug=True)
