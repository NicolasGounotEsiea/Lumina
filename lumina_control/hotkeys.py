"""Global hotkey registration via Windows RegisterHotKey / WM_HOTKEY.

Usage
-----
1. Create a ``HotkeyManager`` instance.
2. Call ``install_native_filter(app)`` once after ``QApplication`` is created.
3. Call ``register(modifiers, vkey, callback)`` to bind hotkeys.
4. Call ``unregister_all()`` on shutdown (connected to ``app.aboutToQuit``).

Windows delivers ``WM_HOTKEY`` messages to the thread that called
``RegisterHotKey``.  Qt's native event filter intercepts them from the main
thread's message queue so callbacks are always invoked on the Qt main thread.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
from typing import Callable

log = logging.getLogger(__name__)

# ── Win32 modifier constants ──────────────────────────────────────────────────
MOD_ALT      = 0x0001
MOD_CONTROL  = 0x0002
MOD_SHIFT    = 0x0004
MOD_WIN      = 0x0008
MOD_NOREPEAT = 0x4000    # suppress auto-repeat while the key is held

# ── Common VK codes ───────────────────────────────────────────────────────────
VK_UP        = 0x26
VK_DOWN      = 0x28
VK_F         = ord("F")
VK_G         = ord("G")
VK_N         = ord("N")

_WM_HOTKEY   = 0x0312


class HotkeyManager:
    """Register / unregister global hotkeys and dispatch their callbacks."""

    def __init__(self) -> None:
        self._registered: dict[int, Callable] = {}
        self._next_id: int = 9001
        self._filter = None     # keeps the QAbstractNativeEventFilter alive

    # ── Setup ─────────────────────────────────────────────────────────────────

    def install_native_filter(self, app) -> None:
        """Install a native event filter on *app* to receive WM_HOTKEY."""
        from PySide6.QtCore import QAbstractNativeEventFilter

        mgr = self

        class _Filter(QAbstractNativeEventFilter):
            def nativeEventFilter(self, event_type, message):
                if event_type == b"windows_generic_MSG":
                    try:
                        msg = ctypes.cast(
                            int(message),
                            ctypes.POINTER(ctypes.wintypes.MSG),
                        ).contents
                        if msg.message == _WM_HOTKEY:
                            mgr._dispatch(int(msg.wParam))
                    except Exception:
                        pass
                return False, 0

        self._filter = _Filter()
        app.installNativeEventFilter(self._filter)

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, modifiers: int, vkey: int, callback: Callable) -> int:
        """Register a global hotkey.  Returns the hotkey id (for ``unregister``)."""
        hk_id = self._next_id
        self._next_id += 1
        ok = bool(ctypes.windll.user32.RegisterHotKey(
            None, hk_id, modifiers | MOD_NOREPEAT, vkey
        ))
        if ok:
            self._registered[hk_id] = callback
            log.debug("Hotkey id=%d registered (mod=0x%X vk=0x%X)", hk_id, modifiers, vkey)
        else:
            err = ctypes.windll.kernel32.GetLastError()
            log.warning(
                "RegisterHotKey failed id=%d vk=0x%X error=%d "
                "(key may be taken by another app)",
                hk_id, vkey, err,
            )
        return hk_id

    def unregister(self, hk_id: int) -> None:
        """Unregister a single hotkey by id."""
        ctypes.windll.user32.UnregisterHotKey(None, hk_id)
        self._registered.pop(hk_id, None)

    def unregister_all(self) -> None:
        """Unregister all hotkeys (call on app quit)."""
        for hk_id in list(self._registered):
            ctypes.windll.user32.UnregisterHotKey(None, hk_id)
        self._registered.clear()
        log.debug("All hotkeys unregistered")

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _dispatch(self, hk_id: int) -> None:
        cb = self._registered.get(hk_id)
        if cb:
            try:
                cb()
            except Exception as exc:
                log.warning("Hotkey callback error (id=%d): %s", hk_id, exc)
