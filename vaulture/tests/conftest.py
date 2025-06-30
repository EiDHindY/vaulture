# vaulture/vaulture/tests/conftest.py
import sys
from pathlib import Path
import logging
import pytest
from pytest import MonkeyPatch

# --------------------------------------------------------------------------- #
# Make the inner vaulture/ (which contains src/) importable                   #
# --------------------------------------------------------------------------- #
PACKAGE_ROOT = Path(__file__).resolve().parents[1]      # …/vaulture/vaulture
sys.path.insert(0, str(PACKAGE_ROOT))

# --------------------------------------------------------------------------- #
# Isolation fixture: real handler, but to a tmp file                          #
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolate_logging(tmp_path: Path, monkeypatch: MonkeyPatch): # type:ignore
    """
    Redirect paths.log_path() to tmp_path so RotatingFileHandler still
    exists (tests rely on it) but writes only to an ephemeral file.
    Also start/finish each test with a pristine root logger.
    """
    # 1️⃣  Pretend the log lives in the tmp dir
    monkeypatch.setattr(
        "src.utils.paths.log_path",
        lambda: tmp_path / "vaulture_test.log",
        raising=False,
    )

    # 2️⃣  Clean-slate root logger
    root = logging.getLogger()
    root.handlers.clear()
    root.filters.clear()

    yield  # ---- run the test ----

    # 3️⃣  Ensure no handlers leak between tests
    root.handlers.clear()
    root.filters.clear()
