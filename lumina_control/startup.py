"""Windows startup registry helper (F6).

Registers / unregisters the app in HKCU\\...\\Run so it launches with Windows.
No admin rights required — HKCU is always writable by the current user.
"""
import logging
import os
import sys
import winreg

log = logging.getLogger(__name__)

_APP_NAME = "LuminaControl"
_REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_exe_path() -> str:
    """Return the command string to write into the registry."""
    if getattr(sys, "frozen", False):
        # PyInstaller bundle — sys.executable is the .exe
        return f'"{sys.executable}"'
    # Running from source: use pythonw.exe (no console window) + script path
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable   # fallback if pythonw not found
    script = os.path.abspath(sys.argv[0])
    return f'"{pythonw}" "{script}"'


def is_enabled() -> bool:
    """Return True if the app is registered in the Windows startup key."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY)
        try:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """Add or remove the startup entry. Returns True on success."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        if enabled:
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, get_exe_path())
        else:
            try:
                winreg.DeleteValue(key, _APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except OSError as e:
        log.warning("Cannot modify startup registry key: %s", e)
        return False
