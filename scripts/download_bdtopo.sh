#!/usr/bin/env bash
# ConX — téléchargement de la BD TOPO IGN par département (GPKG).
# Lit les URLs depuis scripts/bdtopo_urls.txt. À compléter avant lancement.
# Reprenable (curl -C -), 3 retries.
#
# Usage :
#   bash scripts/download_bdtopo.sh                # tous les départements
#   bash scripts/download_bdtopo.sh 59             # un seul département

set -uo pipefail

URLS_FILE="scripts/bdtopo_urls.txt"
DEST_DIR="./data/raw/bdtopo"
RETRIES=3
SELECTED_DEPT="${1:-}"

mkdir -p "$DEST_DIR"

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }

if [[ ! -f "$URLS_FILE" ]]; then
    log "❌ $URLS_FILE introuvable."
    exit 1
fi

FAILED=()
TOTAL=0
SUCCESS=0

while IFS= read -r line; do
    line="${line%%#*}"
    line="$(echo "$line" | xargs)"
    [[ -z "$line" ]] && continue

    dept=$(echo "$line" | awk '{print $1}')
    url=$(echo "$line" | awk '{print $2}')
    if [[ -z "$url" || "$url" == TODO_* ]]; then
        log "⚠️  URL manquante ou TODO pour dpt $dept — voir scripts/bdtopo_urls.txt"
        continue
    fi
    if [[ -n "$SELECTED_DEPT" && "$dept" != "$SELECTED_DEPT" ]]; then
        continue
    fi

    TOTAL=$((TOTAL + 1))
    dept_dir="$DEST_DIR/$dept"
    mkdir -p "$dept_dir"
    filename=$(basename "$url")
    dest="$dept_dir/$filename"

    if [[ -f "$dest.done" ]]; then
        log "✅ $dept déjà téléchargé"
        SUCCESS=$((SUCCESS + 1))
        continue
    fi

    log "⬇️  $dept depuis $url"
    attempt=0
    ok=0
    while (( attempt < RETRIES )); do
        attempt=$((attempt + 1))
        if curl -fL -C - --connect-timeout 30 --max-time 7200 -o "$dest" "$url" -s; then
            touch "$dest.done"
            log "✅ $dept terminé ($(du -h "$dest" | cut -f1))"
            ok=1
            SUCCESS=$((SUCCESS + 1))
            break
        else
            log "⚠️  $dept tentative $attempt/$RETRIES échouée"
            sleep $((attempt * 5))
        fi
    done
    (( ok == 0 )) && FAILED+=("$dept")

done < "$URLS_FILE"

log "Bilan : $SUCCESS/$TOTAL téléchargés"
(( ${#FAILED[@]} > 0 )) && { log "❌ Échecs : ${FAILED[*]}"; exit 2; }
