#!/bin/bash
set -e
cd "$(dirname "$0")"

clear
echo "============================================================"
echo " BANZAI FPL — MANUAL UPDATE & PUBLISH v4.1"
echo "============================================================"
echo

if [ ! -d .git ]; then
  echo "ERROR: This folder is not connected to GitHub yet."
  echo "Run setup_github.command once after creating the GitHub repository."
  echo
  read -n 1 -s -r -p "Press any key to close..."
  echo
  exit 1
fi

echo "1/4 Synchronizing with GitHub..."
git pull --rebase --autostash origin main

echo
echo "2/4 Downloading latest finalized FPL data..."
python3 fpl_dashboard_updater.py

echo
echo "3/4 Saving dashboard changes..."
git add dashboard_data.js index.html rules_config.json RULES.md README.md .github/workflows/pages.yml 2>/dev/null || true

if git diff --cached --quiet; then
  echo "No dashboard changes to commit."
else
  GW=$(python3 - <<'PY'
import json,re
text=open('dashboard_data.js',encoding='utf-8').read()
m=re.search(r'=\s*(\{.*\})\s*;?\s*$',text,re.S)
d=json.loads(m.group(1))
print(d.get('latest_gw','latest'))
PY
)
  git commit -m "Update BANZAI FPL dashboard GW${GW}"
fi

echo
echo "4/4 Publishing to GitHub..."
git push origin main

echo
echo "============================================================"
echo " SUCCESS"
echo " GitHub Pages will redeploy the pushed dashboard automatically."
echo " https://filmsurr.github.io/banzai-fpl-dashboard/"
echo "============================================================"
echo
read -n 1 -s -r -p "Press any key to close..."
echo
