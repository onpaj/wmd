"""On-disk store for calendars pushed to the dashboard as .ics files.

Some calendars have no usable published feed (the 8am.com work calendar only
publishes free/busy). For those, an .ics export is uploaded via
``PUT /api/calendars/{name}/ics`` and read from here instead of the URL.
"""

import os
import re
import tempfile

from icalendar import Calendar


class InvalidCalendarUpload(ValueError):
    """The uploaded bytes are not a parseable iCalendar file."""


def _upload_path(upload_dir: str, calendar_name: str) -> str:
    # Calendar names come from config, but never let them steer the path.
    slug = re.sub(r"[^a-z0-9]+", "-", calendar_name.lower()).strip("-") or "calendar"
    return os.path.join(upload_dir, f"{slug}.ics")


def count_events(content: bytes) -> int:
    """Parse ``content`` and return its VEVENT count, or raise InvalidCalendarUpload."""
    if not content.strip():
        raise InvalidCalendarUpload("empty file")
    try:
        cal = Calendar.from_ical(content)
    except ValueError as exc:
        raise InvalidCalendarUpload(f"not an iCalendar file: {exc}") from exc
    if cal.name != "VCALENDAR":
        raise InvalidCalendarUpload("missing VCALENDAR")
    return sum(1 for c in cal.walk() if c.name == "VEVENT")


def save_upload(upload_dir: str, calendar_name: str, content: bytes) -> int:
    """Validate and atomically store an upload. Returns its VEVENT count."""
    event_count = count_events(content)
    os.makedirs(upload_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=upload_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.replace(tmp_path, _upload_path(upload_dir, calendar_name))
    except BaseException:
        os.unlink(tmp_path)
        raise
    return event_count


def read_upload(upload_dir: str, calendar_name: str) -> bytes | None:
    """Return the stored upload for a calendar, or None if none was uploaded."""
    try:
        with open(_upload_path(upload_dir, calendar_name), "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None
