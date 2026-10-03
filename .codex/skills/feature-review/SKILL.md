---
name: feature-review
description: Review a completed SignalScout feature against its specs, test plan, approved UI prototype, security requirements, and architecture. Use after implementation and TDD, or for an explicit feature review.
---

# Feature review

Review the implemented feature against its agreed contract. Do this after the spec-driven and test-driven implementation workflow, or when the user requests a review. A passing test suite alone does not establish acceptance.

## Establish the contract

Read `specs/phase-1-prd.md`, `specs/architecture-tech-stack.md`, the relevant `specs/features/<feature-slug>/{task_spec,technical_spec,test_plan}.md`, and any applicable files in `specs/design/`. Include the latest user decisions. Trace every in-scope acceptance criterion and test-plan case to implementation and observed evidence. Mark each **pass**, **fail**, or **not verified**, with a reason. Identify missing cases, tests that assert implementation details instead of behavior, and claims of completion that evidence does not support. Run the relevant automated and integration checks; use a disposable environment for checks that mutate data or call external services.

## Inspect the running experience

For a feature with UI, open both the running app and `specs/design/index.html` in a browser. Exercise the affected flows and compare equivalent states at matching desktop and narrow viewports. Check layout, content, hierarchy, interaction states, empty/error/loading states, keyboard use, focus, readability, overflow, and broken or misleading controls. Capture screenshots of the prototype and app in a temporary directory (for example, a directory created with `mktemp -d` under `/tmp`); include paths and the viewport/state in review evidence. Do not add screenshots to the repository unless requested. Distinguish intended deviations documented in the specs from defects. If the app cannot run, report the UI comparison as not verified and explain the blocker.

## Inspect security and privacy

Use the [current OWASP Top 10](https://owasp.org/projects/top-ten) as a risk checklist and record evidence or a reason for non-applicability for each category. Review the feature's actual trust boundaries: authentication and authorization when required, including object-level access; input and output validation; injection and untrusted external content; request origin and CSRF controls; URL and fetch safety; secrets and sensitive data in storage, responses, logs, and screenshots; dependencies and configuration; and error handling. For this MVP, check that the no-sign-in assumption remains limited to one trusted local operator, the web port stays bound to localhost, and mutations reject cross-origin requests. A feature that changes that deployment or user model needs an explicit authentication and authorization design. Use safe, local tests; do not probe third-party or production systems without authorization.

## Inspect architecture and feature risks

Compare the implementation with the product architecture and feature technical spec: module boundaries, data flow, schema and API contracts, worker and provider isolation, failure handling, and operational behavior. Look for duplicated logic, dead code, unused dependencies, oversized modules with unrelated responsibilities, and unnecessary coupling. Support maintainability findings with concrete call sites or behavior, rather than arbitrary file-size rules. Check other risks relevant to the feature, such as accessibility, data integrity, performance, provider limits and cost, observability, and recovery from partial failure.

## Close the review

Report findings by severity with a file or screen location, reproduction or evidence, user impact, and a concrete fix. Summarize coverage of the acceptance criteria and test-plan cases, commands run, browser states and screenshot paths, OWASP applicability, and remaining unverified items. For implementation work already in scope, fix material findings through the project's TDD workflow and review again. For a review-only request, report findings without changing runnable behavior unless the user asks for fixes. Update specs only when an agreed decision or acceptance criterion has genuinely changed; do not rewrite the contract to hide a defect.
