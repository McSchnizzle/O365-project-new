"""Package initializer for the app.
Creates the Flask application using the app factory pattern and includes the schedule view.
"""

import logging
from flask import Flask, request
from datetime import datetime
from .config import Config
from .schedule import build_schedule_html

logger = logging.getLogger(__name__)

def create_app() -> Flask:
    """
    Application factory that creates and configures the Flask app.
    The index route displays a calendar view based on a selected date.
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.route("/")
    def index() -> str:
        # Read an optional 'date' query parameter in YYYY-MM-DD format.
        date_str = request.args.get('date')
        if date_str:
            try:
                selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning("Invalid date format provided: %s; defaulting to today's date.", date_str)
                selected_date = datetime.now().date()
        else:
            selected_date = datetime.now().date()

        html_content = build_schedule_html(selected_date)
        return html_content

    return app
