# Monitoring profile — task spec

**Parent scope:** [Phase 1 MVP PRD](../../phase-1-prd.md)  
**Related design:** [Monitoring screen](../../design/index.html)

## Outcome

The operator can define what SignalScout watches and which sources are enabled. The saved profile persists between sessions and guides later collection runs.

## In scope

- Add and remove topics, include keywords, exclude keywords, competitors, and influential people.
- Accept a competitor as a name, domain, or handle and a person as a name, handle, or profile URL.
- Toggle X, Web/news, Hacker News, Reddit, GitHub, and RSS/API sources.
- Save the full profile as one change. Reopen the page or restart the app and see the same values.
- Queue one initial collection after the first save of a non-empty monitoring profile.
- Show a clear saved or unsaved state. A dedicated edit dialog is unnecessary; remove and add again to change an entry.

## Boundaries

This screen does not collect credentials, configure Reddit subreddits, or edit RSS feed URLs. Provider keys and RSS URLs come from the environment. Scheduling and run status belong to the [Collection feature](../signal-collection/task_spec.md).

## Acceptance criteria

1. All five rule kinds and six source toggles persist after a restart.
2. Blank entries and case-insensitive duplicates within the same rule kind are rejected with a useful message.
3. The first non-empty save queues one initial collection; later edits do not queue duplicate initial runs.
4. Source toggles affect subsequent runs. An in-progress run retains the configuration snapshot it started with.
5. API credentials never appear in the monitoring response or page.
