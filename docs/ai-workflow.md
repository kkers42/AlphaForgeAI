# AI Collaboration Workflow

## Branch Strategy

- `main` is a protected branch and must remain deployable at all times.
- Direct pushes to `main` are not allowed.
- Every change starts from a dedicated feature branch created from the latest `main` (for example, `docs/ai-workflow`, `feature/<topic>`, or `fix/<topic>`).
- Keep branches focused on a single change set to simplify review and rollback.

## Pull Request Review Workflow

1. Create a branch from `main` and implement only the scoped change.
2. Run local checks relevant to the change (linting, docs validation, or tests when applicable).
3. Open a pull request (PR) into `main` with:
   - A clear title
   - A concise summary of what changed
   - Any validation steps reviewers can reproduce
4. Request at least one reviewer.
5. Address review feedback in follow-up commits on the same branch.
6. Merge only after approval and passing required checks.
7. Prefer squash merge to keep `main` history clean unless repository policy states otherwise.

## Roles of ChatGPT, Codex, and Claude

### ChatGPT

- Acts as a planning and communication assistant.
- Helps define requirements, acceptance criteria, and user-facing language.
- Supports drafting documentation, release notes, and review summaries.

### Codex

- Acts as an implementation assistant inside the repository.
- Makes scoped code or documentation edits, runs checks, and prepares commits.
- Helps automate repetitive engineering tasks and keeps changes aligned to requested constraints.

### Claude

- Acts as an analytical reviewer and reasoning partner.
- Provides alternative approaches, edge-case analysis, and critical feedback on proposals.
- Supports PR quality by stress-testing assumptions and clarifying trade-offs.

## Recommended Collaboration Pattern

- Use ChatGPT to refine scope and acceptance criteria.
- Use Codex to implement the approved change in a feature branch.
- Use Claude (or another reviewer) to challenge assumptions and review quality before merge.
- Finalize through the standard PR review and approval process.
