"""ConX — module ML estimation DPE (J5).

Random Forest classification (classe A-G) + régression (kWh ep/m²/an).
Split spatial par commune INSEE pour éviter la fuite via autocorrélation spatiale.

D-017 : ML predictions stockées dans public_data.dpe (source='ml-predicted').
Identifiant synthétique = 'ml-pred-<building_id>'.

Pipeline :
1. features.py  : feature engineering (zone climatique, période réglementaire, neighborhood k=20)
2. train.py     : entraînement RF + split spatial + métriques
3. predict.py   : prédiction massive + anomalies + écrêtage

Documentation : docs/ML_DPE.md
"""
