"""Retention classes (brief B4, SPEC §4.16): how long the user wants to keep a document type.

A user-editable table in config.json ("retention.classes": doc type -> years + basis). The engine only writes a
hint into custom metadata; it never deletes, moves or expires anything. The default table is an example:
accounting records 10 years, OR Art. 958f (SR 220; the period starts at the end of the business year).
The business year is assumed to be the calendar year; the user edits the table if theirs differs.
"""
from datetime import date

NOTE = "Hinweis, Keine Rechtsberatung"


def keep_until(document_date: date, years: int) -> date:
    """End of the year of the document plus `years` (OR Art. 958f: from the end of the business year)."""
    return date(document_date.year + years, 12, 31)
