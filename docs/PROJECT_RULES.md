# Project Rules — AlphaForgeAI

## Overview
Cloud Run signal platform exposing live trading signals from the Sentinel bot via HTTPS API and web UI at alphaforgeai.io.

## Approved MCP Working Directories
- `/home/kkers/projects/AlphaForgeAI`

## Secrets & Safety Rules
- Never read, copy, or commit `.env` files, API keys, private keys, or secrets
- Never push directly to `main` (or `master`) — always use a branch + PR
- AI must not execute production deployments without explicit human approval
- Branches for AI-assisted work: `claude/<desc>` or `codex/<desc>`

## Branching Strategy
- `main` / `master` — production, protected
- `develop` — integration branch (if applicable)
- `feature/<name>` — new features
- `fix/<name>` — bug fixes
- `setup/<name>` — infrastructure / tooling changes

## Versioning
Semantic versioning: `MAJOR.MINOR.PATCH`
- MAJOR — breaking or incompatible changes
- MINOR — new backwards-compatible features
- PATCH — bug fixes only

## Code Review
- All PRs require human review before merge to main
- AI-generated code must be human-reviewed
- CI checks must pass before merge

