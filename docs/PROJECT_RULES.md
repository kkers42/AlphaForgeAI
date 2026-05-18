# Project Rules — AlphaForgeAI

## Overview
Cloud Run signal platform. Exposes live trading signals from Sentinel bot via HTTPS API and web UI.

## Approved Working Directories
- `/home/kkers/projects/AlphaForgeAI`

## Secrets & Safety Rules
- Never read, copy, or commit `.env` files, API keys, private keys, or secrets
- Never push directly to `main` (or `master`) — always use a branch + PR
- Use `setup/mcp-environment` naming convention for infrastructure branches
- Branches for AI-assisted work: `claude/<short-description>` or `codex/<short-description>`

## Branching Strategy
- `main` / `master` — production, protected
- `develop` — integration branch (if applicable)
- `feature/<name>` — new features
- `fix/<name>` — bug fixes
- `setup/<name>` — infrastructure / tooling

## Versioning
Semantic versioning: `MAJOR.MINOR.PATCH`
- MAJOR — breaking changes
- MINOR — new features, backwards-compatible
- PATCH — bug fixes

## Code Review
- All PRs require review before merge to main
- AI-generated code must be human-reviewed before merge
- Tests must pass in CI before merge


