---
name: spec-driven-development
description: Create, revise, or implement SignalScout features from its product PRD, architecture, and design. Keep the product-wide documents in specs/ and each smaller feature's task, technical, and test-plan documents under specs/features.
---

# Spec-driven development

Keep the feature contract easy to find and trace through implementation.

## Product and feature locations

Keep the product-wide PRD at `specs/phase-1-prd.md`, architecture at `specs/architecture-tech-stack.md`, and shared design in `specs/design/`. Do not move or replace them with feature documents. Read them for product intent and constraints.

Store each smaller feature's specifications in `specs/features/<feature-slug>/`, using a short lowercase hyphenated slug. Each feature folder contains these three Markdown files:

- `task_spec.md` — user problem, scope, flows, decisions, exclusions, and observable acceptance criteria.
- `technical_spec.md` — architecture, data, APIs, integrations, operational behavior, and material technical decisions.
- `test_plan.md` — meaningful verification scenarios, fixtures or environment, and exit criteria mapped to the task spec.

Add feature-specific design references, decision records, or other artifacts in the feature folder only when they help. Shared design stays in `specs/design/`. Do not duplicate the product-wide PRD or architecture inside a feature folder. When reorganizing feature specs, preserve content and fix relative links. Keep documents concise; mark unresolved decisions explicitly instead of filling sections with guesses. A test plan is a specification artifact and does not itself authorize adding or running tests.

## Work from the contract

1. Read the relevant product-wide documents, feature folder, and current code. Identify the latest explicit user decisions, required behavior, constraints, and deferred scope. A newer user instruction takes precedence over an older document.
2. Make a compact coverage map for the work at hand: requirement → observable behavior → implementation surface. Keep this in working notes unless the user asks for a permanent artifact.
3. Resolve routine implementation choices from the existing architecture and user intent. If two mandatory requirements conflict or a decision would materially change product scope, ask only for that decision while continuing independent work.

## Implement and reconcile

- Build coherent vertical slices across the necessary interface, behavior, and persistence layers. Keep existing conventions unless the technical spec calls for a change.
- Do not implement deferred features or silently narrow a required behavior because a provider or component is difficult; surface the dependency or limitation.
- When implementation changes agreed behavior, update the root documents for product-wide decisions and the feature documents for local behavior. Keep acceptance cases in `test_plan.md` aligned with `task_spec.md`.
- For runnable changes in this project, follow the TDD requirement in `AGENTS.md` and the `test-driven-development` skill. Documentation-only work does not require test execution.

Report completed requirements, material differences from the spec, and blocked or unverified acceptance criteria. Link the feature documents and changed artifacts for review.
