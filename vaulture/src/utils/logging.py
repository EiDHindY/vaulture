"""
logging_config.py – centralised logging bootstrap for Vaulture
==============================================================

Design goals
------------
* **Single initialisation point** – import-side-effect ensures every
  module that calls :func:`get_logger` inherits the same handlers and
  formatting.
* **Privacy by default** – redact highly-sensitive keys so plaintext
  secrets never reach disk or console.
* **Rotation & retention** – 1 MiB rolling logs with five backups keep
  disk usage bounded while preserving recent history for debugging.
* **Frozen-aware** – in a packaged build the log goes to the per-user
  data dir; in dev mode an INFO-level console handler aids diagnosis.
* **Crash capture** – install a custom ``sys.excepthook`` that logs any
  uncaught exception *before* delegating to Python’s default handler.

Usage
-----
Always acquire loggers via :func:`get_logger` instead of calling
``logging.getLogger`` directly:

>>> from logging_config import get_logger
>>> log = get_logger(__name__)
>>> log.info("Service started")

The first call triggers configuration; subsequent calls are cheap no-ops.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from types import TracebackType
from typing import Final

from utils.paths import log_path

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

#: Maximum log file size before rotation (bytes) – 1 MiB.
_LOG_MAX_BYTES: Final[int] = 1_048_576
#: Number of rotated log files to retain on disk.
_LOG_BACKUP_COUNT: Final[int] = 5

# --------------------------------------------------------------------------- #
# Redaction filter
# --------------------------------------------------------------------------- #


class _RedactSecretsFilter(logging.Filter):
    """
    Scrub *extremely* sensitive key/value pairs from structured log calls.

    The filter expects the logging call to supply *kwargs* as ``record.args``::
        log.info("user action", extra={"master_password": value})

    If ``record.args`` is a ``dict``, any key listed in
    :pyattr:`_SENSITIVE_KEYS` is replaced with the literal string
    ``"<redacted>"`` *in-place*.

    Notes
    -----
    * Only dictionary-style ``record.args`` are touched – positional
      `%` formatting tuples are ignored to avoid corrupting messages.
    * The filter always returns :pydata:`True` so the record continues
      down the handler chain.
    """

    _SENSITIVE_KEYS: Final[set[str]] = {
        "master_password",
        "derived_key",
        "password_clear",
        "secret",
    }

    # noqa: D401 – imperative mood for logging.Filter.filter
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        """
        Apply in-place redaction and allow the record through.

        Parameters
        ----------
        record :
            The log record emitted by the caller.

        Returns
        -------
        bool
            Always ``True`` – record should be processed by handlers.
        """
        if isinstance(record.args, dict):
            record.args = {
                k: ("<redacted>" if k in self._SENSITIVE_KEYS else v)
                for k, v in record.args.items()
            }
        return True


# --------------------------------------------------------------------------- #
# Root logger configuration
# --------------------------------------------------------------------------- #


def _configure_root_logger() -> None:
    """
    One-time initialisation of the *root* logger.

    Adds:

    * **RotatingFileHandler** (DEBUG) → ``log_path()``  
      – captures everything, redacts secrets, rotates at 1 MiB × 5.
    * **StreamHandler** (INFO) to *stdout* in *development* mode  
      – suppressed in frozen builds to keep packaged binaries silent.

    Also:

    * Enables ``logging.captureWarnings(True)`` so ``warnings`` module
      output lands in the same sinks.
    * Registers a custom :pydata:`sys.excepthook` that logs unhandled
      exceptions at *CRITICAL* before falling back to Python’s default
      behaviour (which prints tracebacks and returns non-zero).
    """
    root = logging.getLogger()

    # Guard: only run once per interpreter.
    if root.handlers:
        return

    root.setLevel(logging.DEBUG)

    # ---------- File handler ------------------------------------------------ #
    file_handler = logging.handlers.RotatingFileHandler(
        log_path(),
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    file_handler.addFilter(_RedactSecretsFilter())
    root.addHandler(file_handler)

    # ---------- Console handler (development only) -------------------------- #
    if not getattr(sys, "frozen", False):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter("%(levelname)-8s | %(name)s | %(message)s")
        )
        console_handler.addFilter(_RedactSecretsFilter())
        root.addHandler(console_handler)

    # Capture stdlib warnings (e.g. DeprecationWarning)
    logging.captureWarnings(True)

    # ---------- Global exception hook -------------------------------------- #
    def _excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:  
        """
        Log any uncaught exception and then invoke the original hook."""
        root.critical(
            "UNCAUGHT EXCEPTION",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        # Delegate to the default handler (prints to stderr, sets exit code)
        sys.__excepthook__(exc_type, exc_value, exc_traceback)  # type: ignore[arg-type]

    sys.excepthook = _excepthook


# --------------------------------------------------------------------------- #
# Public helper
# --------------------------------------------------------------------------- #


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Retrieve a configured logger, initialising the root logger on demand.

    Parameters
    ----------
    name :
        * ``None`` → the root logger.  
        * A dotted string → hierarchical child (e.g. ``"vaulture.gui"``
        or ``__name__`` inside a module).

    Returns
    -------
    logging.Logger
        The requested logger instance.
    """
    _configure_root_logger()
    return logging.getLogger(name)
