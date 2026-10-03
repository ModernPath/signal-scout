# SignalScout project workflow

Apply this workflow to every request in this repository. The latest explicit user instruction takes precedence if it changes the requested scope or process.

## Start from the product and feature specs

Keep the product-wide PRD at `specs/phase-1-prd.md`, architecture at `specs/architecture-tech-stack.md`, and design in `specs/design/`. Do not move or replace these with feature documents. Read the relevant product-wide documents and feature folder, and use `.codex/skills/spec-driven-development/SKILL.md` for spec work.

Each smaller feature has one folder, `specs/features/<feature-slug>/`, with three required Markdown files:

- `task_spec.md`: intended behavior, scope, and acceptance criteria.
- `technical_spec.md`: implementation design and material technical decisions.
- `test_plan.md`: meaningful verification cases and exit criteria.

Keep feature-specific prototypes and extra documents in that feature folder; shared product design remains in `specs/design/`. Before implementation, reconcile the request with the product-wide and feature documents. Update the root documents for product-wide decisions and the feature documents for local behavior. For a new feature, create the three documents before writing behavior. For a question or review, read the relevant specs and answer without creating placeholder documents.

## Implement with TDD

For every change to runnable behavior, use `.codex/skills/test-driven-development/SKILL.md`. The standing project instruction is to write a meaningful failing test for the next observable behavior, confirm the intended failure, make the smallest code change to pass it, and refactor while green. Repeat for each distinct behavior. Use existing test conventions and keep external calls out of the normal test loop.

If no test harness exists, add only what is needed to exercise the behavior. If a failing test cannot be run because of an environment blocker, report that limitation and do not claim a completed TDD cycle. Documentation-only, research, and status requests do not require test execution; keep `test_plan.md` aligned when they change acceptance criteria.

## Review the feature

After implementing a feature with the spec-driven and test-driven workflows, use `.codex/skills/feature-review/SKILL.md` to validate it against the specs, test cases, approved design, security and privacy requirements, architecture, and feature-specific risks. For UI work, inspect the running app and prototype in a browser and save comparison screenshots in a temporary folder. Record findings and any acceptance criteria that remain unverified. An explicit review request uses the same skill without requiring implementation first.

## Finish against the contract

Compare the result with the PRD, architecture, and relevant feature's `task_spec.md`, `technical_spec.md`, and `test_plan.md`. Report completed behavior, verification performed, and any unmet or unverified acceptance criteria. Update the appropriate root or feature document when implementation changes an agreed decision.

