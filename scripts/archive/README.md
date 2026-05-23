# Scripts archivés

Ces scripts ont été remplacés par d'autres approches et ne doivent plus
être lancés. Conservés en repo pour historique.

## clean_cached_plans.py.deprecated

**Période d'utilité** : 2026-05-22 → 2026-05-23 matin.

**Remplacé par** : génération propre via `scripts/precalc_plans.py` une
fois l'agent live aligné avec le nouveau system prompt (B-013 résolu).

**Pourquoi archivé** : faisait du strip regex post-hoc sur les plans
générés par l'ancienne version du system prompt agent. Solution dégradée
qui produisait des phrasings cassés ("Source : INIES, Source : base
INIES — numéro à confirmer"). La regen live via precalc avec le nouveau
prompt produit directement un texte propre.

NE PAS RELANCER ce script — il dégraderait des plans déjà propres.
