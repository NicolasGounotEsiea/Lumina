"""Vérification de licence hors ligne — signature Ed25519 sur payload JSON.

La clé publique est intégrée au binaire à la compilation.
Aucun accès réseau n'est jamais nécessaire.

Format des champs du payload (noms courts pour des clés compactes)
------------------------------------------------------------------
  e  : adresse email du client (str)
  p  : plan — "pro" | "lifetime" (str)
  m  : nombre max de machines autorisées (int, informatif sauf si "i" présent)
  x  : date d'expiration ISO-8601, ex. "2027-04-14" (str, absent = à vie)
  i  : liste d'IDs machine autorisés (list[str], optionnel — liaison stricte)

Format de la clé
----------------
  {base64url(payload_json)}.{base64url(signature_ed25519)}
  (base64 url-safe sans padding)

Procédure développeur
---------------------
  1. python gen_license.py keygen
  2. Coller la clé publique PEM imprimée dans _PUBLIC_KEY_PEM ci-dessous, puis rebuilder.
  3. python gen_license.py issue --email client@mail.com
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import winreg
from dataclasses import dataclass
from datetime import date

log = logging.getLogger(__name__)

# ── Clé publique embarquée ────────────────────────────────────────────────────
# Remplacer ce placeholder après avoir lancé : python gen_license.py keygen
_PUBLIC_KEY_PEM: bytes = b"""\
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAQYhsK5bhidFJ9fY0VtZdzeJ5vUiHjqOiPbv6glk9SM0=
-----END PUBLIC KEY-----
"""

# ── Mode développeur ──────────────────────────────────────────────────────────
# Définir LUMINA_DEV=1 dans l'environnement pour contourner la vérification.
#   Windows PowerShell : $env:LUMINA_DEV="1"; python multiscreen_tray.py
_DEV_BYPASS: bool = os.environ.get("LUMINA_DEV") == "1"

# ── Clé de registre ───────────────────────────────────────────────────────────
_REG_PATH  = r"SOFTWARE\LuminaControl"
_REG_VALUE = "LicenseKey"


# ── Types publics ─────────────────────────────────────────────────────────────

@dataclass
class LicenseResult:
    valid:    bool
    email:    str        = ""
    plan:     str        = ""
    machines: int        = 0
    expires:  str | None = None   # date ISO ou None (à vie)
    error:    str        = ""

    @property
    def is_lifetime(self) -> bool:
        return self.valid and self.expires is None


# ── Identifiant machine ───────────────────────────────────────────────────────

def get_machine_id() -> str:
    """Renvoie un identifiant stable lié à cette installation Windows."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as k:
            guid: str = winreg.QueryValueEx(k, "MachineGuid")[0]
            return hashlib.sha256(guid.encode()).hexdigest()[:32]
    except Exception:
        return "unknown"


# ── Vérification ─────────────────────────────────────────────────────────────

def verify(license_key: str) -> LicenseResult:
    """Vérifie *license_key* hors ligne. Renvoie LicenseResult (valid=True si OK)."""
    if _DEV_BYPASS:
        log.warning("Vérification de licence IGNORÉE (LUMINA_DEV=1)")
        return LicenseResult(valid=True, email="dev", plan="pro", machines=99)

    try:
        key = license_key.strip()
        parts = key.split(".")
        if len(parts) != 2:
            return LicenseResult(valid=False, error="Format de clé invalide")

        payload_b64, sig_b64 = parts

        def _pad(s: str) -> str:
            return s + "=" * (-len(s) % 4)

        payload_bytes = base64.urlsafe_b64decode(_pad(payload_b64))
        sig_bytes     = base64.urlsafe_b64decode(_pad(sig_b64))

        # Vérification de la signature Ed25519
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        pub = load_pem_public_key(_PUBLIC_KEY_PEM)
        try:
            pub.verify(sig_bytes, payload_bytes)
        except InvalidSignature:
            return LicenseResult(valid=False, error="Signature invalide — clé refusée")

        p = json.loads(payload_bytes.decode())

        # Vérification de la date d'expiration
        expires: str | None = p.get("x")
        if expires and date.today() > date.fromisoformat(expires):
            return LicenseResult(valid=False, error="Licence expirée")

        # Liaison machine (uniquement si le champ "i" est présent dans le payload)
        machine_ids: list[str] = p.get("i", [])
        if machine_ids and get_machine_id() not in machine_ids:
            return LicenseResult(
                valid=False,
                error=(
                    "Licence non valide pour cette machine\n"
                    f"(ID : {get_machine_id()})"
                ),
            )

        return LicenseResult(
            valid=True,
            email=p.get("e", ""),
            plan=p.get("p", "pro"),
            machines=int(p.get("m", 1)),
            expires=expires,
        )

    except Exception as exc:
        log.warning("Erreur lors de la vérification de licence : %s", exc)
        return LicenseResult(valid=False, error=f"Erreur inattendue : {exc}")


# ── Persistance (registre Windows) ────────────────────────────────────────────

def load_stored_key() -> str | None:
    """Lit la clé de licence depuis le registre Windows. Renvoie None si absente."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as k:
            value, _ = winreg.QueryValueEx(k, _REG_VALUE)
            return str(value) if value else None
    except FileNotFoundError:
        return None
    except Exception as exc:
        log.warning("Impossible de lire la licence depuis le registre : %s", exc)
        return None


def store_key(key: str) -> None:
    """Enregistre *key* dans le registre Windows (HKCU)."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as k:
        winreg.SetValueEx(k, _REG_VALUE, 0, winreg.REG_SZ, key)


def delete_key() -> None:
    """Supprime la clé de licence du registre."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH,
            access=winreg.KEY_WRITE,
        ) as k:
            winreg.DeleteValue(k, _REG_VALUE)
    except FileNotFoundError:
        pass
    except Exception as exc:
        log.warning("Impossible de supprimer la licence du registre : %s", exc)
