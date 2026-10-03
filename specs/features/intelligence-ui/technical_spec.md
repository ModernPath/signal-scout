# Intelligence UI — technical specification

## Architecture
The main FastAPI web process serves the existing HTML/vanilla JS shell, two additional views, and `/api/intelligence/*` routes. A small import bridge locates `agents/signal-intelligence` in the repository/container and constructs the same IntelligenceService/IntelligenceStore using the application's engine. No HTTP proxy, separate database, duplicate ranking rules, or frontend build is introduced.

Web handles context CRUD and read-only opportunities/detail; slow analysis/research/draft requests enqueue `intelligence_job` and return 202. Exactly one dedicated `intelligence-worker` process claims jobs transactionally and invokes the shared service. Analysis uses the deterministic core; research/drafts invoke existing bounded subprocess subagents. Only the intelligence worker receives Gemini credentials; web receives a boolean capability flag. Jobs have action, validated input JSON, opportunity FK, status, timestamps, result IDs, and safe error summaries. A partial unique index plus advisory transaction lock permits one active job. Identical active requests reuse it; other requests get 409. Startup and five-minute stale recovery mark running jobs failed. Each execution records a terminal status; partial research is visible both in detail and job status.

Migration 0007 adds jobs and `content_draft.revises_id`. User draft revisions insert new draft rows and preserve channel/format/opportunity/research/evidence; `model_version=operator-edit`. Validate text and channel length; never label edited claims model-verified. Return cited source metadata from the draft's own research snapshot, including older snapshots.

## API
`GET/PUT/DELETE brief`, `GET/POST content`, `PUT/DELETE content/{id}`, `GET opportunities`, `GET opportunities/{id}`, `POST analyze`, `POST opportunities/{id}/research`, `POST opportunities/{id}/draft`, `GET jobs`, `GET jobs/{id}`, `PUT drafts/{id}` under `/api/intelligence`. `GET status` returns provider availability and context status. Same-origin middleware belongs to the application; all IDs and enum/length limits are validated, SQL is parameterized, errors are sanitized. Reads paginate opportunity lists in the browser (20 visible at a time; bounded analysis ≤500 signals in UI, 1000 API) and job history is capped at 20.

## UX
Reuse the shared design system. Opportunities: header/analyze control, setup guidance, persisted job status, ranked list and an inline detail pane, evidence and draft sections. Company context: labeled forms and saved content list/edit/cancel/delete. Persist selected view/opportunity in URL hash for refresh. Poll jobs while active and refresh affected data only when work finishes, retaining unsaved draft/context edits. Copy is explicit and reports clipboard errors. Loading/errors use live regions; all dynamic content is escaped and source links accept only HTTP(S).

## Review refinements

Research summaries deduplicate corroborated claims without dropping source evidence, and Google citation hops resolve once per source to bound HTTP work. Draft prompts request citations for every factual claim, especially numbers. Specific known validation failures map to safe operator messages; arbitrary exception text is never returned. Research evidence expands on demand with visible conflicting/uncertain counts. Narrow navigation wraps so all five screens remain visible; saving a draft revision restores focus to the new editor.
