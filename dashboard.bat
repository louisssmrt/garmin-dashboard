@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ============================================
echo  Dashboard Garmin - Louis
echo ============================================
echo.

echo [1/3] Refresh data Supabase...
python build_data.py --days 90
if errorlevel 1 (
  echo.
  echo ERREUR : build_data.py a echoue. Verifie ton .env / connexion Supabase.
  pause
  exit /b 1
)
echo.

echo [2/3] Demarrage du serveur sur http://localhost:8765 ...
start "" http://localhost:8765/index.html

echo [3/3] Ouverture navigateur...
echo.
echo ============================================
echo  Dashboard ouvert. Ferme cette fenetre quand
echo  tu as fini pour arreter le serveur.
echo ============================================
echo.

python -m http.server 8765
