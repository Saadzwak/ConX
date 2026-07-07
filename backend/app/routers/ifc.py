"""ConX — endpoints `/api/ifc/*` Mode Conformité (J13).

Workflow :
1. Frontend upload .ifc via `POST /api/ifc/upload` (multipart form-data).
2. Backend sauvegarde dans `./data/storage/ifc/<user_id>/<uuid>.ifc`.
3. Backend exécute `ifc/validator.py validate_ifc()` (IfcOpenShell + règles
   RE2020/PMR statiques).
4. Backend génère le PDF via `ifc/pdf.py render_pdf()` dans
   `./data/storage/pdf/<user_id>/<uuid>.pdf`.
5. Insertion dans `app.ifc_validations` (Supabase, RLS).
6. Retourne `{validation_id, rapport_json, pdf_url}`.

⚠ Étape "Agent Conformité" (Anthropic) facultative en J13 : la pré-vérif
locale + le PDF suffisent pour la démo. L'agent (qui humanise le rapport)
sera ajouté en J17 si le partenaire le souhaite (~0.10-0.20 € par validation).

Limites MVP (cf. docs/IFC.md) : 10-15 contrôles, pas de validation
géométrique 3D, IFC2x3/IFC4/IFC4.3 supportés.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..auth import AuthUser, get_current_user
from ..ifc.pdf import render_pdf
from ..ifc.validator import validate_ifc
from ..supabase_client import is_supabase_configured, supabase_for_user

logger = logging.getLogger("conx.routers.ifc")

router = APIRouter(prefix="/api/ifc", tags=["ifc"])

STORAGE_ROOT = Path(os.environ.get("DATA_STORAGE_PATH", "/app/data/storage"))
IFC_DIR = STORAGE_ROOT / "ifc"
PDF_DIR = STORAGE_ROOT / "pdf"

MAX_IFC_SIZE_BYTES = 200 * 1024 * 1024  # 200 Mo — un IFC de bâtiment HDF tient large
ALLOWED_EXTS = {".ifc", ".ifczip"}


# ---------------------------------------------------------------------------
# Schémas
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    validation_id: str  # uuid app.ifc_validations
    ifc_filename: str
    rapport_json: dict[str, Any]
    pdf_url: str  # /api/ifc/pdf/<validation_id>
    re2020_pass: bool | None
    pmr_pass: bool | None


class ValidationListItem(BaseModel):
    id: str
    ifc_filename: str
    re2020_pass: bool | None
    pmr_pass: bool | None
    created_at: str
    pdf_url: str


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _validate_extension(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Extension {ext!r} non supportée. Attendu : {sorted(ALLOWED_EXTS)}",
        )


def _summarize_pass(checks: dict[str, Any]) -> bool | None:
    """True si tous les contrôles passent. None si dict vide (parse error)."""
    if not checks:
        return None
    return all(bool(v.get("pass")) for v in checks.values() if isinstance(v, dict))


async def _persist_validation(
    user: AuthUser,
    validation_id: str,
    ifc_filename: str,
    ifc_path: Path,
    rapport: dict[str, Any],
    pdf_path: Path,
    re2020_pass: bool | None,
    pmr_pass: bool | None,
) -> None:
    """Insert dans `app.ifc_validations` Supabase. No-op si Supabase non
    configuré (mode dev offline)."""
    if not is_supabase_configured():
        logger.warning(
            "Supabase non configuré — validation %s pas persistée côté cloud.",
            validation_id,
        )
        return
    sb = supabase_for_user(user)
    # supabase-py = httpx sync → offload hors event loop (AUDIT C3).
    await asyncio.to_thread(
        lambda: sb.schema("app")
        .table("ifc_validations")
        .insert(
            {
                "id": validation_id,
                "user_id": user.user_id,
                "ifc_filename": ifc_filename,
                "ifc_path_local": str(ifc_path),
                "re2020_pass": re2020_pass,
                "pmr_pass": pmr_pass,
                "rapport_pdf_path_local": str(pdf_path),
                "rapport_json": rapport,
            }
        )
        .execute()
    )


# ---------------------------------------------------------------------------
# POST /api/ifc/upload
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=UploadResponse)
async def upload_ifc(
    request: Request,
    user: Annotated[AuthUser, Depends(get_current_user)],
    file: Annotated[UploadFile, File(description="Fichier .ifc à valider")],
) -> UploadResponse:
    """Upload un fichier IFC + validation locale + génération PDF.

    Auth requise (tout rôle valide). Le fichier est stocké dans
    `./data/storage/ifc/<user_id>/<uuid>.ifc` (volume Docker).

    Le pipeline complet (parse + validation + PDF) doit tenir en < 10 s
    pour un IFC de taille raisonnable (~50 Mo). Au-delà, on garde la requête
    synchrone — pas de file d'attente J13 (à voir si besoin J16).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier manquant.")
    _validate_extension(file.filename)

    max_mb = MAX_IFC_SIZE_BYTES // (1024 * 1024)

    # 1. Rejet précoce sur Content-Length (indicatif — un client hostile peut
    # mentir, d'où le recomptage en streaming ci-dessous). Cf. AUDIT M2.
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_IFC_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"Fichier > {max_mb} Mo.")

    # 2. Préparer les chemins (on écrit en streaming, jamais tout en RAM).
    validation_id = str(uuid.uuid4())
    user_ifc_dir = IFC_DIR / user.user_id
    user_pdf_dir = PDF_DIR / user.user_id
    user_ifc_dir.mkdir(parents=True, exist_ok=True)
    user_pdf_dir.mkdir(parents=True, exist_ok=True)
    ifc_path = user_ifc_dir / f"{validation_id}.ifc"
    pdf_path = user_pdf_dir / f"{validation_id}.pdf"

    # 3. Écriture par chunks avec garde de taille stricte (anti-DoS OOM :
    # on n'accumule jamais l'intégralité du fichier en mémoire). Cf. AUDIT M2.
    chunk_size = 1024 * 1024  # 1 Mo
    total = 0
    try:
        with ifc_path.open("wb") as fh:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_IFC_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail=f"Fichier > {max_mb} Mo.")
                fh.write(chunk)
    except HTTPException:
        ifc_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        ifc_path.unlink(missing_ok=True)
        logger.exception("Erreur écriture IFC")
        raise HTTPException(status_code=500, detail=f"Erreur écriture : {exc}") from exc

    if total == 0:
        ifc_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Fichier vide.")

    logger.info(
        "IFC uploadé par %s : %s → %s (%d bytes)",
        user.user_id,
        file.filename,
        ifc_path,
        total,
    )

    # 4. Valider via IfcOpenShell + règles MVP (CPU-bound C++ → offload hors
    # event loop pour ne pas geler le stream SSE et les autres requêtes, C3).
    try:
        rapport = await asyncio.to_thread(validate_ifc, ifc_path)
    except ImportError as exc:
        # ifcopenshell pas dispo dans le container — fallback graceful
        raise HTTPException(
            status_code=503,
            detail=f"IfcOpenShell indisponible côté backend : {exc}",
        ) from exc

    re2020_pass = _summarize_pass(rapport.get("re2020_checks") or {})
    pmr_pass = _summarize_pass(rapport.get("pmr_checks") or {})

    # 5. Générer le PDF (WeasyPrint CPU-bound → offload, C3)
    try:
        await asyncio.to_thread(render_pdf, rapport, pdf_path)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erreur génération PDF")
        raise HTTPException(status_code=500, detail=f"Erreur génération PDF : {exc}") from exc

    # 6. Persister côté Supabase (best-effort : la validation + le PDF ont
    # réussi, un échec de persistance ne doit pas perdre le résultat, M4)
    try:
        await _persist_validation(
            user,
            validation_id,
            file.filename,
            ifc_path,
            rapport,
            pdf_path,
            re2020_pass,
            pmr_pass,
        )
    except Exception as exc:
        logger.warning(
            "Persistance validation %s échouée (%s) — résultat renvoyé quand même.",
            validation_id,
            exc,
        )

    return UploadResponse(
        validation_id=validation_id,
        ifc_filename=file.filename,
        rapport_json=rapport,
        pdf_url=f"/api/ifc/pdf/{validation_id}",
        re2020_pass=re2020_pass,
        pmr_pass=pmr_pass,
    )


