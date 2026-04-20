"""Diagnostic: teste toutes les séquences de réveil sur un moniteur éteint (VCP=5)."""
import time
import ctypes
import ctypes.wintypes

from monitorcontrol import get_monitors

VCP_POWER      = 0xD6
VCP_BRIGHTNESS = 0x10


def dpms_wake():
    HWND_BROADCAST  = 0xFFFF
    WM_SYSCOMMAND   = 0x0112
    SC_MONITORPOWER = 0xF170
    SMTO_ABORTIFHUNG = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, -1,
        SMTO_ABORTIFHUNG, 500, None,
    )
    import win32api, win32con
    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 1, 1, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, -1, -1, 0, 0)


def set_gamma(device_name: str):
    """Touche le signal GPU via SetDeviceGammaRamp (comme reset_gamma_all)."""
    ramp = (ctypes.c_ushort * 768)()
    for i in range(256):
        v = min(65535, int((i / 255.0) * 65535))
        ramp[i] = ramp[256 + i] = ramp[512 + i] = v
    hdc = ctypes.windll.gdi32.CreateDCW("DISPLAY", device_name, None, None)
    if hdc:
        ctypes.windll.gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp))
        ctypes.windll.gdi32.DeleteDC(hdc)
        print(f"   SetDeviceGammaRamp → {device_name}")


def ddc_alive(m) -> bool:
    try:
        with m:
            m.vcp.get_vcp_feature(VCP_BRIGHTNESS)
        return True
    except Exception:
        return False


def try_vcp(m, code: int, label: str) -> bool:
    try:
        with m:
            m.vcp.set_vcp_feature(VCP_POWER, code)
        print(f"   VCP={code} ({label}) → OK (pas d'erreur I2C)")
        return True
    except Exception as e:
        print(f"   VCP={code} ({label}) → ERREUR: {e}")
        return False


# ── Détection des moniteurs ───────────────────────────────────────────────────
monitors = list(get_monitors())
print(f"\n{len(monitors)} moniteur(s) détecté(s) :")
for i, m in enumerate(monitors):
    alive = ddc_alive(m)
    print(f"  [{i}] DDC {'VIVANT' if alive else 'MORT / pas de réponse'}")

print()
idx = int(input("Index du LG UltraWide (actuellement ÉTEINT) : "))
m = monitors[idx]

# Essaie de lire son device_name via screeninfo pour le gamma test
try:
    from screeninfo import get_monitors as _gm
    sm = list(_gm())
    device_name = sm[idx].name if idx < len(sm) else None
except Exception:
    device_name = None
print(f"   device_name screeninfo : {device_name}")

print()
print("═" * 60)
print(" TESTS DE RÉVEIL")
print("═" * 60)
print("(attends 3 s après chaque envoi avant de répondre)")
print()


def test(label: str, fn) -> bool:
    print(f"── {label}")
    fn()
    time.sleep(3)
    r = input("   Rallumé ? (o/n) : ").strip().lower() == "o"
    if not r:
        # re-éteindre si par hasard ça a marché à moitié
        pass
    return r


results = {}

# Test 1 : VCP=1 seul
def t1():
    try_vcp(m, 1, "power on")
results["VCP=1 seul"] = test("VCP=1 direct", t1)

# Test 2 : DPMS seul
def t2():
    dpms_wake()
    print("   DPMS -1 envoyé")
results["DPMS seul"] = test("DPMS wake (SC_MONITORPOWER -1)", t2)

# Test 3 : SetDeviceGammaRamp seul
def t3():
    if device_name:
        set_gamma(device_name)
    else:
        print("   (device_name inconnu, test ignoré)")
results["Gamma seul"] = test("SetDeviceGammaRamp seul", t3)

# Test 4 : DPMS + VCP=1
def t4():
    dpms_wake()
    time.sleep(0.3)
    try_vcp(m, 1, "power on")
results["DPMS + VCP=1"] = test("DPMS puis VCP=1 (0.3 s délai)", t4)

# Test 5 : Gamma + VCP=1
def t5():
    if device_name:
        set_gamma(device_name)
    time.sleep(0.3)
    try_vcp(m, 1, "power on")
results["Gamma + VCP=1"] = test("SetDeviceGammaRamp puis VCP=1", t5)

# Test 6 : VCP=2 (standby) puis VCP=1
def t6():
    try_vcp(m, 2, "standby")
    time.sleep(0.5)
    try_vcp(m, 1, "power on")
results["VCP=2+1"] = test("VCP=2 (standby) puis VCP=1", t6)

# Test 7 : VCP=4 puis VCP=1
def t7():
    try_vcp(m, 4, "off-soft")
    time.sleep(0.5)
    try_vcp(m, 1, "power on")
results["VCP=4+1"] = test("VCP=4 (off-soft) puis VCP=1", t7)

# Test 8 : DPMS + Gamma + VCP=1
def t8():
    dpms_wake()
    if device_name:
        set_gamma(device_name)
    time.sleep(0.3)
    try_vcp(m, 1, "power on")
results["DPMS+Gamma+VCP=1"] = test("DPMS + Gamma + VCP=1", t8)

print()
print("═" * 60)
print(" RÉSULTATS")
print("═" * 60)
for k, v in results.items():
    print(f"  {'✓' if v else '✗'}  {k}")
print()
