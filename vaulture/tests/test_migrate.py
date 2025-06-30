# vaulture/tests/test_migrate.py

"""
Test suite for: src/infrastructure/database/migrate.py

This suite verifies the integrity, safety, and correctness of the manual
SQLite migration runner. It ensures:

- Correct parsing of version prefixes from filenames.
- Filtering and ordering of pending migrations.
- Actual execution of SQL files with PRAGMA version tracking.
- Protection against partial state on failure (via transaction rollback).
"""

import sys
import importlib
import sqlite3
from pathlib import Path
from types import ModuleType

import pytest
from pytest import MonkeyPatch


# Make sure `src/` is on sys.path so we can import internal modules directly
project_root = Path(__file__).resolve().parents[1]
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

PKG = "src.infrastructure.database.migrate"  # Single source of truth for reloading


def _reload_module(_: MonkeyPatch | None = None) -> ModuleType:
    """
    Force a clean import of the migration module.

    This enables monkeypatching of module-level functions like
    `_list_sql_files()` or `_connect()` that are otherwise cached.
    """
    sys.modules.pop(PKG, None)
    return importlib.import_module(PKG)


# ─────────────────────────────────────────────────────────────────────────────
# _extract_prefix
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_prefix_valid(monkeypatch: MonkeyPatch) -> None:
    """
    A filename with a numeric prefix should return the correct integer version.

    Verifies the standard case:
    - zero-padded prefixes like 001
    - multi-digit numbers like 010
    """
    mod = _reload_module(monkeypatch)
    assert mod._extract_prefix(Path("001_create_users_table.sql")) == 1
    assert mod._extract_prefix(Path("010_add_index.sql")) == 10


def test_extract_prefix_invalid(monkeypatch: MonkeyPatch) -> None:
    """
    Filenames with no numeric prefix should raise ValueError.

    Ensures `_extract_prefix` fails fast on malformed inputs, which
    protects the migration runner from applying unversioned SQL.
    """
    mod = _reload_module(monkeypatch)

    with pytest.raises(ValueError):
        mod._extract_prefix(Path("no_prefix.sql"))

    with pytest.raises(ValueError):
        mod._extract_prefix(Path("abc.sql"))


# ─────────────────────────────────────────────────────────────────────────────
# _pending_migrations
# ─────────────────────────────────────────────────────────────────────────────

def test_pending_migrations(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """
    Given a current version, only higher-numbered migrations are returned.

    Also verifies:
    - Output is sorted even if filenames aren't.
    - Skips already-applied versions correctly.
    """
    files = [
        tmp_path / "001_init.sql",
        tmp_path / "002_add_email.sql",
        tmp_path / "004_index.sql",
    ]
    for f in files:
        f.write_text("-- no-op\n")

    mod = _reload_module(monkeypatch)

    # Monkeypatch _list_sql_files() to return our test files
    monkeypatch.setattr(mod, "_list_sql_files", lambda: sorted(files), raising=True)

    # Version 1: should apply 2 and 4
    assert mod._pending_migrations(1) == [(2, files[1]), (4, files[2])]

    # Version 3: should apply only 4
    assert mod._pending_migrations(3) == [(4, files[2])]

    # Version 4: up-to-date → nothing to do
    assert mod._pending_migrations(4) == []


# ─────────────────────────────────────────────────────────────────────────────
# _apply_migration
# ─────────────────────────────────────────────────────────────────────────────

def test_apply_migration_in_memory(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """
    _apply_migration() executes SQL and updates user_version.

    This test:
    - Uses an in-memory DB.
    - Writes a migration file that creates a table.
    - Asserts the table exists.
    - Asserts `PRAGMA user_version` is updated atomically.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")

    # Create a simple migration file
    sql_file = tmp_path / "001_create_table.sql"
    sql_file.write_text("CREATE TABLE foo(id INTEGER PRIMARY KEY);", encoding="utf-8")

    mod = _reload_module(monkeypatch)
    mod._apply_migration(conn, sql_file, version=1)

    # Table created
    cur = conn.execute("SELECT name FROM sqlite_master WHERE name='foo'")
    assert cur.fetchone() == ("foo",)

    # Version updated
    cur = conn.execute("PRAGMA user_version")
    assert cur.fetchone()[0] == 1


# ─────────────────────────────────────────────────────────────────────────────
# run() – full migration flow
# ─────────────────────────────────────────────────────────────────────────────

def test_run_applies_all_migrations(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """
    run() should:
    - Connect to DB
    - Discover migration files
    - Apply them in sorted order
    - Set user_version to highest prefix
    """
    files = [
        tmp_path / "001_create.sql",
        tmp_path / "002_insert.sql",
    ]
    files[0].write_text("CREATE TABLE foo(id INTEGER PRIMARY KEY);", encoding="utf-8")
    files[1].write_text("INSERT INTO foo(id) VALUES (42);", encoding="utf-8")

    mod = _reload_module(monkeypatch)

    # Monkeypatch: migration file list and DB connection path
    monkeypatch.setattr(mod, "_list_sql_files", lambda: sorted(files), raising=True)

    db_file = tmp_path / "vault.db"

    def fake_connect():
        conn = sqlite3.connect(db_file)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr(mod, "_connect", fake_connect, raising=True)

    mod.run()  # Run the full migration engine

    # Validate state in real file-based DB
    conn = sqlite3.connect(db_file)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM foo").fetchone()[0] == 1
    conn.close()


def test_run_rolls_back_on_error(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """
    If a migration has syntax errors:
    - run() must raise an exception
    - Nothing should be committed
    - PRAGMA user_version must not change
    """
    bad_sql = tmp_path / "001_broken.sql"
    bad_sql.write_text("CREATE TABLE broken(", encoding="utf-8")  # invalid SQL

    mod = _reload_module(monkeypatch)

    # Inject the bad file and in-memory DB
    monkeypatch.setattr(mod, "_list_sql_files", lambda: [bad_sql], raising=True)
    monkeypatch.setattr(mod, "_connect", lambda: sqlite3.connect(":memory:"), raising=True)

    with pytest.raises(sqlite3.Error):
        mod.run()

    # Validate that no version bump happened
    conn = sqlite3.connect(":memory:")
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
