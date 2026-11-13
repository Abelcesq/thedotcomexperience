"""Turning a Dot's meeting night and time (typed by staff) into real dates and times."""
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_weekday(text):
    """"Tuesday", "Tues", "tuesday nights" -> 1 (Monday is 0). None if it can't be read."""
    word = re.sub(r"[^a-z]", " ", (text or "").lower()).split()
    for token in word:
        for index, name in enumerate(WEEKDAYS):
            if len(token) >= 3 and name.startswith(token.rstrip("s")[:len(name)]):
                return index
    return None


def parse_time(text):
    """"7:00 PM", "7pm", "7:30 p.m.", "19:00" -> a time. None if it can't be read."""
    s = (text or "").strip().lower().replace(".", "")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
    if not m:
        return None
    hour, minute, half = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if minute > 59:
        return None
    if half:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if half == "pm" else 0)
    elif hour > 23:
        return None
    return time(hour, minute)


def next_meeting(weekday, clock, tz_name, now):
    """The next meeting start at or after `now`, as an aware datetime in the Dot's time zone."""
    tz = ZoneInfo(tz_name)
    local_now = now.astimezone(tz)
    for days_ahead in range(0, 8):
        day = local_now.date() + timedelta(days=days_ahead)
        if day.weekday() != weekday:
            continue
        start = datetime.combine(day, clock, tzinfo=tz)
        if start > local_now:
            return start
    return None


def reminder_time(start, hours_before, quiet_start=8, quiet_end=21):
    """When to text about a meeting: `hours_before` ahead, but never during quiet hours.

    Texts go out only between 8am and 9pm in the Dot's time zone. A reminder that would land
    earlier waits until 8am; for a meeting earlier than that, it goes out at 6pm the evening before.
    """
    send_at = start - timedelta(hours=hours_before)
    day_open = start.replace(hour=quiet_start, minute=0, second=0, microsecond=0)
    day_close = start.replace(hour=quiet_end, minute=0, second=0, microsecond=0)
    if send_at < day_open:
        send_at = day_open
    if send_at >= start:                      # the meeting itself is before 8am
        send_at = (start - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    if send_at > day_close and send_at.date() == start.date():
        send_at = day_close
    return send_at
