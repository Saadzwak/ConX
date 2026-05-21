"""ConX — mise à jour de l'URL du tunnel ngrok dans la config de l'Agent Sélection.

Lit NGROK_PUBLIC_URL depuis .env, met à jour la config de l'Agent Sélection côté Anthropic
afin que ses appels HTTP (web_fetch) pointent vers la bonne URL.

À relancer après chaque démarrage de ngrok (URL gratuite change à chaque session).

STUB J1 — implémentation complète à J10 (création des agents).
Pour l'instant, vérifie juste que les variables sont définies et affiche un message.

Usage :
    python scripts/update_tunnel_url.py
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    ngrok_url = os.environ.get("NGROK_PUBLIC_URL", "").strip()
    agent_selection_id = os.environ.get("AGENT_SELECTION_ID", "").strip()

    if not ngrok_url:
        print("❌ NGROK_PUBLIC_URL non défini dans .env")
        print("   Démarre ngrok : ngrok http 8000, puis copie l'URL https://...ngrok-free.app")
        return 1

    print(f"ℹ️  NGROK_PUBLIC_URL = {ngrok_url}")

    if not agent_selection_id:
        print("⚠️  AGENT_SELECTION_ID non défini — agents pas encore créés (J10).")
        print("   Stub J1 : pas de mise à jour Anthropic. À implémenter à J10.")
        return 0

    # TODO J10 : implémentation réelle
    #
    # from anthropic import Anthropic
    # client = Anthropic()
    # client.beta.agents.update(
    #     agent_selection_id,
    #     # Update du system prompt ou de la config web_fetch allowlist
    #     ...
    # )
    print(f"⚠️  Stub J1 : mise à jour Anthropic non implémentée (Agent ID = {agent_selection_id})")
    print("   À implémenter en J10 quand les agents seront créés.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
