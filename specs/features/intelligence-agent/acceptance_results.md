# Standalone intelligence agent — feature review

**Date:** 2026-10-01  
**Status:** Independent implementation complete; editorial and narrow-browser acceptance pending  
**Contract:** [Task](task_spec.md) · [Technical](technical_spec.md) · [Test plan](test_plan.md)

## Test-plan trace

| Case | Result | Evidence and limit |
|---|---|---|
| I-01 | Pass | Disposable PostgreSQL integration groups two related cross-source signals and one unrelated signal, retains source IDs, and reuses the same analysis run for identical inputs. |
| I-02 | Partial | Pure-core test rejects broad-topic merging; ambiguous real events and manual split/merge are unverified. |
| I-03 | Partial | Missing velocity history is `unknown` with lower confidence; calibrated rising-versus-steady labelled cases remain unverified. |
| I-04 | Pass | Pure scoring excludes provider-specific likes, stars, and point counts. |
| I-05 | Partial | Prior-content match changes novelty and is cited in browser; distinct-claim editorial quality needs real examples. |
| I-06 | Pass | Missing brief makes Why us/POV fit unavailable; saving a complete brief and rerunning analysis produces company-specific fit in browser. |
| I-07 | Partial | Live Gemini research on two recent public PageBreak articles saved 12 dated segments with direct publisher URLs and confirmed an original source. Fake provider verifies conflict labels and safe partial failure. A contested live topic and independent publisher-page retrieval are unverified. |
| I-08 | Partial | Service rejects unverified URLs and draft evidence IDs; provider keeps only grounding-supported segments. Live hostile-page prompt injection is unverified. |
| I-09 | Partial | Live Gemini saved all four LinkedIn/X post and reply drafts from a complete public research snapshot; length and evidence IDs were validated. Initial truncation and overlong responses were rejected, then generation budgets and X targeting were corrected. Qualitative claim support still needs human review. |
| I-10 | Pass | No-key path reports unavailable research/drafting; fake provider failure leaves a safe partial research record and offline analysis works. |
| I-11 | Pass | Migrations through `0006_agent_memory` applied to the application and both disposable databases. Agent CLI works without the application web process; root suite still passes. |
| I-12 | Partial | Safe JSON/API errors, restricted subprocess environment, and tests protect known secrets. Full dependency audit and review with private company text are unverified. |
| I-13 | Pass | Brief/content add, replace, inspect, and delete share PostgreSQL. Deletion scrubs all brief versions and content replacement lineage; API and UI deletion tests pass. |
| I-14 | Partial | Three bounded subagents and JSON contracts are tested; malformed output and timeout handling are tested. Every provider-specific failure shape is unverified. |
| I-15 | Pass for public fixture | Offline chat persists bounded PostgreSQL turns and model tool wrappers enforce eight calls. With the updated key, live Gemini chat used `list_opportunities` and returned the shared service result. |
| I-16 | Pass | Direct tools, API, CLI, and UI call the same service. API/UI cross-origin mutation tests pass; both live containers report healthy. |
| I-17 | Partial | Real browser exercised empty dashboard, signal analysis, context forms, prior-content match, research state, and offline chat. Narrow viewport override did not change the browser's actual width; comparison with the local prototype was blocked by browser URL policy. Screenshots were viewed in the browser tool but could not be saved to a temp path through that tool. |
| I-18 | Pass | PostgreSQL cleanup tests expire chat and redact research excerpts while retaining citation URLs; operator deletion scrubs private context. |

The agent suite passed **43 tests** against disposable `signalscout_intelligence_test`; the application suite passed **55 tests** against separate disposable `signalscout_root_test` before the provider-only changes. Both agent containers passed Compose health checks, and localhost `/health` returned `{"status":"ok"}` for UI and API. The running browser UI reached the shared application database and showed the expected empty state. The application signal data was not analyzed or changed during review.

