"""
Command-line entry point for running synchronization and initialization tasks.
"""

import os
import sys
import logging
from app.config import Config

from app.sync import sync_calendar, get_today_events, build_html_email
from app.email_sender import send_email_via_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize() -> None:
    """
    Delete existing database and delta link files to reinitialize the project.
    """
    files_to_delete = [Config.SQLITE_DB_FILE, Config.ATTENDEE_DB_FILE, Config.DELTA_LINK_FILE]
    for f in files_to_delete:
        if os.path.exists(f):
            os.remove(f)
            logger.info("Deleted %s", f)
        else:
            logger.info("%s not found.", f)
    logger.info("Initialization complete. Databases and delta_link will be recreated on next sync.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "initialize":
        initialize()
    else:
        logger.info("Starting daily sync and email process...")
        sync_calendar()
        today_events = get_today_events()
        logger.info("Building HTML email from %d events", len(today_events))
        html_content = build_html_email(today_events)
        send_email_via_graph(html_content)
