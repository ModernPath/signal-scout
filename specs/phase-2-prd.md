# SignalScout — Phase 2 AI Intelligence PRD

**Status:** Standalone agent implemented; main application integration implemented; company editorial acceptance pending  
**Parent:** [Phase 1 MVP PRD](phase-1-prd.md)  
**First delivery:** [Standalone intelligence agent](features/intelligence-agent/task_spec.md)

## Outcome

Help the same trusted operator move from a feed of individual signals to evidence-backed content opportunities. The operator should see which conversations are gaining momentum, why one matters to the company now, how it differs from prior company content, and editable LinkedIn/X posts and replies. Nothing is published automatically.

## Phase boundary

Build and validate a complete independent agent in `agents/signal-intelligence/` first, following the architecture of [`agents/example-agent/`](../agents/example-agent/). It reads Phase 1 signals and monitoring context from the application's PostgreSQL database and writes its own versioned intelligence and agent-memory records to that same database. The independent agent has its own chat CLI, direct tool CLIs, local API, and local UI. The operator has authorized [main application integration](features/intelligence-ui/task_spec.md) after successful live Gemini verification; company editorial acceptance remains pending. Phase 1 feed order and triage remain unchanged.

## Operator workflow

1. Enter a company brief: company description, audience, expertise, point of view, claims to avoid, voice, and links or text of previous company content. The agent must make missing context visible rather than invent it.
2. Run analysis on a bounded, recent signal window. The agent groups semantically related *signals* into conversations. A conversation is broader than Phase 1 duplicate grouping and retains every signal and source item as evidence.
3. Review ranked opportunities and their relevance, velocity, novelty, and company POV fit components. Inspect the cited reasons: **Why now? Why us? What’s our angle?**
4. Select an opportunity for deeper research. Review a sourced evidence summary, disagreements, unknowns, and links to original material.
5. Request editable LinkedIn/X post and reply drafts grounded in the selected opportunity and company brief. The operator verifies claims and chooses whether to use the text elsewhere.

## Product decisions

| Area | Phase 2 decision |
|---|---|
| Deployment | Same single trusted local operator; no hosted or team access. |
| Source of truth | Existing PostgreSQL `signal`, `source_item`, `signal_topic`, `signal_state`, and monitoring records. Intelligence tables use the same database, with migrations owned by the application. |
| Company context | Explicit operator-supplied brief and content library; monitoring keywords alone are insufficient to infer a company POV. |
| Analysis cadence | Explicit operator action through the standalone CLI, chat, API, or agent UI. Scheduling is deferred until the independent agent is accepted. |
| Agent architecture | Match the example agent's dependency direction: interfaces and chat → service → pure core, PostgreSQL memory, and narrow subagent processes. All surfaces call the same use cases. |
| Agent memory | Company brief, previous content, intelligence output, drafts, and bounded chat sessions live in application PostgreSQL. No separate JSON file is a second source of truth. |
| Ranking | Explainable component scores and a deterministic total. Raw engagement units from different sources are never compared directly. Missing history lowers confidence rather than being treated as zero velocity or proven novelty. |
| AI use | Model assistance may label conversations, assess fit, synthesize sourced evidence, and write drafts. Validate structured output; keep deterministic grouping safeguards, scoring arithmetic, and persistence outside the model. |
| Research | Preserve source URLs and retrieval times. Distinguish signal evidence from independently checked material. Never present an unverified model assertion as a fact. |
| Drafts | Drafts only, versioned and tied to the cited evidence snapshot; no posting, scheduling, or external messaging. |

## Success and acceptance

- Related signals across sources appear in one conversation without collapsing distinct stories or losing provenance; uncertain matches remain separate.
- An opportunity exposes its four score components, confidence/coverage, timestamp, and a short, evidence-linked rationale for Why now, Why us, and the proposed angle.
- A prior company article or post with a substantially similar claim is surfaced; a genuinely different claim can still be proposed as a fresh angle.
- Research records each claim with a source URL and retrieval time, flags unsupported or conflicting claims, and fails visibly when sources cannot be checked.
- Generated LinkedIn/X posts and replies are editable drafts, include no unsupported specific facts, and remain unavailable when the brief or evidence is insufficient.
- Repeating analysis for unchanged inputs is idempotent; a changed signal set, brief, content library, or model/prompt version produces a traceable new analysis version.
- The standalone chat CLI, direct tools, agent API, and agent UI use the same service behavior against PostgreSQL without starting the SignalScout web process. No key, raw provider payload, or private company content leaks to logs or unrelated responses.
- The agent remains useful without a model key: it can inspect context and opportunities and run deterministic clustering/ranking, while research and drafting clearly report unavailable provider capabilities.

## Deferred from this delivery

Continuous scheduling, multi-user permissions, fine tuning, automatic publishing, automatic replies, outbound outreach, and claiming that a draft is legally or factually approved. The agent's own local UI/API are part of the first independent delivery. The guided main application UI is now included through the separate integration feature. Vector retrieval was deferred from that delivery; it is now implemented through [company knowledge RAG](features/company-knowledge-rag/task_spec.md), with representative company editorial acceptance pending.

## Company knowledge RAG

Index operator-supplied previous content and checked research evidence in the existing application PostgreSQL database. Retrieve relevant original passages for prior-claim comparison, cited angle refinement, and research-grounded drafts. Show retrieved passages and indexing coverage in Company context and Opportunities. Company voice/history and factual research sources have distinct roles; retrieval similarity does not prove truth or novelty. Preserve deterministic analysis and visible lexical fallback when semantic retrieval is unavailable.

The [technical plan](features/company-knowledge-rag/technical_spec.md) implements pgvector and PostgreSQL full-text search, using the `rag-example` submodule as a reference. Semantic signal clustering is a later separately verified increment. Technical acceptance evidence and remaining editorial limits are recorded in the feature folder.

## Open product inputs

Before live research and draft acceptance, the operator must provide a representative company brief, a small sample of previous company content, preferred LinkedIn/X voice, and approved model/research provider credentials. The CLI and tests can be built with fixtures while these inputs are pending.

## Conversational application workspace

The operator approved the [Agent workspace](features/agent-workspace/task_spec.md) on 2026-10-03: prominent main navigation, persisted chat alongside observable tool/subagent activity, explicit opportunity context and links to existing saved results. Chat orchestrates the same use cases and keeps human review and draft-only boundaries.
