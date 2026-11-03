"""SQLite databases (WAL) with numbered migrations and a backup before each upgrade (SPEC §4.2)."""
import sqlite3
from pathlib import Path


class StoreError(RuntimeError):
    pass


def open_db(path: Path, migrations: list[str]) -> sqlite3.Connection:
    """Open `path` and apply `migrations[current:]`; migrations[i] brings the schema to version i+1."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    con = sqlite3.connect(path, isolation_level=None)  # explicit transactions below
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    version = con.execute("PRAGMA user_version").fetchone()[0]
    target = len(migrations)
    if version > target:
        con.close()
        raise StoreError(f"{path.name} has schema v{version}, this engine knows only v{target}")
    if version < target:
        if existed and version > 0:
            backup = sqlite3.connect(path.with_name(f"{path.name}.v{version}.bak"))
            con.backup(backup)
            backup.close()
        try:
            con.execute("BEGIN IMMEDIATE")
            for statement in migrations[version:]:
                con.execute(statement)
            con.execute(f"PRAGMA user_version={target:d}")
            con.execute("COMMIT")
        except sqlite3.Error:
            con.execute("ROLLBACK")
            con.close()
            raise
    con.isolation_level = ""  # back to Python's default transaction handling for callers
    return con
