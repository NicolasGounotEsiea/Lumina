#!/usr/bin/env python3
"""
Lumina Control — License key generator  (DEVELOPER TOOL — ne pas distribuer).

Première utilisation
--------------------
    python gen_license.py keygen
    → crée lumina_private.pem  (ne jamais partager, ne jamais commiter)
    → affiche la clé publique PEM à coller dans lumina_control/license.py

Émettre une licence
-------------------
    python gen_license.py issue --email alice@example.com
    python gen_license.py issue --email alice@example.com --plan pro --expires 2027-04-14
    python gen_license.py issue --email alice@example.com --machine-ids abc123,def456

Options
-------
    --email       Email du client (obligatoire pour 'issue')
    --plan        pro | lifetime  (défaut : pro)
    --expires     Date d'expiration YYYY-MM-DD (omis = à vie)
    --machines    Nombre de machines autorisées — informatif (défaut : 2)
    --machine-ids IDs machine séparés par des virgules (liaison stricte, optionnel)
    --force       Écraser un fichier de clé existant (keygen seulement)
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

PRIVATE_KEY_PATH = Path("lumina_private.pem")
PUBLIC_KEY_PATH  = Path("lumina_public.pem")


# ── keygen ────────────────────────────────────────────────────────────────────

def cmd_keygen(args: argparse.Namespace) -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )

    if PRIVATE_KEY_PATH.exists() and not args.force:
        print(f"ERREUR : {PRIVATE_KEY_PATH} existe déjà. Utilisez --force pour écraser.")
        sys.exit(1)

    priv = Ed25519PrivateKey.generate()
    pub  = priv.public_key()

    priv_pem = priv.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    pub_pem  = pub.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

    PRIVATE_KEY_PATH.write_bytes(priv_pem)
    PUBLIC_KEY_PATH.write_bytes(pub_pem)

    print(f"✓ Clé privée enregistrée : {PRIVATE_KEY_PATH}  — NE JAMAIS partager ou commiter")
    print(f"✓ Clé publique enregistrée : {PUBLIC_KEY_PATH}")
    print()
    print("Collez le bloc suivant dans lumina_control/license.py (_PUBLIC_KEY_PEM) :")
    print("-" * 64)
    print(pub_pem.decode())


# ── issue ─────────────────────────────────────────────────────────────────────

def cmd_issue(args: argparse.Namespace) -> None:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    if not PRIVATE_KEY_PATH.exists():
        print(f"ERREUR : {PRIVATE_KEY_PATH} introuvable. Lancez : python gen_license.py keygen")
        sys.exit(1)

    priv = load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)

    payload: dict = {
        "e": args.email,
        "p": args.plan,
        "m": args.machines,
    }
    if args.expires:
        payload["x"] = args.expires
    if args.machine_ids:
        payload["i"] = [mid.strip() for mid in args.machine_ids.split(",")]

    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    payload_b64   = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    sig_b64       = base64.urlsafe_b64encode(priv.sign(payload_bytes)).rstrip(b"=").decode()

    license_key = f"{payload_b64}.{sig_b64}"

    print(f"\nClé de licence pour {args.email} :")
    print(f"\n  {license_key}\n")
    print(f"Plan      : {args.plan}")
    print(f"Machines  : {args.machines}")
    print(f"Expiration : {args.expires or 'jamais (à vie)'}")
    if args.machine_ids:
        print(f"IDs machine : {args.machine_ids}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lumina Control — outil de gestion des licences",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # keygen
    kg = sub.add_parser("keygen", help="Générer une paire de clés Ed25519")
    kg.add_argument("--force", action="store_true", help="Écraser les clés existantes")

    # issue
    iss = sub.add_parser("issue", help="Émettre une clé de licence signée")
    iss.add_argument("--email",       required=True,           help="Email du client")
    iss.add_argument("--plan",        default="pro",           choices=["pro", "lifetime"])
    iss.add_argument("--machines",    type=int, default=2,     help="Nb machines (informatif)")
    iss.add_argument("--expires",     default=None,            help="Expiration YYYY-MM-DD")
    iss.add_argument("--machine-ids", default=None, dest="machine_ids",
                     help="IDs machine séparés par virgules (liaison stricte)")

    args = parser.parse_args()
    {"keygen": cmd_keygen, "issue": cmd_issue}[args.cmd](args)


if __name__ == "__main__":
    main()
