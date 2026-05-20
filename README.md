# Dashboard Garmin

Dashboard statique alimente depuis Supabase. Aucune cle exposee cote navigateur : `build_data.py` lit `.env` et ecrit `data.json`, le HTML lit ce fichier local.

## Lancer

```powershell
cd C:\Users\MORET\claude\projets\GARMIN-TRAINING\dashboard
.\run.ps1            # refresh 90j + serveur + navigateur
.\run.ps1 -Days 180  # fenetre plus longue
```

Ou en deux temps :

```powershell
python build_data.py --days 90
python -m http.server 8765
# puis http://localhost:8765/index.html
```

## Contenu

- KPIs 14j : sessions, course, velo (entrain. > 10 km), nat, charge 7j, readiness 7j
- Objectifs courses : semi 31/05, trail 13/09, marathon Lille 25/10, 10 km
- Volume hebdo 8 sem par discipline (course km, velo km, nat hm, muscu h)
- Donut repartition seances 30j
- Charge cumulee 30j (rolling 7j)
- Scatter allure course par seance, code couleur par zone (endurance / tempo-seuil / VMA)
- Readiness, FC repos + HRV, body battery, sommeil duree+score, stress 30j
- Tableau statut HRV (BALANCED / UNBALANCED / LOW)
- 30 dernieres activites
- Zones d'allures cibles (calees sur semi 1h30)

## Refresh

`run.ps1` rebuild `data.json` a chaque lancement. Si tu veux juste refresher la donnee sans relancer le navigateur, lance `python build_data.py` puis F5 dans le navigateur.

Pour avoir les donnees du jour, lance d'abord `python ..\sync_garmin.py --days 2` pour pousser Garmin -> Supabase.
