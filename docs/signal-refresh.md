# Signal Refresh

The generated signal snapshot is refreshed by GitHub Actions.

- Workflow: `.github/workflows/refresh-signals.yml`
- Schedule: hourly at minute 17 UTC
- Manual run: GitHub Actions -> Refresh signals snapshot -> Run workflow
- Output: `data/signals/latest.json`

The workflow reuses `scripts/generate_signals.py`, validates the generated JSON,
starts the FastAPI app locally, and smoke checks `/health` and `/signals`.

The generator writes through an atomic temp-file path. If generation, validation,
or route smoke checks fail, the workflow stops before committing, so the last
known good snapshot stays in place.
