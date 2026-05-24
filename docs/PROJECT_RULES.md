# Project Rules — AlphaForgeAI

## Overview
Cloud Run signal platform exposing live trading signals from the Sentinel bot via HTTPS API and web UI at alphaforgeai.io.

## Approved MCP Working Directories
Project source is cloned to the MCP development server workspace.
Specific server paths are defined in the server-local MCP config and are not committed to this repo.

## Secrets & Safety Rules
- Never read, copy, or commit `.env` files, API keys, private keys, or secrets
- Never push directly to `master` — always use a branch + PR
- AI must not execute production deployments (Cloud Run deploy) without explicit human approval
- Branches for AI-assisted work: `claude/<desc>` or `codex/<desc>`

## Branching Strategy
- `master` — production, protected
- `feature/<name>` — new features
- `fix/<name>` — bug fixes
- `setup/<name>` — infrastructure / tooling changes

## Versioning
Semantic versioning: `MAJOR.MINOR.PATCH`
- MAJOR — breaking or incompatible changes
- MINOR — new backwards-compatible features
- PATCH — bug fixes only

## Code Review
- All PRs require human review before merge to master
- AI-generated code must be human-reviewed
- CI checks must pass before merge
