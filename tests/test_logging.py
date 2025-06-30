import logging, importlib, sys
from pytest import MonkeyPatch

def _reload_logging(monkeypatch: MonkeyPatch):
    sys.modules.pop("src.utils.logging", None)
    root = logging.getLogger()
    root.handlers.clear()
    root.filters.clear()
    return importlib.import_module("vaulture.src.utils.logging")


def test_single_initialisation(monkeypatch: MonkeyPatch):
    _reload_logging(monkeypatch)
    root = logging.getLogger()
    assert len(root.handlers) == 1

    importlib.import_module("vaulture.src.utils.logging")
    assert len(root.handlers) == 1

