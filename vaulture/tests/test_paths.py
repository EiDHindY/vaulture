# vaulture/tests/test_path.py
import importlib, sys
from pathlib import Path
from types import ModuleType
from pytest import MonkeyPatch

PKG = "src.utils.paths"  # Single source-of-truth for re-imports


def _reload_paths(_: MonkeyPatch | None = None) -> ModuleType:
    """Drop src.utils.paths from sys.modules and import it fresh."""
    sys.modules.pop(PKG, None)
    return importlib.import_module(PKG)


def test_db_path_source(monkeypatch: MonkeyPatch) -> None:
    """
    In development/source mode `db_path()` must resolve to
    …/src/infrastructure/database/data/vault.db relative to project root.
    """
    mod = _reload_paths(monkeypatch)        # ① fresh import → not frozen
    db_path = mod.db_path()                 # ② call

    # ③ build the expected path by walking up from this test file
    project_root = Path(__file__).resolve().parents[1]   # vaulture/vaulture
    expected = (
        project_root
        / "src"
        / "infrastructure"
        / "database"
        / "data"
        / "vault.db"
    )

    # ④ assertions
    assert db_path == expected
    assert db_path.parent.exists(), "data/ directory is missing"


def test_db_path_frozen(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """When frozen, db_path() should go into user_data_dir(), mocked here."""
    # 1️⃣ Simulate "frozen" mode + dummy executable path
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Vaulture.exe"))

    # 2️⃣ Stub platformdirs.user_data_dir to return a controlled path
    monkeypatch.setattr(
        "platformdirs.user_data_dir",
        lambda *a, **kw: str(tmp_path / "my-data"),  # type:ignore
        raising=True,
    )

    mod = _reload_paths(monkeypatch)
    db_path = mod.db_path()

    expected = tmp_path / "my-data" / "vault.db"
    assert db_path == expected
    assert db_path.parent.exists()


def test_migrations_path_source(monkeypatch: MonkeyPatch) -> None:
    """
    migrations_path() should resolve to the repo-relative directory
    <inner-project-root>/src/infrastructure/database/migrations.
    """
    mod = _reload_paths(monkeypatch)            # fresh import → not frozen
    mig_path = mod.migrations_path()

    # walk up to <vaulture/vaulture>
    project_root = Path(__file__).resolve().parents[1]
    expected = (
        project_root
        / "src"
        / "infrastructure"
        / "database"
        / "migrations"
    )

    assert mig_path == expected
    assert mig_path.is_dir()


def test_migrations_path_frozen(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """
    When frozen, migrations_path() should sit next to the executable.
    """
    # 1️⃣ Simulate being frozen → fake exe in <tmp>/Bundle/Vaulture.exe
    exe_dir = tmp_path / "Bundle"
    exe_dir.mkdir()
    exe_file = exe_dir / "Vaulture.exe"
    exe_file.touch()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_file))

    mod = _reload_paths(monkeypatch)
    mig_path = mod.migrations_path()

    expected = exe_dir / "src" / "infrastructure" / "database" / "migrations"
    assert mig_path == expected
    assert not mig_path.exists()  # ❗does NOT auto-create folder


def test_log_path_source(monkeypatch: MonkeyPatch) -> None:
    """
    log_path() in dev mode should resolve to …/logs/vaulture.log
    *inside the real project tree* and create the logs/ dir.
    """
    mod = _reload_paths(monkeypatch)
    log_path = mod.log_path()

    # Log file should be named correctly and inside a "logs" folder
    assert log_path.name == "vaulture.log"
    assert log_path.parent.name == "logs"
    assert log_path.parent.exists()


def test_log_path_frozen(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """
    In frozen builds, log_path() should resolve to inside user_data_dir().
    """
    # 1️⃣ Simulate bundled app → fake executable
    exe_file = tmp_path / "Vaulture.exe"
    exe_file.touch()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_file))

    # 2️⃣ Stub platformdirs.user_data_dir → return controlled location
    monkeypatch.setattr(
        "platformdirs.user_data_dir",
        lambda *a, **kw: str(tmp_path / "user-logs"),  # type:ignore
        raising=True,
    )

    mod = _reload_paths(monkeypatch)  # fresh import
    log_path = mod.log_path()

    expected = tmp_path / "user-logs" / "vaulture.log"
    assert log_path == expected
    assert log_path.parent.exists()