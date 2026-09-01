# Changelog

## v4.1 Manual Update
- Removed scheduled GitHub FPL data updater (`update-data.yml`).
- FPL data is updated only when the user runs `update_and_publish.command` locally.
- Kept GitHub Pages deployment workflow so every push to `main` republishes the site.
- Added one-time `setup_github.command` for a newly recreated empty repository.
- Retained clean v4 dashboard/rules and net monthly penalty logic after transfer hits.

## v4.0
- Clean rebuild of BANZAI FPL dashboard and rule engine.
