import sqlite3

import pytest

from dt3agent import store

V1 = ["CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"]
V2 = V1 + ["ALTER TABLE item ADD COLUMN note TEXT"]


def test_new_database_uses_wal_and_foreign_keys(tmp_path):
    con = store.open_db(tmp_path / "q.db", V1)
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert con.execute("PRAGMA user_version").fetchone()[0] == 1


def test_migration_backs_up_and_upgrades(tmp_path):
    path = tmp_path / "q.db"
    con = store.open_db(path, V1)
    con.execute("INSERT INTO item (name) VALUES ('a')")
    con.commit()
    con.close()
    con = store.open_db(path, V2)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 2
    assert con.execute("SELECT name, note FROM item").fetchall() == [("a", None)]
    backup = sqlite3.connect(tmp_path / "q.db.v1.bak")
    assert backup.execute("SELECT name FROM item").fetchall() == [("a",)]


def test_failed_migration_leaves_database_unchanged(tmp_path):
    path = tmp_path / "q.db"
    store.open_db(path, V1).close()
    with pytest.raises(sqlite3.Error):
        store.open_db(path, V1 + ["THIS IS NOT SQL"])
    con = store.open_db(path, V1)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 1


def test_newer_database_than_code_is_refused(tmp_path):
    path = tmp_path / "q.db"
    store.open_db(path, V2).close()
    with pytest.raises(store.StoreError):
        store.open_db(path, V1)
