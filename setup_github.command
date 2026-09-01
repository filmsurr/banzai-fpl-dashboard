#!/bin/bash
set -e
cd "$(dirname "$0")"

clear
echo "============================================================"
echo " BANZAI FPL — ONE-TIME GITHUB SETUP v4.1"
echo "============================================================"
echo
echo "Before continuing, create an EMPTY PUBLIC GitHub repository named:"
echo "  banzai-fpl-dashboard"
echo "under the GitHub account: filmsurr"
echo
read -r -p "Press Enter after the empty repository has been created..."

echo
if [ ! -d .git ]; then
  git init
fi

git branch -M main

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin https://github.com/filmsurr/banzai-fpl-dashboard.git
else
  git remote add origin https://github.com/filmsurr/banzai-fpl-dashboard.git
fi

echo "Fetching latest FPL data before first publish..."
python3 fpl_dashboard_updater.py

echo
git add -A
if git diff --cached --quiet && git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "No new files to commit."
else
  git commit -m "Initial BANZAI FPL v4.1 manual dashboard" || true
fi

echo
echo "Publishing to GitHub..."
git push -u origin main

echo
echo "============================================================"
echo " GITHUB UPLOAD COMPLETE"
echo "============================================================"
echo "Next on GitHub: Settings > Pages > Source = GitHub Actions"
echo "Then wait for the Pages workflow to turn green."
echo
echo "Future updates: run ./update_and_publish.command"
echo
read -n 1 -s -r -p "Press any key to close..."
echo
