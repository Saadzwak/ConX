"""ConX — test roundtrip RLS sur Supabase Cloud.

Pré-requis : la migration `scripts/sql/supabase/001_app_schema.sql` doit avoir
été appliquée (cf. SUPABASE_MIGRATION.md).

Le test :
1. Crée 2 utilisateurs test via auth.admin.create_user (service_role).
2. Génère 2 JWTs (un par user) en HS256 avec SUPABASE_JWT_SECRET.
3. Crée un client supabase-py "user A" propageant son JWT.
4. INSERT app.renovation_plans pour user A → doit réussir.
5. SELECT depuis le client "user B" → doit voir 0 lignes (RLS isole).
6. SELECT depuis "user A" → doit voir 1 ligne (le sien).
7. UPDATE depuis "user B" sur le plan de A → doit échouer / 0 lignes touchées.
8. DELETE depuis "user A" sur son propre plan → doit réussir.
9. Cleanup : delete 2 users via service_role.

Usage :
    python scripts/supabase_rls_roundtrip.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
import uuid
from pathlib import Path

import jwt as pyjwt

ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("rls_roundtrip")


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.split("#", 1)[0].strip())


def _make_user_jwt(user_id: str, secret: str, email: str) -> str:
    now = int(time.time())
    return pyjwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iat": now,
            "exp": now + 3600,
        },
        secret,
        algorithm="HS256",
    )


def main() -> int:
    _load_env()
    try:
        from supabase import create_client
    except ImportError:
        logger.error("supabase non installé : `pip install supabase==2.10.0`")
        return 2

    url = os.environ["SUPABASE_URL"]
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    jwt_secret = os.environ["SUPABASE_JWT_SECRET"]

    admin = create_client(url, service_key)
    logger.info("Client admin (service_role) créé.")

    # 1. Création de 2 users test
    test_email_a = f"test-a-{uuid.uuid4().hex[:8]}@conx.test"
    test_email_b = f"test-b-{uuid.uuid4().hex[:8]}@conx.test"
    pw = "ConX-Test-" + uuid.uuid4().hex

    user_a = admin.auth.admin.create_user({"email": test_email_a, "password": pw, "email_confirm": True})
    user_b = admin.auth.admin.create_user({"email": test_email_b, "password": pw, "email_confirm": True})
    uid_a = user_a.user.id
    uid_b = user_b.user.id
    logger.info("User A créé : %s (%s)", uid_a, test_email_a)
    logger.info("User B créé : %s (%s)", uid_b, test_email_b)

    # 2. Génération des JWTs
    jwt_a = _make_user_jwt(uid_a, jwt_secret, test_email_a)
    jwt_b = _make_user_jwt(uid_b, jwt_secret, test_email_b)

    # 3. Clients per-user
    sb_a = create_client(url, os.environ["SUPABASE_ANON_KEY"])
    sb_a.postgrest.auth(jwt_a)
    sb_b = create_client(url, os.environ["SUPABASE_ANON_KEY"])
    sb_b.postgrest.auth(jwt_b)

    # Préparer une session bidon pour FK (renovation_plans → agent_sessions)
    sess_id = f"test-ses-{uuid.uuid4().hex[:12]}"
    sb_a.schema("app").table("agent_sessions").insert({
        "session_id": sess_id, "agent_name": "conx-plan",
        "user_id": uid_a, "user_query": "test roundtrip", "building_id": "test-bld-1",
    }).execute()

    # 4. INSERT plan pour A
    plan_id = str(uuid.uuid4())
    insert_res = sb_a.schema("app").table("renovation_plans").insert({
        "id": plan_id, "building_id": "test-bld-1", "session_id": sess_id,
        "user_id": uid_a, "version": 1,
        "plan_json": {"strategie": "test", "materiaux": ["chanvre"]},
        "carbon_t_total": -12.3,
    }).execute()
    assert insert_res.data, "INSERT A a échoué"
    logger.info("✓ INSERT plan v1 pour A OK (id=%s)", plan_id)

    # 5. SELECT depuis B → doit retourner 0 lignes (RLS)
    sel_b = sb_b.schema("app").table("renovation_plans").select("id").eq("id", plan_id).execute()
    if sel_b.data:
        logger.error("❌ RLS CASSÉE : B peut lire le plan de A : %s", sel_b.data)
        return 5
    logger.info("✓ B ne voit PAS le plan de A (RLS isole).")

    # 6. SELECT depuis A → doit retourner 1 ligne
    sel_a = sb_a.schema("app").table("renovation_plans").select("id, carbon_t_total").eq("id", plan_id).execute()
    assert sel_a.data and len(sel_a.data) == 1, f"A ne voit pas son plan : {sel_a.data}"
    logger.info("✓ A voit son plan : %s", sel_a.data[0])

    # 7. UPDATE depuis B sur le plan de A → doit toucher 0 lignes
    upd_b = sb_b.schema("app").table("renovation_plans").update({"carbon_t_total": 999}).eq("id", plan_id).execute()
    if upd_b.data:
        logger.error("❌ RLS CASSÉE : B a modifié le plan de A : %s", upd_b.data)
        return 6
    logger.info("✓ UPDATE depuis B sur plan A : 0 ligne touchée.")

    # Vérif que la valeur n'a pas changé
    sel_a2 = sb_a.schema("app").table("renovation_plans").select("carbon_t_total").eq("id", plan_id).execute()
    assert sel_a2.data[0]["carbon_t_total"] == -12.3, f"Valeur modifiée par B (RLS cassée) : {sel_a2.data}"
    logger.info("✓ Valeur carbon_t_total inchangée côté A.")

    # 8. DELETE depuis A → OK
    del_a = sb_a.schema("app").table("renovation_plans").delete().eq("id", plan_id).execute()
    assert del_a.data, "DELETE par A a échoué"
    logger.info("✓ DELETE plan par A OK.")

    # Cleanup session bidon
    sb_a.schema("app").table("agent_sessions").delete().eq("session_id", sess_id).execute()

    # 9. Cleanup users
    admin.auth.admin.delete_user(uid_a)
    admin.auth.admin.delete_user(uid_b)
    logger.info("✓ Users test supprimés.")

    logger.info("🎉 RLS roundtrip PASS — l'isolation user_id fonctionne.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
