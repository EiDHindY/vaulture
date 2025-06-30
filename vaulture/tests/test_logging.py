
# vaulture/src/tests/test_logging.py

"""
Regression tests for *vaulture.src.utils.logging*.

The goal is to guarantee that the project-wide logging bootstrap
performs **exactly one** root-level initialisation—even if the module is
imported multiple times (directly or indirectly).

Why this matters
----------------
* Duplicate handlers ⇒ log lines written **N ×** per call, bloating log
  files and spamming consoles.
* Multiple redaction filters ⇒ redundant work and potential
  double-redaction bugs.
* Conflicting handler state ⇒ rotation limits or formatter settings may
  diverge between copies.

The test uses `pytest.MonkeyPatch` to evict the module from
`sys.modules`, simulating a *fresh* interpreter import without having to
spawn a subprocess.



– redaction-filter regression test
==================================================

This test ensures the project-wide ``_RedactSecretsFilter``:

1. Leaves **non-sensitive** keys untouched.
2. Replaces **sensitive** keys (e.g. ``master_password``) with the
   literal string ``"<redacted>"`` before the record reaches any handler.
3. Emits exactly **one** log record at the DEBUG level.

A failure here would imply that plaintext secrets might leak to disk or
stdout, violating Vaulture’s privacy guarantees.
"""

import sys, importlib, logging
from logging.handlers import RotatingFileHandler
from pytest import MonkeyPatch
import pytest
from _pytest.logging import LogCaptureFixture
from typing import Iterator                

#: Single source of truth for the module under test.  Keeping it in one
#: constant avoids typos between `importlib.import_module()` calls.
PKG: str = "src.utils.logging"


@pytest.fixture(autouse=True)
def _no_file_writes() -> Iterator[None]:  # type: ignore
    """
    Ensure tests do not write to the actual vaulture.log file.

    This autouse fixture runs around **every test**, and after each one:
    - Removes any `RotatingFileHandler` instances from the root logger.
    - Ensures log output is captured by in-memory tools like `caplog` only.

    Prevents disk writes and avoids interfering with production log rotation.
    """
    yield
    # Strip file handlers post-test to avoid polluting vaulture.log
    root = logging.getLogger()
    root.handlers[:] = [
        h for h in root.handlers if not isinstance(h, RotatingFileHandler)
    ]



# --------------------------------------------------------------------------- #
# Helper utilities                                                            #
# --------------------------------------------------------------------------- #
def _reload_logging(_: MonkeyPatch):  # noqa: D401
    """
    Remove *vaulture.src.utils.logging* from `sys.modules` and re-import.

    This forces a *cold* import so the root-logger configuration code
    (`_configure_root_logger`) executes again, allowing us to validate
    that it installs handlers **idempotently**.

    Parameters
    ----------
    _ : MonkeyPatch
        Fixture supplied by `pytest` (unused but retained for symmetry
        with other tests that may require patching).

    Returns
    -------
    module
        The freshly imported logging configuration module.
    """
    sys.modules.pop(PKG, None)  # Forget any prior import.
    root = logging.getLogger()
    root.handlers.clear()
    root.filters.clear()
    return importlib.import_module(PKG)


def _n_file_handlers() -> int:
    """
    Count *RotatingFileHandler* instances attached to the root logger.

    Returns
    -------
    int
        Number of `RotatingFileHandler` objects currently registered.
    """
    return sum(
        isinstance(h, RotatingFileHandler)
        for h in logging.getLogger().handlers
    )


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #
def test_single_initialisation(monkeypatch: MonkeyPatch) -> None:
    """
    Ensure `get_logger` sets up **one and only one** file handler.

    Steps
    -----
    1.  Reload the logging module in a pristine state.
    2.  Call `get_logger` once → should create **one** handler.
    3.  Import the module *again* (simulating transient re-imports) →
        handler count must stay unchanged.
    """
    mod = _reload_logging(monkeypatch)

    # The logger isn’t configured until *somebody* asks for it.
    mod.get_logger(__name__)
    assert _n_file_handlers() == 1

    # Re-importing the module should be a no-op regarding handler count.
    importlib.import_module(PKG)
    assert (
        _n_file_handlers() == 1
    ), "Duplicate RotatingFileHandlers detected – logging is not idempotent"

