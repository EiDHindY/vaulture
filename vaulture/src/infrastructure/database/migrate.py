"""
migrate.py – lightweight, file-based migration runner for Vaulture.

Design philosophy
-----------------
* **No external tooling**: we rely solely on SQLite and plain `.sql`
  files so the binary distribution remains dependency-free.
* **Monotonic integer versions**: each migration file starts with a
  zero-padded integer prefix (e.g. ``001_create_users_table.sql``).
  The prefix becomes the *target* value of SQLite's `PRAGMA user_version`.
* **Idempotent execution**: already-applied migrations are skipped by
  comparing their prefix with the current `user_version`.
* **Transactional safety**: each file is wrapped in a single
  `executescript` call inside a context manager (`with conn:`) so it
  commits atomically or rolls back on error.
* **Foreign-key enforcement**: immediately enable `PRAGMA foreign_keys`
  to ensure all later DDL respects constraints.

The module exposes one public function, :func:`run`, which is invoked by
the `if __name__ == "__main__"` guard for CLI usage and can also be
imported by the application bootstrapper.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Tuple

from src.utils.paths import db_path, migrations_path

# --------------------------------------------------------------------------- #
# Low-level helpers
# --------------------------------------------------------------------------- #

def _connect() -> sqlite3.Connection:
    """
    Open a connection to the *encrypted* Vaulture SQLite database.

    The caller is responsible for closing the connection (see :func:`run`
    which uses a context manager).  Foreign keys are enabled immediately
    to guarantee relational integrity for every subsequent statement.

    Returns
    -------
    sqlite3.Connection
        A live connection object with ``foreign_keys = ON``.
    """
    conn = sqlite3.connect(db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _current_version(conn: sqlite3.Connection) -> int:
    """
    Return the integer stored in ``PRAGMA user_version``.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open connection where the pragma will be queried.

    """
    cur = conn.execute("PRAGMA user_version")
    return cur.fetchone()[0]


def _list_sql_files() -> List[Path]:
    """
    Enumerate all ``*.sql`` files inside the *migrations* directory,
    sorted lexicographically so natural numeric ordering holds (because
    of zero-padded prefixes).

    Returns
    -------
    list[pathlib.Path]
        Absolute paths of every `.sql` migration.
    """
    return sorted(migrations_path().glob("*.sql"))


def _extract_prefix(file_path: Path) -> int:
    """
    Parse the leading numeric prefix from a migration filename.

    Example
    -------
    ``002_add_index.sql`` ⇒ ``2``

    Raises
    ------
    ValueError
        If the prefix is missing or not an integer.
    """
    prefix_str: str = file_path.name.split("_", 1)[0]
    return int(prefix_str)


def _pending_migrations(current_version: int) -> List[Tuple[int, Path]]:
    """
    Build an ordered list of migrations whose prefix is **greater**
    than ``current_version``.

    The output is a list of ``(version, Path)`` tuples already sorted in
    ascending order, ready for sequential execution.

    Notes
    -----
    Using tuples keeps the version integer adjacent to its file path,
    making later loops clearer and type-safe.
    """
    pending_files: List[Tuple[int, Path]] = []
    for sql_file in _list_sql_files():
        file_version: int = _extract_prefix(sql_file)
        if file_version > current_version:
            pending_files.append((file_version, sql_file))

    # Explicit sort – even though _list_sql_files() is sorted, this adds
    # a safety net if someone renames a file incorrectly.
    pending_files.sort(key=lambda pair: pair[0])
    return pending_files


def _apply_migration(
    conn: sqlite3.Connection,
    sql_file: Path,
    version: int,
) -> None:
    """
    Execute a single SQL migration and update ``user_version``.

    The context manager around *conn* in :func:`run` guarantees a commit
    if the script succeeds or a rollback plus raised exception if it
    fails – keeping the database in a consistent state.

    Parameters
    ----------
    conn : sqlite3.Connection
        An *open* connection with active transaction scope.
    sql_file : pathlib.Path
        Path to the ``*.sql`` file to be executed.
    version : int
        Target schema version after applying this migration.
    """
    with conn:
        conn.executescript(sql_file.read_text(encoding="utf-8"))
        conn.execute(f"PRAGMA user_version = {version}") 


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def run() -> None:  # noqa: D401
    """
    Apply all pending database migrations **in sequence**.

    This function is *idempotent* – a second call right after a
    successful run will perform no work because the stored
    ``user_version`` equals the highest migration prefix.

    Raises
    ------
    sqlite3.Error
        Propagated up if any migration fails; the transaction for that
        file is rolled back automatically by the context manager.
    """
    with _connect() as conn:
        current_version: int = _current_version(conn)

        for version, file in _pending_migrations(current_version):
            _apply_migration(conn, file, version)
            current_version = version  # for clarity in future loops


# --------------------------------------------------------------------------- #
# CLI entry-point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    # Allow `python -m src.infrastructure.database.migrate` or direct
    # invocation to bootstrap a fresh schema during development.
    run()
