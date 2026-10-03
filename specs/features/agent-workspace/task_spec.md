# Agent workspace

Status: implemented and reviewed, 2026-10-03; see [acceptance results](acceptance_results.md). Extends the Phase 2 PRD and intelligence UI.

## Outcome
Prominent main navigation opens conversational intelligence beside an actual execution activity panel. Existing screens and chat share the same services, saved opportunities, company context, research and drafts.

## Acceptance
- W1: Agent workspace provides suggested prompts, persistent sessions, a selected-opportunity control, messages and keyboard-accessible composer; desktop/mobile fit the shared product shell.
- W2: Each submitted turn queues promptly; reload restores messages, active work and activity. Duplicate submission tokens reuse the job; conflicting work is visible. Web has no provider key.
- W3: Gemini can use bounded existing service tools for opportunity listing/inspection, analysis, company retrieval, angle refinement, research and drafting. Research/refinement/draft tools require the explicitly pinned opportunity; missing prerequisites remain visible. Offline inspection and analysis remain useful, with explicit fallback status.
- W4: Persist actual tool start/completion/failure events with safe summaries, observable inputs, source/result references and uncertainty. Show deterministic analysis honestly and named research/draft subagents only when used. No invented execution steps or reasoning transcripts.
- W5: Results provide cards linking to opportunity details, original safe sources, company passages and saved editable drafts. Chat never publishes or changes company context.
- W6: Limit messages/history/tool calls/output/provider time; validate all tool arguments. Provider failure after a side effect never replays the turn. Interrupted tool activity is failed visibly. Session deletion/90-day expiry remove turns, associated chat jobs and events; no credentials/raw provider payloads enter responses/logs.

## Decisions
Use the existing single intelligence worker and single-active-job constraint. Keep main guided screens. Selected opportunity is explicit UI context on each turn, not inferred from history. Source excerpts are untrusted data. Human review remains required for generated editorial claims.
