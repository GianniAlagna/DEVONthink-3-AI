"""One all-day calendar event as iCalendar text (RFC 5545) for a stated deadline (brief B5).

DT3 imports the .ics next to the document; a double-click hands it to the macOS Calendar. Lines end with
CR LF and are folded at 75 octets (RFC 5545 §3.1); TEXT values escape \\ ; , and newlines (§3.3.11).
"""
from datetime import date, timedelta


def _text(value: str) -> str:
    if any(ord(c) < 32 and c != "\n" for c in value):
        raise ValueError("control characters")
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    out, cur = [], ""
    for ch in line:
        limit = 75 if not out else 74  # continuation lines start with one space
        if len((cur + ch).encode()) > limit:
            out.append(cur)
            cur = ch
        else:
            cur += ch
    out.append(cur)
    return [out[0]] + [" " + x for x in out[1:]]


def build_event(*, uid: str, when: date, title: str, notes: str, url: str, stamp: str) -> str:
    """stamp: DTSTAMP in UTC, e.g. 20261105T090000Z. Reminder: one day before (VALARM -P1D)."""
    if not title.strip():
        raise ValueError("empty title")
    description = "\n".join(x for x in (notes.strip(), url) if x)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//DT3 Agent//Deadline//DE", "CALSCALE:GREGORIAN",
             "BEGIN:VEVENT", f"UID:{_text(uid)}@dt3agent", f"DTSTAMP:{stamp}",
             f"DTSTART;VALUE=DATE:{when:%Y%m%d}", f"DTEND;VALUE=DATE:{when + timedelta(days=1):%Y%m%d}",
             f"SUMMARY:{_text(title)}", f"DESCRIPTION:{_text(description)}"]
    if url:
        lines.append(f"URL:{url}")
    lines += ["TRANSP:TRANSPARENT", "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_text(title)}",
              "TRIGGER:-P1D", "END:VALARM", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(part for line in lines for part in _fold(line)) + "\r\n"
