# vaulture/tests/test_path.py
import importlib, sys
from pathlib import Path
from types import ModuleType
from pytest import MonkeyPatch
import os

PKG = "src.utils.paths"  # Single source-of-truth for re-imports


def _reload_paths(_: MonkeyPatch | None = None) -> ModuleType:
    """
    Force a fresh import of `src.utils.paths` to simulate an initial interpreter state.

    Removes the module from sys.modules so any runtime conditions
    (like `sys.frozen`) can be tested with accurate side effects.
    """
    sys.modules.pop(PKG, None)
    return importlib.import_module(PKG)


def test_db_path_source(monkeypatch: MonkeyPatch) -> None:
    """
    Ensure that in **source (development) mode**, `db_path()` resolves to:
    <project_root>/src/infrastructure/database/data/vault.db
    """
    mod = _reload_paths(monkeypatch)     # ① Simulate dev mode (not frozen)
    db_path = mod.db_path()              # ② Resolve path under test

    # ③ Calculate the expected path relative to this test file’s location
    project_root = Path(__file__).resolve().parents[1]  # → vaulture/vaulture
    expected = (
        project_root
        / "src"
        / "infrastructure"
        / "database"
        / "data"
        / "vault.db"
    )

    # ④ Assertions: must match exactly, and parent directory must exist
    assert db_path == expected
    assert db_path.parent.exists(), "data/ directory is missing"

def test_db_path_frozen(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    # 1️  pretend we’re frozen
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Vaulture.exe"))

    # 2️  stub platformdirs.user_data_dir
    monkeypatch.setattr(
        "platformdirs.user_data_dir",
        lambda *a, **kw: str(tmp_path / "my-data"), # type:ignore
        raising=True,
    )

    mod = _reload_paths(monkeypatch)
    db_path = mod.db_path()

    expected = tmp_path / "my-data" / "vault.db"
    assert db_path == expected
    assert db_path.parent.exists()