def test_redaction_filter(monkeypatch: MonkeyPatch, caplog: LogCaptureFixture):   
    """Verify that the redaction filter replaces sensitive values
        with the literal string ``"<redacted>"`` **and** leaves non-sensitive
        keys untouched.

        Steps performed:
            1. Reload the logging module so that each test starts
            with a *clean* root logger (handled by ``_reload_logging``).
            2. Re-attach pytest’s capture handler after the reload
            to intercept records post-filtering.
            3. Emit a DEBUG record containing both sensitive
            (``master_password``) and ordinary (``service``) data.
            4. Assert:
                • the secret value never appears in plain text,
                • the record count is exactly one,
                • the sensitive key is now ``"<redacted>"``,
                • the non-sensitive key remains unchanged.
        """

    # Reload the logging configuration so the root logger is pristine.
    log_mod = _reload_logging(monkeypatch)

    # Obtain a namespaced logger; the first call triggers config.
    log = log_mod.get_logger("test.redact")

    # pytest’s caplog fixture was detached by _reload_logging → add it back.
    root = logging.getLogger()
    root.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG)          # capture everything

    # ------------------------------------------------------------------ #
    # Emit a structured DEBUG record that should be filtered.            #
    # ------------------------------------------------------------------ #
    log.debug(
        "saving %(service)s credentials",
        {
            "service": "github.com",
            "master_password": "hunter2",
            "username": "dod",
        },
    )

    # ------------------------------------------------------------------ #
    # Assertions                                                         #
    # ------------------------------------------------------------------ #
    # The secret must not appear anywhere in the captured log text.
    assert "hunter2" not in caplog.text
    # Exactly one record should have been emitted.
    assert len(caplog.records) == 1

    record = caplog.records[0]
    # Sensitive key was redacted.
    assert record.args["master_password"] == "<redacted>"  # type: ignore[index]
    # Non-sensitive key is untouched.
    assert record.args["service"] == "github.com"           # type: ignore[index]

def test_uncaught_exception_hook(monkeypatch: MonkeyPatch,
                                 caplog: LogCaptureFixture) -> None:
    # Reload the logging config to install the sys.excepthook override.
    log_mod = _reload_logging(monkeypatch)

    # Re-attach pytest’s capture handler to the root logger,
    # since _reload_logging clears all handlers.
    root = logging.getLogger()
    root.addHandler(caplog.handler)
    caplog.set_level(logging.CRITICAL)

    # -------- fabricate an exception --------
    try:
        1 / 0  # type:ignore
    except ZeroDivisionError: 
        exc_type, exc_val, exc_tb = sys.exc_info()  # Capture the full exception tuple

    # Manually invoke the global exception hook, simulating a crash
    # without terminating the test process.
    log_mod.sys.excepthook(exc_type, exc_val, exc_tb)  # type: ignore[attr-defined]

    # ------------- assertions ---------------

    # Ensure exactly one critical-level record was emitted
    assert len(caplog.records) == 1, "Hook did not log"
    rec = caplog.records[0]

    # Confirm it was logged as CRITICAL
    assert rec.levelno == logging.CRITICAL

    # Message should begin with the hardcoded string in excepthook
    assert rec.getMessage().startswith("UNCAUGHT EXCEPTION")

    # exc_info should be attached so the handler/formatter can include the traceback
    assert rec.exc_info is not None

    # Sanity-check: traceback contains the test function or module-level line
    import traceback
    tb_list = traceback.extract_tb(rec.exc_info[2])
    assert tb_list[-1].name == "<module>" or tb_list[-1].name == "test_uncaught_exception_hook"