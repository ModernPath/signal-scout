# Company knowledge RAG — test plan

**Status:** Technical verification executed; see [acceptance results](acceptance_results.md). Representative company editorial judgments remain unverified.

## Fixtures

Use synthetic company articles containing a paraphrased repeated claim, a different argument on the same subject, an exact product/entity name, a buried relevant section, contradictory passages, and irrelevant text. Add checked research evidence for two opportunities to test isolation. Include deleted/replaced content, an incomplete corpus, missing brief/key, and source text containing hostile instructions. Build a fixed set of 20 retrieval queries with manually labeled relevant passages before tuning thresholds.

| Acceptance | Meaningful verification |
|---|---|
| AC1 | Main UI and standalone service content writes create durable pending indexing. With fake provider counters, repeated unchanged sync makes no document embedding calls; edits embed only changed inputs. Save succeeds while research occupies the single-active queue. |
| AC2 | Against real pgvector/full-text SQL, paraphrase, buried passage and exact entity queries retrieve labeled passages. Verify filtering, overlap deduplication, deterministic tie breaks and bounded prompt selection. |
| AC3 | Editorial comparison identifies a repeated claim and a new claim on the same topic using cited original passages. Empty/partial results yield uncertainty, not proof of novelty. Existing numeric ranking remains reproducible. |
| AC4 | Enrichment citations resolve to the exact supplied source versions; forged IDs and claims unsupported by source passages are rejected or marked uncertain. Human review checks meaning, not just citation existence. |
| AC5 | Drafts retrieve factual material only from the chosen complete research snapshot. An unrelated opportunity, prior marketing claim, conflicting evidence or voice passage cannot satisfy factual support. Retain existing channel-length, prohibited-claim and numeric checks. |
| AC6 | Edit/delete during embedding cannot publish stale chunks. Deletion and retention expiry purge derived text/vectors/cache/retrieval excerpts; historical output references become visibly unavailable. |
| AC7 | Missing key, zero hits, rate limit, invalid dimensions/count/NaN, partial index and provider timeout produce safe visible states. Lexical inspection/deterministic analysis work; incomplete research still blocks drafts. Model change never mixes vector spaces or deletes the valid generation prematurely. |
| AC8 | Slow endpoints return queued status; duplicate jobs reuse appropriately, new actions dispatch correctly, retries resume safely and interrupted batches respect stale recovery. Main and standalone interfaces exercise the same service. |
| AC9 | A content, brief, corpus, prompt/model or retrieval-config change invalidates affected caches; a historical output shows its original sources unless redacted. |

## Evaluation and live verification

- Offline TDD: meaningful failing tests per next behavior, deterministic fake embeddings/provider output, real disposable PostgreSQL integration tests. Keep external calls out of the normal suite.
- Retrieval gate: on the fixed 20-query set, at least 18 queries place a labeled relevant passage in the top five; no cross-opportunity or deleted-source leakage. Record lexical baseline and semantic improvement specifically on paraphrases. This is a proposed target to validate against representative company data.
- Editorial gate: at least ten reviewed repeated/different-claim pairs, no confidently mislabeled fresh angle among known repeated claims, and explicit uncertainty when evidence is inadequate. Retrieval metrics alone do not establish this gate.
- Opt-in Gemini smoke test: use a small synthetic or operator-approved corpus, verify actual embedding access/model behavior, index → retrieve → refine → research → draft, record model/config/version and safe usage counts. Set a bounded request budget before running; no secrets/raw private payloads in reports.
- Browser review: compare the feature prototype with the main app at desktop and narrow widths. Capture temporary screenshots for indexing, retry, previous passages, citation inspection, draft sources and source deletion. Verify keyboard operation, focus, copy/edit and loading/error states.
- Deployment gate: extension installation, migrations on existing schema/data, backup/restore, restart/recovery and feature-flag rollback on disposable PostgreSQL 17 before changing the live volume.

## Exit criteria

All AC1–AC9 have evidence, existing feed/collection/intelligence regressions pass, and feature review records findings. Document pending real-company editorial acceptance separately from synthetic/live technical verification. Do not claim factual reliability solely from similarity scores or syntactically valid citations.
