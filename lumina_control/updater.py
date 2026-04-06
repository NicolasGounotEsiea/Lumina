"""GitHub Releases update checker (B10).

Runs a non-blocking background check against the GitHub API.
Emits ``update_available(latest_version)`` when a newer release is found.

Usage::

    checker = UpdateChecker()
    checker.update_available.connect(my_slot)
    checker.start()          # non-blocking
"""
import json
import logging
import ssl
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, QThread, Signal, Slot

from lumina_control.config import APP_VERSION

log = logging.getLogger(__name__)

_API_URL      = "https://api.github.com/repos/NicolasGounotEsiea/Lumina/releases/latest"
_TIMEOUT_S    = 6
_RELEASES_URL = "https://github.com/NicolasGounotEsiea/Lumina/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    """Convert 'v1.2.3' or '1.2.3' to (1, 2, 3). Non-numeric parts → 0."""
    tag = tag.lstrip("vV").strip()
    parts = []
    for p in tag.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts) if parts else (0,)


def _is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


# ── Worker ────────────────────────────────────────────────────────────────────

class _CheckWorker(QObject):
    """Performs the HTTP request on a background thread."""

    result = Signal(str)   # emitted with latest version tag if newer, else ""

    @Slot()
    def run(self) -> None:
        try:
            ctx = ssl.create_default_context()
            req = urllib.request.Request(
                _API_URL,
                headers={"Accept": "application/vnd.github+json",
                         "User-Agent": "LuminaControl-updater"},
            )
            with urllib.request.urlopen(req, context=ctx, timeout=_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "")
            if tag and _is_newer(tag, APP_VERSION):
                self.result.emit(tag)
            else:
                self.result.emit("")
        except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError) as e:
            log.debug("Update check failed: %s", e)
            self.result.emit("")


# ── Public API ────────────────────────────────────────────────────────────────

class UpdateChecker(QObject):
    """One-shot async update checker.  Call ``start()`` once."""

    update_available = Signal(str)   # latest version tag (e.g. "v1.1.0")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread = QThread(self)
        self._worker = _CheckWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.result.connect(self._on_result)
        self._worker.result.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)

    def start(self) -> None:
        """Start the background check (no-op if already started)."""
        if not self._thread.isRunning():
            self._thread.start()

    @Slot(str)
    def _on_result(self, tag: str) -> None:
        if tag:
            self.update_available.emit(tag)

    @property
    def releases_url(self) -> str:
        return _RELEASES_URL
