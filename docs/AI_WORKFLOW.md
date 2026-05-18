# AI Workflow Guidelines — AlphaForgeAI

## Scope of AI Assistance
AI tools (Claude, Codex) may be used for:
- Code generation, refactoring, and review
- Documentation and changelog maintenance
- Test writing
- Debugging and root-cause analysis
- Infrastructure setup (MCP, CI/CD)

## What AI Must Never Do
- Read or output `.env` files, API keys, or secrets
- Push directly to `main` or `master`
- Delete branches without explicit user instruction
- Execute production deployments without user approval
- Commit credentials, tokens, or private keys

## Standard AI Branch Naming
- `claude/<short-description>` — Claude-assisted work
- `codex/<short-description>` — Codex-assisted work
- `setup/<name>` — infrastructure setup

## Commit Message Format
```
<type>(<scope>): <short description>

[optional body]
```
Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`

## PR Process
1. AI creates branch from `main`/`master`/`develop`
2. AI commits changes with descriptive messages
3. AI opens draft PR with summary
4. Human reviews and approves
5. Human (not AI) merges to main

## MCP Environment Notes
- Filesystem MCP is scoped to `/home/kkers/projects` and `/ssd/projects`
- GitHub MCP uses a temporary fine-grained PAT — update in `~/.claude.json` when it expires
- Git MCP operates on `/home/kkers/projects` working directory
- Playwright MCP runs headless on Atlas (no display)
