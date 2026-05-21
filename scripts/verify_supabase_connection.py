"""ConX — vérification de la connexion à l'instance Supabase existante (J1).

Lit les variables d'environnement (SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
SUPABASE_JWT_SECRET) et effectue 4 vérifications NON destructives :

1. Variables d'env présentes et non vides.
2. SUPABASE_URL répond en HTTPS sur /auth/v1/health.
3. Clés JWT décodables (format JWT valide, sans vérification crypto).
4. Service role key peut lister les utilisateurs auth (read-only, premier batch).

N'écrit rien dans Supabase. À relancer chaque fois que les credentials changent.

Usage :
    python scripts/verify_supabase_connection.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
from typing import Any

import httpx

REQUIRED_ENVS = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET",
]


def _check(label: str, condition: bool, detail: str = "") -> bool:
    icon = "✅" if condition else "❌"
    print(f"{icon} {label}" + (f" — {detail}" if detail else ""))
    return condition


def decode_jwt_unsafe(token: str) -> dict[str, Any] | None:
    """Décode un JWT sans vérifier la signature (uniquement pour inspection format)."""
    try:
        _header_b64, payload_b64, _sig_b64 = token.split(".")
        # padding base64
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None


def main() -> int:
    print("ConX — vérification connexion Supabase (J1)")
    print("─" * 60)

    # 1. Variables d'env
    missing = [k for k in REQUIRED_ENVS if not os.environ.get(k)]
    if not _check(
        "Variables d'environnement présentes",
        not missing,
        detail=("manquantes : " + ", ".join(missing)) if missing else "",
    ):
        print("\nRemplis ton .env à partir de .env.example.")
        return 1

    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    jwt_secret = os.environ["SUPABASE_JWT_SECRET"]

    # 2. Endpoint Supabase joignable
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(
                f"{supabase_url}/auth/v1/health", headers={"apikey": anon_key}
            )
        _check(
            f"Endpoint Supabase joignable ({supabase_url})",
            r.status_code in (200, 404),  # 404 acceptable selon le tier
            detail=f"HTTP {r.status_code}",
        )
    except httpx.HTTPError as e:
        _check(f"Endpoint Supabase joignable ({supabase_url})", False, detail=str(e))
        return 1

    # 3. JWT keys décodables
    anon_payload = decode_jwt_unsafe(anon_key)
    service_payload = decode_jwt_unsafe(service_key)
    _check(
        "SUPABASE_ANON_KEY a un format JWT valide",
        anon_payload is not None and anon_payload.get("role") == "anon",
        detail=f"role={anon_payload.get('role') if anon_payload else 'INVALID'}",
    )
    _check(
        "SUPABASE_SERVICE_ROLE_KEY a un format JWT valide",
        service_payload is not None and service_payload.get("role") == "service_role",
        detail=f"role={service_payload.get('role') if service_payload else 'INVALID'}",
    )
    _check(
        "SUPABASE_JWT_SECRET défini (non vide, longueur ≥ 32)",
        len(jwt_secret) >= 32,
        detail=f"longueur={len(jwt_secret)}",
    )

    # 4. Lecture admin (auth users, read-only)
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(
                f"{supabase_url}/auth/v1/admin/users?per_page=1",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
            )
        ok = r.status_code == 200
        detail = f"HTTP {r.status_code}"
        if ok:
            data = r.json()
            user_count = len(data.get("users", [])) if isinstance(data, dict) else 0
            detail += f", {user_count} utilisateur(s) lus (sans modification)"
        _check("Service role key fonctionne (admin/users lecture)", ok, detail=detail)
        if not ok:
            print(f"   → réponse : {r.text[:200]}")
            return 1
    except httpx.HTTPError as e:
        _check("Service role key fonctionne", False, detail=str(e))
        return 1

    print("─" * 60)
    print("✅ Connexion Supabase OK. Aucune donnée modifiée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
