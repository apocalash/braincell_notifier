"""
Date parsing module.
Parses user-supplied date strings with flexible formats.
"""
from datetime import datetime
from dateutil import parser as dateutil_parser


def parse_user_date(raw_text: str) -> datetime | None:
    """
    Parse user-supplied date strings.
    Accepts: DD-MM-YYYY or DD/MM/YYYY.
    Returns a datetime object or None if unparseable.
    Uses dayfirst=True to force DD-MM interpretation.

    Args:
        raw_text: The date string from the user

    Returns:
        datetime object or None if parsing fails
    """
    normalized = raw_text.strip().replace("/", "-")
    try:
        return dateutil_parser.parse(normalized, dayfirst=True)
    except (ValueError, OverflowError):
        return None
