# ConX

Plateforme IA pour la rénovation énergétique hors-site décarbonée — Hauts-de-France.

> **Code propriétaire, données 100 % publiques** (BDNB CSTB, DPE ADEME, LiDAR HD IGN, BD TOPO IGN, BD Ortho IGN, BAN, INIES — Licence Ouverte Etalab 2.0).

## Documents projet

- [CLAUDE.md](CLAUDE.md) — source de vérité du projet
- [docs/SCORING.md](docs/SCORING.md) — formule de scoring déterministe
- [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) — sources de données et licences
- [DECISIONS.md](DECISIONS.md) — décisions techniques
- [BLOCKERS.md](BLOCKERS.md) — points en arbitrage
- [BUILD_LOG.md](BUILD_LOG.md) — journal de bord

## Démarrage local

```bash
cp .env.example .env
# Remplir .env avec les valeurs réelles

docker compose up
# Backend : http://localhost:8000/api/health
# Martin (tuiles MVT) : http://localhost:3000
```

## Vérifications J1

```bash
python scripts/verify_supabase_connection.py
bash scripts/download_bdnb.sh        # tâche de fond, reprenable (git-bash sur Windows OK)
```

---

Données : IGN (LiDAR HD, BD TOPO, BD Ortho), CSTB (BDNB), ADEME (DPE, Base Carbone), INIES (FDES), DGFiP (BAN) — Licence Ouverte Etalab 2.0.
