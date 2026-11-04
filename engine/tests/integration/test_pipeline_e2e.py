"""End to end with fakes (T8): spool file → queue → pipeline → llama-server (fake) → tag → undo."""
import json
from datetime import UTC, datetime

from dt3agent import queue as queuemod
from dt3agent import store
from dt3agent.adapter import DT3Adapter
from dt3agent.ai import LlamaClient
from dt3agent.audit import AuditLog
from dt3agent.intake import ingest_spool
from dt3agent.pipeline import MIGRATIONS, Pipeline
from dt3agent.undo import MIGRATIONS as UNDO_MIGRATIONS
from dt3agent.undo import UndoJournal
from tests.fakes import FakeDT3, FakeLlamaServer

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"


def test_spool_to_tag_to_undo(tmp_path):
    dt3 = FakeDT3({A: {"name": "SECRET-NAME", "tags": [], "contentHash": "h1", "text": "Rechnung Nr. 4711"}})
    server = FakeLlamaServer(reply=json.dumps({"tags": ["Invoice"]}))
    try:
        con = store.open_db(tmp_path / "engine.db", queuemod.MIGRATIONS + MIGRATIONS)
        q = queuemod.Queue(con, lambda: datetime(2026, 11, 4, tzinfo=UTC))
        spool = tmp_path / "spool"
        spool.mkdir()
        (spool / f"{A}.json").write_text(json.dumps({"uuid": A}))
        assert ingest_spool(spool, q, "spool", min_age=0) == 1
        adapter = DT3Adapter(dt3, UndoJournal(store.open_db(tmp_path / "undo.db", UNDO_MIGRATIONS)),
                             AuditLog(tmp_path / "audit"))
        p = Pipeline(adapter, LlamaClient(server.url, context=4096), con, dry_run=False, vocabulary=["invoice"])
        assert p.run_once(q) == "applied"
        assert dt3.records[A]["tags"] == ["invoice"] and q.counts() == {"done": 1}
        assert "Rechnung Nr. 4711" in server.requests[0]["body"]["messages"][-1]["content"]
        assert adapter.undo_last_batch() == {"restored": 1, "conflicts": []}
        assert dt3.records[A]["tags"] == []
        logs = "".join(f.read_text() for f in (tmp_path / "audit").glob("*.jsonl"))
        assert "SECRET-NAME" not in logs and "Rechnung" not in logs
    finally:
        server.close()