A capped live Gemini research call was exercised only against disposable fixture signals. The provider returned grounded search results about a different organization with the same placeholder name. That result was incorrectly marked complete in the first browser run. The service now requires confirmation from at least one original Phase 1 source URL before a research run can be complete; otherwise it stores `partial` and blocks drafting. The regression test for unrelated results passes. Real company research and human draft review are still required before SignalScout UI integration.

The operator then replaced the invalid 53-character credential with a working Gemini Developer API key. A minimal request returned HTTP 200 and `OK`; live model chat used the opportunity tool. On a separate disposable fixture with [Google's PageBreak announcement](https://blog.google/security/agentic-hacks-real-proofs-inside-googles-pagebreak-project/) and [Cyber Kendra's report](https://www.cyberkendra.com/2026/09/google-pagebreak-ai-agent-500-xss-flaws.html), analysis grouped both signals into one opportunity. Gemini research produced 12 grounded segments. Its citation URIs were Google redirects, so the first run correctly stayed partial. A tested, non-following redirect resolution then produced direct public publisher URLs and a complete run with an original source confirmed. Four channel/format drafts were saved, all unpublished. Gemini initially exhausted output tokens on a LinkedIn reply and exceeded X's 280-character limit on a later reply; bounded thinking and a shorter X target corrected both. A final X reply was 224 characters. The output remains a draft: one earlier reply contained an unsupported conversational setup, prompting a neutral-reply instruction, and qualitative factual support still needs editorial review.

## Findings

| Severity | Finding | Resolution or next action |
|---|---|---|
| Medium | Ambiguous names can lead provider search to unrelated grounded pages. | The completion gate requires an original source; the public PageBreak run confirmed it after safe redirect resolution. Test representative company topics before integrating. |
| Medium | Gemini grounding URLs are redirect wrappers, and the agent does not independently fetch publisher pages. | Fixed by resolving only Google's citation hop with a non-following HEAD request and public-URL check. Claim truth still needs editorial review. |
| Medium | Heuristic clustering, velocity, novelty, and POV scores are not calibrated on labelled company examples. | Keep confidence/unknown states visible; gather a labelled sample and tune in a later iteration. |
| Medium | Draft checks cannot prove that every qualitative assertion follows from cited evidence. A reply initially implied a prior discussion that was not supplied. | Added a neutral-reply instruction and verified later live replies did not imply prior context. Keep drafts unpublished and require human editorial approval before any use. |
| Low | Responsive browser override and local-file prototype navigation were blocked by the browser environment. | API/UI route tests and desktop browser flows passed; repeat a matching narrow-width comparison and save screenshots in an environment that permits it. |

## Architecture and privacy review

The agent matches the example architecture: CLI/chat/tool/API/UI interfaces → shared service → pure core, PostgreSQL memory, and named subagent processes. The application owns the schema. Agent host ports are bound to `127.0.0.1`; database is not exposed. Only one trusted local operator is in scope. The agent has no publishing tool. Deletion and 90-day cleanup are implemented, but cleanup is manually invoked rather than scheduled.

Checked against the current [OWASP Top 10:2025](https://top10.owasp.org/2025/): A01/A07 access and authentication are limited by loopback single-operator deployment; remote use needs a new design. A02 configuration uses loopback ports, same-origin mutations, and scoped environment loading. A03 dependencies are pinned, with vulnerability audit pending. A04 secrets stay in environment and are omitted from error payloads. A05 SQL is parameterized, Jinja escapes content, and untrusted source text is data in provider prompts. A06 explicit selection, evidence gates, and no publish path reduce unsafe automation. A08 grounded segments, URL checks, and citation IDs constrain model output but do not establish truth. A09 provider cost/usage alerting is not implemented. A10 provider/subagent errors have bounded exits and safe partial records. Public URL validation rejects private IP literals and local hostnames; no arbitrary server-side page fetch is performed.
