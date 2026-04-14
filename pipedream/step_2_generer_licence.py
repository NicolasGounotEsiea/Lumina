"""
PIPEDREAM — Étape 2 : Générer la clé de licence Ed25519
"""
import base64
import json
import os
import re


def _fix_pem(raw: str) -> bytes:
    """Reconstruit un PEM Ed25519 valide depuis une string potentiellement malformée.
    Gère les cas : \\n littéraux, espaces à la place des sauts de ligne, tout sur une ligne.
    """
    # Normaliser les \n littéraux
    raw = raw.replace("\\n", "\n").replace("\\r", "")
    # Extraire le contenu base64 (entre les headers -----...-----)
    b64 = re.sub(r"-----[^-]+-----", "", raw)
    b64 = re.sub(r"\s+", "", b64)   # supprimer tout whitespace restant
    # Reformater : 64 caractères par ligne
    lines = [b64[i:i + 64] for i in range(0, len(b64), 64)]
    pem = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
    return pem.encode("utf-8")


def handler(pd: "pipedream"):
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    prev = pd.steps["code"]["$return_value"]
    if prev.get("skip"):
        return {"skip": True}

    email        = prev["email"]
    product_name = prev["product_name"]
    plan         = "lifetime" if "lifetime" in product_name.lower() else "pro"

    priv_pem = _fix_pem(os.environ["LUMINA_PRIVATE_KEY"])
    priv     = load_pem_private_key(priv_pem, password=None)

    payload     = json.dumps({"e": email, "p": plan, "m": 2}, separators=(",", ":")).encode()
    payload_b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    sig_b64     = base64.urlsafe_b64encode(priv.sign(payload)).rstrip(b"=").decode()

    return {
        "skip":        False,
        "license_key": f"{payload_b64}.{sig_b64}",
        "plan":        plan,
    }
