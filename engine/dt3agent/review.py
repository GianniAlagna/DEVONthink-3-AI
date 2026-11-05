"""Review queue: proposals the engine does not apply on its own, and the user's decisions (SPEC §4.12).

Decisions: accept (apply the proposal), edit (apply the user's value), reject (apply nothing).
Every decision is audited (codes and field names only). Applying is done by the caller through the
DT3 adapter, so it gets the undo journal like every other write.
"""
import json
import sqlite3
from datetime import UTC, datetime

KINDS = ("planned", "error", "field", "duplicate", "case", "deadline", "urgent")
# Widens review_items (Phase 2) with the SPEC §4.12 kinds and the decision columns. Append-only migrations.
MIGRATIONS = [
    f"""CREATE TABLE review_items_v2 (
        id INTEGER PRIMARY KEY,
        uuid TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN {KINDS}),
        code TEXT,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        decided_at TEXT,
        decision TEXT CHECK (decision IN ('accept', 'edit', 'reject')),
        value_json TEXT)""",
    "INSERT INTO review_items_v2 (id, uuid, kind, code, payload_json, created_at, decided_at) "
    "SELECT id, uuid, kind, code, payload_json, created_at, decided_at FROM review_items",
    "DROP TABLE review_items",
    "ALTER TABLE review_items_v2 RENAME TO review_items",
]
# B-0: the record behind an item can disappear in DT3 (deleted, emptied trash). Separate list: append only.
MIGRATIONS_2 = ["ALTER TABLE review_items ADD COLUMN record_missing INTEGER NOT NULL DEFAULT 0"]


class ReviewError(ValueError):
    pass


def decide(con: sqlite3.Connection, item_id: int, decision: str, value=None) -> dict:
    """Record a decision on an open item. Returns {uuid, kind, payload, apply} where apply is what to write
    (None for reject or for items without a proposal)."""
    if decision not in ("accept", "edit", "reject"):
        raise ReviewError("bad_decision")
    row = con.execute("SELECT uuid, kind, payload_json, record_missing FROM review_items "
                      "WHERE id = ? AND decided_at IS NULL", (item_id,)).fetchone()
    if row is None:
        raise ReviewError("no_open_item")
    if row[3] and decision != "reject":
        raise ReviewError("record_missing")  # nothing to apply to: only closing the item is possible
    uuid, kind, payload = row[0], row[1], json.loads(row[2])
    if decision == "edit" and value is None:
        raise ReviewError("edit_needs_value")
    proposal = payload.get("after", payload.get("tags_add"))
    apply = None if decision == "reject" else (value if decision == "edit" else proposal)
    with con:
        con.execute("UPDATE review_items SET decided_at = ?, decision = ?, value_json = ? WHERE id = ?",
                    (datetime.now(UTC).isoformat(), decision, json.dumps(apply), item_id))
    return {"uuid": uuid, "kind": kind, "payload": payload, "apply": apply, "decision": decision}


def reopen(con: sqlite3.Connection, item_id: int) -> None:
    """Undo a recorded decision whose write failed, so the item stays in the review list."""
    with con:
        con.execute("UPDATE review_items SET decided_at = NULL, decision = NULL, value_json = NULL WHERE id = ?",
                    (item_id,))


def set_missing(con: sqlite3.Connection, item_id: int, missing: bool) -> None:
    with con:
        con.execute("UPDATE review_items SET record_missing = ? WHERE id = ?", (int(missing), item_id))
