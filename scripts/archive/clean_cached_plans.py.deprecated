"""Strip internal jargon from cached plan JSONs.

Saad's rule (cf. CHANTIER 2 du brief 2026-05-23) : pas de mention de skills
internes / catalogues privés / numéros FDES inventés dans les livrables.

Transformations appliquées en place sur les 3 plans cachés :
- "TBC-J9" / "TBC-JX" → "" (et nettoyage du fragment phrase autour)
- "catalogue horssite-biosource §N" → "documentation hors-site biosourcée"
- "logique cible re2020-target" → "logique cible RE2020"
- "carbon-calc / fdes-lookup / pmr-checks / ifc-check" → références indirectes
- "base ConX consultée le …" → "base INIES"
- "cf. catalogue ConX" → "documentation hors-site"

Idempotent : ré-exécuter laisse le fichier inchangé après la première passe.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent

PATTERNS: list[tuple[str, str]] = [
    # FDES placeholders type "TBC-J9"
    (
        r"\(base ConX consult[eé]e le \d{4}-\d{2}-\d{2}\)\s*",
        "",
    ),
    (
        r"FDES n[°ºo]\s*TBC[-_]?J?\d+",
        "Source : base INIES",
    ),
    (
        r"INIES n[°ºo]\s*TBC[-_]?J?\d+",
        "base INIES",
    ),
    (
        r"INIES,?\s*FDES n[°ºo]\s*TBC[-_]?J?\d+",
        "base INIES",
    ),
    (
        r"num[eé]ro[s]?\s+FDES\s*[`']?TBC[-_]?J?\d+[`']?",
        "numéros FDES",
    ),
    (
        r"num[eé]ros\s+FDES\s*`?TBC[-_]?J?\d+`?",
        "numéros FDES",
    ),
    # Mentions de skills internes
    (
        r"\(cf\.?\s*catalogue\s+horssite-biosource\s*§\s*\d+\)",
        "(approche hors-site biosourcée standard)",
    ),
    (
        r"catalogue\s+horssite-biosource(\s*§\s*\d+)?",
        "documentation hors-site biosourcée",
    ),
    # skill `horssite-biosource` (avec backticks)
    (
        r"skill\s*`?horssite-biosource`?(\s*§[^.)]*)?",
        "documentation hors-site biosourcée",
    ),
    (
        r"`horssite-biosource`(\s*§[^.)]*)?",
        "documentation hors-site biosourcée",
    ),
    (
        r"\(horssite-biosource\s*§[^)]+\)",
        "(approche hors-site biosourcée)",
    ),
    (
        r"horssite-biosource(\s*§[^.,)]*)?",
        "documentation hors-site biosourcée",
    ),
    # CARBON.md / SKILL.md
    (
        r"CARBON\.md(\s*§\s*\d+)?",
        "méthodologie carbone ConX",
    ),
    (
        r"SKILL\.md",
        "documentation ConX",
    ),
    (
        r"limite\s+\*\*B-\d+\*\*\s+signal[eé]e\s+dans\s+la\s+documentation\s+ConX",
        "limite signalée dans la méthodologie ConX",
    ),
    (
        r"limit[eé]\s+B-\d+",
        "",
    ),
    (
        r"logique\s+cible\s+re2020-target",
        "cible RE2020 réglementaire",
    ),
    (
        r"re2020-target\s*§[«»\"'A-Za-z\s\d_-]+(?:»|\"|')?",
        "indicateurs RE2020",
    ),
    (
        r"re2020-target",
        "RE2020",
    ),
    (
        r"cf\.?\s*carbon-calc[A-Za-z\s.,§\d_-]*",
        "calcul carbone déterministe (méthodologie ConX)",
    ),
    (
        r"carbon-calc\.SKILL\.md\s*§\d+",
        "méthodologie ConX",
    ),
    (
        r"carbon-calc\s+SKILL\.md\s*§\d+",
        "méthodologie ConX",
    ),
    (
        r"\(cf\.?\s*carbon-calc\b[^)]*\)",
        "",
    ),
    (
        r"carbon-calc",
        "calcul carbone ConX",
    ),
    (
        r"fdes-lookup",
        "base FDES INIES",
    ),
    (
        r"pmr-checks",
        "règles PMR",
    ),
    (
        r"ifc-check",
        "validation IFC",
    ),
    # "base ConX 30 matériaux" → "base FDES INIES"
    (
        r"INIES\s+\(?base\s+ConX\s+30\s+mat[eé]riaux\)?",
        "base INIES (FDES publique)",
    ),
    (
        r"base\s+ConX\s+30\s+mat[eé]riaux",
        "base FDES INIES",
    ),
    (
        r"base\s+ConX",
        "base INIES",
    ),
    # Mention CARBON.md interne
    (
        r"convention signes CARBON\.md\s*§\d+",
        "convention signes RE2020 (incorporé algébrique, NET négatif = vertueux)",
    ),
    # Nettoyer numéros TBC restants
    (
        r"\bTBC[-_]J?\d+\b",
        "",
    ),
    # Espaces multiples laissés par les remplacements — ATTENTION : ne pas
    # toucher aux sauts de ligne (markdown les utilise pour séparer
    # paragraphes/listes/blockquotes). On limite à [ \t]+.
    (r"[ \t]+,", ","),
    (r"\(\s*\)", ""),
    (r"[ \t]{2,}", " "),
    (r" \.\s*\)", ".)"),
]


def clean_text(text: str) -> str:
    for pat, repl in PATTERNS:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)
    return text


PREAMBULE = (
    "> Ce pré-cadrage propose une **approche modulaire** : chaque lot "
    "(ITE, toiture, menuiseries, systèmes, ventilation) peut être ajusté "
    "indépendamment. Vous pouvez itérer en chat avec ConX pour affiner les "
    "choix techniques, et exporter ce pré-cadrage en PDF à tout moment.\n\n"
)


def inject_preambule(text: str) -> str:
    """Insère le préambule juste après la première ligne titre (## …)
    si non déjà présent.

    Idempotent : ne réinjecte pas si l'incipit "approche modulaire" est
    déjà détecté dans les 800 premiers caractères.
    """
    if "approche modulaire" in text[:800].lower():
        return text
    # Trouver la fin de la ligne 1 (titre H2) puis les éventuelles lignes
    # italiques / blockquotes existantes (>) jusqu'au premier "---" ou ligne
    # vide.
    lines = text.split("\n", 1)
    if len(lines) < 2 or not lines[0].startswith("## "):
        # Pas de header H2 reconnaissable, on injecte tout en haut.
        return PREAMBULE + text
    # Cherche un séparateur "---" ou une ligne vide pour insérer le
    # préambule juste avant la première section "###".
    head, rest = lines[0], lines[1]
    # On insère après l'éventuelle ligne sous-titre italique
    sub_lines = rest.split("\n")
    insert_at = 0
    for i, ln in enumerate(sub_lines[:4]):
        s = ln.strip()
        if s.startswith("*") or s.startswith(">") or s == "":
            insert_at = i + 1
        else:
            break
    inserted = "\n".join(sub_lines[:insert_at]) + "\n\n" + PREAMBULE + "\n".join(sub_lines[insert_at:])
    return head + "\n" + inserted


def process_file(path: Path) -> tuple[int, int]:
    """Retourne (old_len, new_len) du plan_text."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if "plan_text" not in data:
        print(f"  ! {path.name}: pas de clé plan_text, skip")
        return (0, 0)
    old = data["plan_text"]
    new = clean_text(old)
    new = inject_preambule(new)
    if old == new:
        print(f"  = {path.name}: déjà clean ({len(old)} chars)")
        return (len(old), len(new))
    data["plan_text"] = new
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] {path.name}: {len(old)} -> {len(new)} chars")
    return (len(old), len(new))


def main() -> int:
    targets = [
        REPO / "docs" / "demo_assets" / "cached_plans",
        REPO / "data" / "storage" / "cached_plans",
    ]
    total_files = 0
    for d in targets:
        if not d.exists():
            print(f"Skip {d} (n'existe pas)")
            continue
        print(f"\n# {d.relative_to(REPO)}")
        for p in sorted(d.glob("*.json")):
            process_file(p)
            total_files += 1
    print(f"\n{total_files} fichier(s) traité(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
