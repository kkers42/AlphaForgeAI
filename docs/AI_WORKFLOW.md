# AI Workflow Guidelines — AlphaForgeAI

## What AI May Do
- Generate, refactor, and review code
- Write and update documentation and changelogs
- Write tests and analyze failures
- Create branches, commits, and draft PRs
- Set up infrastructure (MCP, CI/CD config)

## What AI Must Never Do
- Read or output `.env`, API keys, private keys, or secrets
- Push directly to `main` or `master`
- Delete branches without explicit user instruction
- Execute production deployments without user approval
- Commit or log credentials, tokens, or private keys

## Branch Naming Convention
| Prefix | Purpose |
|--------|---------|
| `claude/<desc>` | Claude-assisted work |
| `codex/<desc>` | Codex-assisted work |
| `feature/<name>` | New features |
| `fix/<name>` | Bug fixes |
| `setup/<name>` | Infrastructure setup |

## Commit Message Format
```
<type>(<scope>): <short description>

[optional body explaining WHY, not WHAT]
```
Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`

## PR Process
1. AI creates branch from `main`/`master`/`develop`
2. AI commits with descriptive messages
3. AI opens draft PR with summary
4. Human reviews and approves
5. Human (not AI) merges to main

## MCP Environment (Atlas: 192.168.1.43)
- **filesystem** — scoped to `/home/kkers/projects` and `/ssd/projects`
- **github** — fine-grained PAT stored in `~/.claude.json` (update when it expires)
- **git** — operates on `/home/kkers/projects`
- **playwright** — headless browser on Atlas (no display)
