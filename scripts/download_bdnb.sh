#!/usr/bin/env bash
# ConX — téléchargement asynchrone des 5 départements BDNB Hauts-de-France.
# Lancé en tâche de fond à J1, reprenable si interrompu (curl -C -).
#
# Usage :
#   ./scripts/download_bdnb.sh                # télécharge tous les départements manquants
#   ./scripts/download_bdnb.sh 59             # un seul département
#
# Sortie : ./data/raw/bdnb/<dept>/bdnb_2025-07-a_<dept>.gpkg (ou .sql.gz selon dispo)
#
# IMPORTANT : les URLs de téléchargement direct ne sont pas encore figées dans ce script.
# Premier run : repérage manuel sur https://bdnb.io/download/ puis remplir le tableau URLS.

set -euo pipefail

MILLESIME="2025-07-a"
DEPTS="${1:-59 62 80 60 02}"
DEST_DIR="./data/raw/bdnb"
mkdir -p "$DEST_DIR"

# TODO J1 : remplir avec les URLs exactes après visite https://bdnb.io/download/
# Format attendu : URL pointant vers un GPKG ou pgdump du dpt pour le millésime ${MILLESIME}.
declare -A URLS=(
    [59]=""
    [62]=""
    [80]=""
    [60]=""
    [02]=""
)

log() { echo "[$(date +'%H:%M:%S')] $*"; }

for dept in $DEPTS; do
    url="${URLS[$dept]:-}"
    if [[ -z "$url" ]]; then
        log "⚠️  URL non définie pour le département $dept — édite scripts/download_bdnb.sh"
        continue
    fi

    dept_dir="$DEST_DIR/$dept"
    mkdir -p "$dept_dir"
    filename=$(basename "$url")
    dest="$dept_dir/$filename"

    if [[ -f "$dest.done" ]]; then
        log "✅ $dept déjà téléchargé : $dest"
        continue
    fi

    log "⬇️  Téléchargement $dept depuis $url"
    # -C - pour reprise si interrompu
    if curl -fsSL -C - -o "$dest" "$url"; then
        touch "$dest.done"
        log "✅ $dept terminé : $dest"
    else
        log "❌ Échec $dept — relance le script pour reprendre"
        exit 1
    fi
done

log "Téléchargement BDNB terminé."
