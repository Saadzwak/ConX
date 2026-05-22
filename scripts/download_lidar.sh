#!/usr/bin/env bash
# ConX — J8 : téléchargement d'une dalle LiDAR HD IGN pour un bâtiment donné.
#
# Plan §2.4 + D-008. Téléchargement à la demande (LAZ ~ 100 MB - 2 GB / dalle).
# La dalle 1 km x 1 km est nommée selon le format IGN :
#   LHD_FXX_<XKM>_<YKM>_PTS_C_LAMB93_IGN69.copc.laz
# où XKM, YKM sont les coords km du coin Sud-Ouest en Lambert-93.
#
# Usage :
#   scripts/download_lidar.sh <building_id>
#   scripts/download_lidar.sh --dalle <dalle_name>
#   scripts/download_lidar.sh --bbox <xmin>,<ymin>,<xmax>,<ymax>
#
# Pré-requis :
#   - bâtiment existant dans public_data.buildings AVEC centroid en Lambert-93
#   - psql accessible via POSTGRES_LOCAL_* env vars
#   - curl pour le download (reprenable via curl -C -)
#
# Source IGN : https://geoservices.ign.fr/lidarhd
# Index dalles : https://diffusion-lidarhd.ign.fr/ressources/Liste_dalle_LAZ_HD.csv
#
# NB : ce script est paramétrable. La couverture LiDAR HD France n'est pas complète
# (dpts livrés progressivement 2021-2026). Pour HDF : 59/62 livrés ; 02/60/80 à vérifier
# au moment du téléchargement sur https://macarte.ign.fr/.

set -euo pipefail

STORAGE_DIR="${STORAGE_DIR:-./data/storage/lidar}"
PG_USER="${POSTGRES_LOCAL_USER:-conx}"
PG_DB="${POSTGRES_LOCAL_DB:-conx}"
PG_PORT_HOST="${POSTGRES_LOCAL_PORT_HOST:-5433}"
PG_PWD="${POSTGRES_LOCAL_PASSWORD:?POSTGRES_LOCAL_PASSWORD non défini}"
PG_HOST="${PG_HOST:-localhost}"

# Endpoint IGN — l'URL exacte a changé plusieurs fois 2022-2025 (entrepot-lidarhd-pcrs,
# diffusion-lidarhd, Géoplateforme…). Pas de valeur par défaut → fail-fast jusqu'à
# confirmation partenaire (B-008). À renseigner via .env :
#   IGN_LIDAR_URL=https://...../data
IGN_BASE_URL="${IGN_LIDAR_URL:?IGN_LIDAR_URL non défini — vérifier l'URL courante du CDN LiDAR HD sur https://geoservices.ign.fr/lidarhd et la mettre dans .env (cf. B-008)}"

usage() {
    echo "Usage:"
    echo "  $0 <building_id>"
    echo "  $0 --dalle <dalle_name>"
    echo "  $0 --bbox <xmin>,<ymin>,<xmax>,<ymax>"
    exit 1
}

[ $# -lt 1 ] && usage

# Détermine la dalle cible (1 km x 1 km Lambert-93)
case "${1:-}" in
    --dalle)
        DALLE="$2"
        ;;
    --bbox)
        # bbox xmin,ymin,xmax,ymax (Lambert-93). Calcule le coin SW arrondi au km
        IFS=',' read -r XMIN YMIN XMAX YMAX <<< "$2"
        XKM=$(( ${XMIN%.*} / 1000 ))
        YKM=$(( (${YMIN%.*} / 1000) + 1 ))   # IGN nomme par coin Nord
        DALLE="LHD_FXX_$(printf '%04d' $XKM)_$(printf '%04d' $YKM)_PTS_C_LAMB93_IGN69.copc.laz"
        ;;
    *)
        BUILDING_ID="$1"
        echo "Localisation du bâtiment $BUILDING_ID via PostGIS..."
        # Récupère le centroïde Lambert-93 du bâtiment
        COORDS=$(PGPASSWORD="$PG_PWD" psql -h "$PG_HOST" -p "$PG_PORT_HOST" -U "$PG_USER" -d "$PG_DB" -tA -c "
            SELECT ST_X(centroid)::int || ',' || ST_Y(centroid)::int
            FROM public_data.buildings
            WHERE building_id = '$BUILDING_ID';
        ")
        if [ -z "$COORDS" ]; then
            echo "ERREUR : bâtiment $BUILDING_ID introuvable."
            exit 2
        fi
        X_LAMB=${COORDS%,*}
        Y_LAMB=${COORDS#*,}
        XKM=$(( X_LAMB / 1000 ))
        YKM=$(( (Y_LAMB / 1000) + 1 ))  # IGN nomme par coin Nord
        DALLE="LHD_FXX_$(printf '%04d' $XKM)_$(printf '%04d' $YKM)_PTS_C_LAMB93_IGN69.copc.laz"
        echo "Bâtiment trouvé en ($X_LAMB, $Y_LAMB) Lambert-93 → dalle $DALLE"
        ;;
esac

mkdir -p "$STORAGE_DIR"
TARGET="$STORAGE_DIR/$DALLE"

if [ -f "$TARGET" ]; then
    echo "[skip] $TARGET existe déjà."
else
    URL="$IGN_BASE_URL/$DALLE"
    echo "Téléchargement : $URL"
    echo "       → $TARGET"
    if ! curl -fL --progress-bar -C - -o "$TARGET" "$URL"; then
        echo ""
        echo "ERREUR — téléchargement échoué. Causes probables :"
        echo "  1. URL IGN changée — vérifier https://geoservices.ign.fr/lidarhd"
        echo "     et l'endpoint réel sur https://macarte.ign.fr/data/lidar-hd/."
        echo "  2. Dalle non disponible (dpt pas encore livré par IGN)."
        echo "  3. Variable IGN_LIDAR_URL à régler dans .env."
        rm -f "$TARGET"
        exit 3
    fi
    echo "OK : $(stat --printf="%s" "$TARGET") bytes."
fi

# Insère la métadonnée dans public_data.lidar_tiles
PGPASSWORD="$PG_PWD" psql -h "$PG_HOST" -p "$PG_PORT_HOST" -U "$PG_USER" -d "$PG_DB" <<SQL
INSERT INTO public_data.lidar_tiles (dalle_name, emprise, ign_url, laz_path_local,
                                      laz_size_bytes, laz_downloaded_at)
VALUES (
    '$DALLE',
    ST_MakeEnvelope(${XKM:-0} * 1000, (${YKM:-1} - 1) * 1000,
                    (${XKM:-0} + 1) * 1000, ${YKM:-1} * 1000, 2154),
    '$IGN_BASE_URL/$DALLE',
    '$TARGET',
    $(stat --printf="%s" "$TARGET" 2>/dev/null || echo 0),
    now()
) ON CONFLICT (dalle_name) DO UPDATE SET
    laz_path_local = EXCLUDED.laz_path_local,
    laz_size_bytes = EXCLUDED.laz_size_bytes,
    laz_downloaded_at = EXCLUDED.laz_downloaded_at;
SQL

echo "Dalle indexée dans public_data.lidar_tiles."
echo ""
echo "Prochaine étape : convertir en mesh glTF via PDAL"
echo "  python scripts/lidar_to_gltf.py --dalle $DALLE [--building <id>]"
