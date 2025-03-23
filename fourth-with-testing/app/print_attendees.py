# app/print_attendees.py
"""
Script to print attendee records to the console.
"""

from app.attendees_db import get_attendee_summary

def main() -> None:
    summary = get_attendee_summary()
    if not summary:
        print("No attendee records found.")
        return

    # Print header
    header = "{:<30} {:<30} {:<25} {:<25} {:<50}".format(
        "Email", "Name", "Last Meeting", "Next Meeting", "Last Meeting Subject"
    )
    print(header)
    print("-" * len(header))
    
    # Print each attendee record.
    for row in summary:
        email, name, last_meeting, next_meeting, last_meeting_subject, *_ = row
        print("{:<30} {:<30} {:<25} {:<25} {:<50}".format(
            email,
            name,
            last_meeting or "",
            next_meeting or "",
            last_meeting_subject or ""
        ))

if __name__ == "__main__":
    main()
