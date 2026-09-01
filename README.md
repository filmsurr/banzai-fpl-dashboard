# BANZAI FPL Season 2 — Manual Update v4.1

League ID: **218355**  
Live site after GitHub setup: **https://filmsurr.github.io/banzai-fpl-dashboard/**

This is the clean BANZAI rebuild with **manual FPL data updates from your Mac**.

## Update model

There is **no scheduled GitHub FPL updater** in this version.

Your normal workflow is:

`Terminal / update_and_publish.command → FPL API → dashboard_data.js → GitHub push → GitHub Pages deploy`

GitHub Actions is used only to **publish the website after you push**, not to fetch FPL data automatically.

## Included rules/features

- League ID 218355.
- Prize target 5,000 THB.
- 7 prize categories.
- Maximum 2 prizes per manager with pass-down logic.
- Highest GW MVP tracking.
- Highest single GW score, captain points, and team value.
- Correct Aug 2026–May 2027 monthly GW schedule.
- Monthly penalty teams/pool determined by number of GWs in that month.
- Monthly penalty uses **official net GW score after transfer-hit deductions**.
- Dashboard shows Raw Points / Transfer Hits / Net Penalty Score.
- Finalized penalty totals and projected current-month penalty.
- Glassmorphism dashboard and PNG export.
- GitHub Pages deployment on each push to `main`.

## First setup after deleting/recreating your repository

1. Create an **empty public** GitHub repository named `banzai-fpl-dashboard` under `filmsurr`.
2. Unzip this package to a permanent folder on your Mac.
3. Run `setup_github.command` once.
4. On GitHub: **Settings → Pages → Source = GitHub Actions**.
5. Wait for `Deploy BANZAI FPL dashboard to GitHub Pages` to turn green.

## Every future Gameweek

From Terminal:

```bash
cd "/path/to/BANZAI_FPL_v4.1_MANUAL"
./update_and_publish.command
```

Or simply double-click `update_and_publish.command` in Finder.

The script:
1. syncs with GitHub,
2. downloads the latest finalized FPL data,
3. recalculates the dashboard,
4. commits changed `dashboard_data.js`,
5. pushes to `main`.

GitHub Pages then republishes the same URL automatically.

## Important penalty score definition

For each GW, monthly penalty uses the official net contribution to league total:

`Net GW score = current total_points − previous total_points`

The transfer cost is displayed separately for transparency. This avoids subtracting a `-4` transfer hit twice.
