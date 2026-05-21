#!/usr/bin/env bash
# ConX — téléchargement asynchrone des départements BDNB.
# Lit les URLs depuis scripts/bdnb_urls.txt (format : <dept> <url> par ligne).
# Reprenable (curl -C -), 3 retries par dpt, marker .done.
#
# Usage :
#   bash scripts/download_bdnb.sh                # tous les départements du fichier
#   bash scripts/download_bdnb.sh 59             # un seul département
#
# Sortie : ./data/raw/bdnb/<dept>/<filename>.zip (+ .done marker)
# Log    : redirection conseillée vers ./data/raw/bdnb/download.log

set -uo pipefail

URLS_FILE="scripts/bdnb_urls.txt"
DEST_DIR="./data/raw/bdnb"
RETRIES=3
SELECTED_DEPT="${1:-}"

mkdir -p "$DEST_DIR"

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }

if [[ ! -f "$URLS_FILE" ]]; then
    log "❌ Fichier $URLS_FILE introuvable."
    exit 1
fi

# Parse le fichier : lignes "dept url", ignore commentaires et lignes vides.
FAILED_DEPTS=()
TOTAL=0
SUCCESS=0
SKIPPED=0

while IFS= read -r line; do
    # Skip commentaires et vides
    line="${line%%#*}"
    line="$(echo "$line" | xargs)"
    [[ -z "$line" ]] && continue

    dept="$(echo "$line" | awk '{print $1}')"
    url="$(echo "$line" | awk '{print $2}')"

    if [[ -z "$dept" || -z "$url" ]]; then
        log "⚠️  Ligne malformée ignorée : $line"
        continue
    fi

    # Filtre éventuel par département
    if [[ -n "$SELECTED_DEPT" && "$dept" != "$SELECTED_DEPT" ]]; then
        continue
    fi

    TOTAL=$((TOTAL + 1))
    dept_dir="$DEST_DIR/$dept"
    mkdir -p "$dept_dir"
    filename=$(basename "$url")
    dest="$dept_dir/$filename"

    if [[ -f "$dest.done" ]]; then
        log "✅ $dept déjà téléchargé : $dest"
        SKIPPED=$((SKIPPED + 1))
        SUCCESS=$((SUCCESS + 1))
        continue
    fi

    log "⬇️  Téléchargement $dept depuis $url"
    attempt=0
    success=0
    while (( attempt < RETRIES )); do
        attempt=$((attempt + 1))
        if curl -fL -C - --connect-timeout 30 --max-time 7200 \
                -o "$dest" "$url" \
                --progress-bar 2>&1; then
            touch "$dest.done"
            log "✅ $dept terminé (tentative $attempt) : $dest ($(du -h "$dest" | cut -f1))"
            success=1
            SUCCESS=$((SUCCESS + 1))
            break
        else
            log "⚠️  $dept échec tentative $attempt/$RETRIES"
            sleep $((attempt * 5))
        fi
    done

    if (( success == 0 )); then
        log "❌ $dept abandonné après $RETRIES tentatives"
        FAILED_DEPTS+=("$dept")
    fi
done < "$URLS_FILE"

log "─────────────────────────────────────────────"
log "Bilan : $SUCCESS/$TOTAL téléchargés ($SKIPPED déjà présents)"
if (( ${#FAILED_DEPTS[@]} > 0 )); then
    log "❌ Échecs : ${FAILED_DEPTS[*]}"
    exit 2
fi
log "✅ Tous les départements demandés sont téléchargés."