# ---------------------------------------------------------------------------
# GET /api/ifc/pdf/{validation_id}
# ---------------------------------------------------------------------------


@router.get("/pdf/{validation_id}")
async def download_pdf(
    validation_id: str,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> FileResponse:
    """Télécharge le PDF d'une validation appartenant à l'utilisateur."""
    # validation_id doit être un UUID : bloque le path traversal en mode dégradé
    # (le chemin disque est construit à partir de cette valeur). Cf. AUDIT C2/M2.
    try:
        uuid.UUID(validation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="validation_id invalide.") from exc

    # Ownership via RLS Supabase + filtre user_id explicite (défense en profondeur :
    # tient même si la RLS est bypassée par service_role). Cf. AUDIT C2.
    row: dict[str, Any] | None = None
    if is_supabase_configured():
        sb = supabase_for_user(user)
        try:
            res = await asyncio.to_thread(  # supabase-py sync → offload (C3)
                lambda: sb.schema("app")
                .table("ifc_validations")
                .select("rapport_pdf_path_local, ifc_filename")
                .eq("id", validation_id)
                .eq("user_id", user.user_id)
                .limit(1)
                .execute()
            )
            rows = res.data if hasattr(res, "data") else res.get("data", [])
        except Exception as exc:
            # Supabase injoignable → dégradation vers chemin par convention.
            logger.warning(
                "Ownership PDF %s indisponible (Supabase injoignable: %s) — "
                "chemin par convention (scopé au dossier de l'utilisateur).",
                validation_id,
                exc,
            )
            rows = None
        if rows is not None:
            if not rows:
                raise HTTPException(status_code=404, detail="Validation introuvable.")
            row = rows[0]

    if row is not None:
        pdf_path = Path(row["rapport_pdf_path_local"])
        ifc_filename = row["ifc_filename"]
    else:
        # Non configuré ou injoignable : chemin par convention. Scopé au dossier
        # de l'utilisateur (user_id issu de l'auth + validation_id validé UUID),
        # donc pas d'accès cross-utilisateur.
        pdf_path = PDF_DIR / user.user_id / f"{validation_id}.pdf"
        ifc_filename = f"{validation_id}.ifc"

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF introuvable sur disque.")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"conx_conformite_{Path(ifc_filename).stem}.pdf",
    )


