
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
"""


import sys, importlib, logging
from logging.handlers import RotatingFileHandler
from pytest import MonkeyPatch
#: Single source of truth for the module under test.  Keeping it in one
#: constant avoids typos between `importlib.import_module()` calls.
PKG: str = "vaulture.src.utils.logging"


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