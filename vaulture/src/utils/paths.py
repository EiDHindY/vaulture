"""
paths.py – centralised helpers for locating Vaulture’s on-disk resources.

This module abstracts away the differences between a *frozen* binary
(PyInstaller, cx_Freeze, etc.) and an “editable” source checkout.  
Its primary job is to return the absolute path of the **encrypted vault
database** while ensuring that, in the packaged build, the parent
directory is created with restrictive permissions (0700).

Attributes
----------
APP_NAME : str
    Human-friendly application name (used by `platformdirs`).
APP_AUTHOR : str
    Publisher/author string (also used by `platformdirs`).

Functions
---------
db_path() -> Path
    Compute the correct location of ``vault.db`` for the current runtime
    context.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from platformdirs import user_data_dir

#: Application identifiers reused by ``platformdirs`` to build a
#: per-user data directory in a cross-platform fashion.
_APP_NAME: Final[str] = "Vaulture"
_APP_AUTHOR: Final[str] = "DoD"
_DB_FILE_NAME:Final[str] = "vault.db"


def db_path() -> Path:  # noqa: D401
    """
    Return the absolute filesystem path to *vault.db*.

    Behaviour
    ---------
    * **Frozen executable** (attribute ``sys.frozen`` injected by most
    bundlers):  
      - Place the database under the OS-correct *user data directory*,
        e.g. ``%APPDATA%\\Vaulture\\vault.db`` on Windows or
        ``~/.local/share/Vaulture/vault.db`` on Linux.  
    - Create the directory tree on first run with permissions
        ``0o700`` (owner RWX only) to prevent other local users from
        listing or reading its contents.

    * **Source / development mode**:  
    - Keep the database inside the repository at  
        ``src/infrastructure/database/data/vault.db`` relative to this
        file.  This lets devs inspect or delete the file easily and keeps
        test artefacts local to the project tree.

    Returns
    -------
    pathlib.Path
        Fully resolved path pointing to the *vault.db* file.
    """
    if getattr(sys, "frozen", False):
        # Running as a bundled executable. Use platformdirs to get a
        # per-user location that follows the host OS guidelines.
        db_dir: Path = Path(user_data_dir(_APP_NAME, _APP_AUTHOR))

        # Ensure the directory exists; `mode=0o700` is vital on *nix
        # systems so that other local accounts cannot peek at the vault.
        db_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        return db_dir / _DB_FILE_NAME

    # Development/runtime from source: place the DB in the repo so it is
    # version-control-adjacent and easy to locate.
    return (
        Path(__file__).resolve().parent.parent
        / "src"
        / "infrastructure"
        / "database"
        / "data"
        / _DB_FILE_NAME
    )



#: Relative location of the directory that stores SQL migration scripts
#: when running from *source*.  The same folder is expected to be copied
#: verbatim next to the executable in a frozen (PyInstaller, cx_Freeze)
#: build so that migrations remain discoverable at runtime.
_REL_MIGRATIONS: Final[str] = "src/infrastructure/database/migrations"


def migrations_path() -> Path:  # noqa: D401
    """
    Return the absolute path of the *migrations* directory.

    Behaviour
    ---------
    * **Frozen executable** (`sys.frozen` set by most bundlers)  
      Assume that the packager copied the *migrations* folder into the
        same directory as the produced binary.  Using
        ``Path(sys.executable).parent`` keeps the lookup simple and
        independent of the host platform’s layout.

    * **Source / development mode**  
        Navigate two levels up from this file to reach the project root,
        then append the canonical relative path
        ``src/infrastructure/database/migrations`` so that the SQL files
        can be loaded directly from the repository tree.

    Notes
    -----
    * The function **does not** create the directory; migrations are
        read-only assets consumed by the database bootstrapper.
    * Keeping this logic in one place isolates filesystem assumptions and
        makes future refactors (e.g. switching to Alembic) easier.

    Returns
    -------
    pathlib.Path
        Fully resolved path pointing to the migrations directory.
    """
    if getattr(sys, "frozen", False):
        # e.g. …/Vaulture.exe → …/  (Windows)  |  …/Vaulture → …/ (Linux/macOS)
        base: Path = Path(sys.executable).parent
    else:
        # utils/paths.py → utils → project_root
        base: Path = Path(__file__).resolve().parent.parent

    return base / _REL_MIGRATIONS

#: Folder that will *contain* the log file when running from source
_LOG_DIR_NAME: Final[str] = "logs"
#: Filename of the main application log
_LOG_FILE_NAME: Final[str] = "vaulture.log"


def log_path() -> Path:  # noqa: D401
    """
    Return the absolute path where Vaulture should write its log file.

    Behaviour
    ---------
    * **Frozen / packaged build**  
      Use ``platformdirs.user_data_dir(APP_NAME, APP_AUTHOR)`` so the log
      sits alongside other user-specific data with OS-appropriate
      layout.

    * **Source / development mode**  
      Resolve to ``<project_root>/logs/vaulture.log`` to keep noisy
      output out of ``src/`` and under version-control-ignored folders.

    Side effects
    ------------
    * Ensures the parent directory exists and is created with
      permissions ``0o700`` (owner read/write/execute only).

    Returns
    -------
    pathlib.Path
        Fully resolved path to *vaulture.log*.
    """
    if getattr(sys, "frozen", False):
        # e.g. ~/.local/share/Vaulture  |  %APPDATA%\Vaulture
        base_dir: Path = Path(user_data_dir(_APP_NAME, _APP_AUTHOR))
    else:
        # utils/paths.py -> utils -> project_root / logs
        base_dir: Path = Path(__file__).resolve().parent.parent / _LOG_DIR_NAME

    # Create the directory tree securely; `exist_ok=True` prevents races
    # on subsequent calls, and `0o700` keeps other local users out.
    base_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    return base_dir / _LOG_FILE_NAME