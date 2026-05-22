"""ConX — module IFC backend (J13).

Réutilise la skill `skills/ifc-check/ifc_validator.py` qui contient la logique
de validation. Le backend en a besoin localement parce que l'upload se fait
côté backend (pas dans le sandbox Anthropic), et la pré-vérification doit
tourner rapidement pour donner un retour < 10 s à l'utilisateur.

L'Agent Conformité (Anthropic) recevra ensuite le JSON résultant comme
contexte et générera le rapport humanisé + analyse.
"""
