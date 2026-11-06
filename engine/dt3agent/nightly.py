"""J-3 nightly incremental (SPEC §4.21 D1): records changed since the last night go to the queue.

Read-only towards DT3: it only lists. The first night only records the newest change as the watermark, so
existing records are not queued in bulk (they come through the Smart Rule or the menu). Unchanged content is
skipped by the pipeline as before. More than 500 changes in one scope in one night: the newest 500 are queued
and the result is `capped`, so the status shows it.
"""
from dt3agent.bridge import BridgeError

LIST_MAX = 500


def run(adapter, queue, scopes: list[dict]) -> str:
    if not scopes:
        return "no_scopes"
    result = "ok"
    for scope in scopes:
        database, group = scope["database"], scope["group"]
        since = queue.pull_since(database, group)
        try:
            records = adapter.list_scope(database, group, since or "")
        except BridgeError as e:
            if result == "ok":
                result = str(e) if str(e).isidentifier() and len(str(e)) <= 40 else "list_failed"
            continue
        if since is not None:
            for r in records:
                queue.enqueue(r["uuid"], "pull")
            if len(records) >= LIST_MAX and result == "ok":
                result = "capped"
        newest = max((r["modified"] for r in records if r["modified"]), default=None)
        if newest and newest != since:
            queue.set_pull_since(database, group, newest)
        elif since is None:
            queue.set_pull_since(database, group, "")
    return result
