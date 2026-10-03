---
name: test-driven-development
description: Implement or fix runnable behavior with a test-first red-green-refactor loop. Use for code changes in this project as required by AGENTS.md, or when the user explicitly requests TDD elsewhere; skip documentation-only work.
---

# Test-driven development

Use a failing test to define one observable behavior, then make that behavior pass with the smallest useful change.

## The loop

1. Inspect the existing test runner, conventions, and relevant behavior. Choose one user-visible outcome or public contract. For a bug, start with a regression case that reproduces it.
2. Write the smallest meaningful test for that outcome. Run the targeted test and confirm it fails for the expected behavior, not because of broken setup, a typo, or an unrelated failure.
3. Implement the minimum code needed to pass. Run the targeted test again. Refactor only while keeping the behavior green.
4. Repeat for the next distinct outcome. Run broader relevant checks when needed to catch integration risk or satisfy an existing gate, then stop.

## Test quality and boundaries

- Prefer behavior at a stable public boundary over assertions that copy the implementation. Use the test level that gives the clearest signal; a unit test is not automatically the right choice.
- Keep fixtures and mocks at external boundaries such as network services, clocks, or payment systems. Do not mock the behavior under test. Avoid real external side effects in the red-green loop.
- Preserve existing tests and patterns. Change an existing assertion only when the intended contract has changed, and explain that change.
- If the environment cannot run a meaningful failing test, state that limitation. Do not claim a TDD cycle occurred merely because a test file was written.
- When an agreed spec is also present, take each test case from its acceptance criteria and keep the implementation within that scope.