# ---------------------------------------------------------------------------
# GET /api/ifc/validations  (historique utilisateur)
# ---------------------------------------------------------------------------


@router.get("/validations", response_model=list[ValidationListItem])
async def list_validations(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> list[ValidationListItem]:
    """Liste les validations de l'utilisateur (les plus récentes en tête)."""
    if not is_supabase_configured():
        return []
    sb = supabase_for_user(user)
    try:
        res = await asyncio.to_thread(  # supabase-py sync → offload (C3)
            lambda: sb.schema("app")
            .table("ifc_validations")
            .select("id, ifc_filename, re2020_pass, pmr_pass, created_at")
            .eq("user_id", user.user_id)  # défense en profondeur (AUDIT C2)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
    except Exception as exc:
        logger.warning("Liste validations indisponible (Supabase injoignable: %s).", exc)
        return []
    rows = res.data if hasattr(res, "data") else res.get("data", [])
    out: list[ValidationListItem] = []
    for r in rows:
        # created_at vient de Supabase au format ISO ; on relit / passe tel quel
        ca = r.get("created_at")
        if isinstance(ca, datetime):
            ca = ca.isoformat()
        elif not ca:
            ca = datetime.now(UTC).isoformat()
        out.append(
            ValidationListItem(
                id=r["id"],
                ifc_filename=r["ifc_filename"],
                re2020_pass=r.get("re2020_pass"),
                pmr_pass=r.get("pmr_pass"),
                created_at=ca,
                pdf_url=f"/api/ifc/pdf/{r['id']}",
            )
        )
    return out
