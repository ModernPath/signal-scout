# Intelligence in the SignalScout application

Status: implemented; verification and remaining browser limits are in [acceptance results](acceptance_results.md), 2026-10-01.

## Outcome and scope
The trusted local operator can use Phase 2 from the main application at localhost:8000. Add Opportunities and Company context to its existing navigation and a feed shortcut. Reuse the independent agent service, core, memory, and research/draft subagents against the application's PostgreSQL database.

## Acceptance criteria
- U-01: Company context has a persisted, versioned brief (description, audience, expertise, POV, voice, prohibited claims) and previous content add/edit/delete. Empty context explains what to supply and why.
- U-02: Analyze recent, non-dismissed signals over a selected 1–90 day window; show a ranked list, membership, component scores, unknowns, score coverage, run timestamp, Why now/Why us/angle, and previous content matches. Feed provides an entry point. Analysis can run without Gemini.
- U-03: Select an opportunity and request research; show queued/running/complete/partial/failed status, safe errors, dated evidence, source links, conflict/unknown labels, and source provenance.
- U-04: With a brief and complete research, generate any LinkedIn/X post/reply; display evidence references and editable drafts; save revisions with history, retain original evidence snapshot, copy text. Without prerequisites/provider, explain the blocker. Nothing publishes.
- U-05: Slow work queues promptly in PostgreSQL and survives browser reload/navigation. Repeated identical active requests reuse the job; conflicting work is rejected clearly. Worker restart fails abandoned running work visibly, keeps queued work, and never silently replays provider calls.
- U-06: Same-origin validation, localhost binding, bounded/validated payloads, safe error summaries, escaped content and safe links apply to all new routes. No secrets enter the browser or job results. Prior feed/monitoring/collection behavior remains functional.
- U-07: Desktop and narrow layouts, keyboard access, busy/empty/error/partial states, and the complete journey are inspected in a browser and recorded.

## Decisions
Manual analysis and selected research/drafts only. Use deterministic topic titles during application analysis to bound duration/cost; Gemini research/drafting use the existing subagents. Jobs use context current at execution; changes to context require a fresh analysis. Human edits are explicitly editorial revisions, not newly verified claims. Chat remains available through the independent agent; the main UI exposes the guided workflow. Editorial quality with actual company material remains an operator acceptance step.

The 2026-10-03 [Agent workspace](../agent-workspace/task_spec.md) supersedes the decision to keep chat only in the independent agent. Main UI chat is queued and shares service/memory with the guided workflow.
