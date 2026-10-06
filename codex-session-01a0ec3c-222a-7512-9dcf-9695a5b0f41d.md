# Codex conversation

## User

Create a new skill: feature-review. Put this after the spec-driven and test-driven workflow to review and validate the implementation against following aspects:\
1. Check that the specification and test cases are all implemented and acceptance criterias are met\\
2. Check that UI and design matches our prototype at '/Users/pasivuorio/training/signal-scout/specs/design'. Check also for any UX issues or problems with the UI layouts. Use browser and take screenshots while doing this and put on some tmp folder.\
3. Security, including authentication and authorization (if required) and data privacy/security issues. OWASP TOP-10 checks. \
4. Architecture. Look how well it matches out overall architectu, how clean the code is and that there are no dead code or god modules.\
5. Other relevant for that feature

## Assistant

I’ll read the repository workflow and the skill creation guidance, then add `feature-review` and place it after the spec and TDD steps. I’ll check the new skill against the project’s feature documents and review conventions.

## Activity

    $ cat /Users/pasivuorio/.codex/skills/.system/skill-creator/SKILL.md
    ---
    name: skill-creator
    description: Create or update a Codex skill with appropriately scoped instructions and any needed supporting resources.
    metadata:
      short-description: Create or update a skill
    ---
    
    # Skill Creator
    
    Create skills that give Codex useful, non-obvious guidance without constraining unrelated work.
    
    ## Core Principles
    
    **Assume Codex is already capable.** Include only information that changes its decisions or improves its work. Remove generic advice, repeated instructions, speculative edge cases, and examples that do not materially clarify the task.
    
    **Preserve user intent and scope.** A skill should support the requested task, not replace the user's chosen product, expand the assignment, modify unrelated configuration, or imply permission for additional external actions. Do not turn a particular example, past failure, or personal preference into a universal requirement.
    
    Approval to complete a task does not expand its scope or execution permissions. For retrying or externally mutating workflows, define a stopping condition proportional to the risk.
    
    **Match specificity to the risk.** Give the model room to choose an appropriate approach when multiple approaches are reasonable. Use detailed steps, deterministic scripts, or absolute language only when correctness, safety, permissions, or a genuinely fragile workflow requires them.
    
    For open-ended work, describe the outcome and relevant decision criteria. For workflows with a preferred shape, offer useful examples or configurable scripts. Reserve fixed sequences and narrow parameters for operations where deviation would cause a concrete problem. Preserve non-obvious operational invariants, distinguish actual requirements from optional recommendations or local conventions, and avoid restating policies already enforced elsewhere.
    
    **Keep discovery cheap and precise.** Skill names and descriptions are available before a skill is loaded. Describe the actual capability and when it applies, adding exclusions only when they prevent likely misrouting. Avoid exhaustive capability lists and catchalls that attract unrelated requests.
    
    Keep skills self-contained; refer to another skill or tool only when the requested workflow genuinely requires it and it is available in the target environment. Specialized review, hardening, or audit workflows should apply when requested or genuinely needed, not merely because ordinary work touches the same subject.
    
    **Disclose detail progressively.** Keep shared purpose, essential constraints, and useful routing in `SKILL.md`. Put substantial mode-specific guidance, schemas, examples, or procedures in supporting references and read only the references relevant to the current task. A simple self-contained skill does not need a router or extra files.
    
    ## Anatomy of a Skill
    
    Every skill is a folder containing a required `SKILL.md` file and any optional resources its actual workflow needs:
    
    ```text
    skill-name/
    |-- SKILL.md                 Required skill instructions
    |   |-- YAML frontmatter     Required name and description
    |   `-- Markdown body        Instructions loaded when the skill is used
    |-- agents/                  Optional UI metadata and invocation policy
    |   `-- openai.yaml
    |-- scripts/                 Optional executable helpers
    |-- references/              Optional documentation loaded as needed
    `-- assets/                  Optional files used in generated output
    ```
    
    Choose the structure that fits the actual task. Some skills are short and self-contained; others route among operating modes or delegate complex mechanics to scripts. Avoid creating directories, placeholders, examples, or ancillary documentation without a clear use.
    
    ### SKILL.md
    
    The YAML frontmatter identifies the skill and determines when it should be considered. Include the required `name` and `description`, and preserve supported optional fields such as existing `metadata` when appropriate.
    
    The Markdown body is loaded only when the skill is used. Put the purpose, essential workflow, real constraints, and useful links there. Keep detailed procedures and examples in supporting references when they are relevant only to particular modes.
    
    Skill information is disclosed in three stages:
    
    1. **Name and description:** Available during skill selection, so keep them concise and discriminating.
    2. **SKILL.md body:** Loaded when the skill applies, so keep its instructions relevant to that task.
    3. **Supporting resources:** Read or execute only when the current task actually needs them.
    
    The entrypoint should be as short as the task permits while retaining important constraints. A large upper bound is not a target: move conditional detail into references when doing so improves clarity or context use, rather than waiting for the file to become unwieldy.
    
    ### Scripts
    
    Use `scripts/` for executable code when the same logic would otherwise be rewritten repeatedly or deterministic execution materially improves reliability.
    
    - **Example:** `scripts/rotate_pdf.py` for a PDF operation that would otherwise require recreating the same code.
    - **Useful for:** Repeated transformations, reliable API operations, data processing, and other concrete automation.
    - **Validation:** Run new or changed scripts to verify their behavior. Scripts can usually be executed without loading their full implementation into context, although an agent may need to inspect them when patching or adapting them.
    
    ### References
    
    Use `references/` for documentation that is needed only in particular contexts.
    
    - **Examples:** `references/schema.md` for database tables, `references/policies.md` for domain rules, `references/api_docs.md` for an API, or separate writing guides for different deliverables.
    - **Useful for:** Schemas, API documentation, company policies, format-specific procedures, detailed workflows, and substantial examples.
    - **Routing:** Link each reference from `SKILL.md` or another relevant resource and explain when it should be read. Keep information in one place instead of duplicating it across the entrypoint and references.
    
    Keep references focused on maintained, task-specific information that changes the agent's decisions. Avoid copied manuals, exhaustive catalogs, and generic tutorials already available from authoritative sources. Before removing existing resources, inspect their callers and purpose.
    
    For large references, include useful search terms or a short contents section when that makes the needed material easier to find.
    
    ### Assets
    
    Use `assets/` for files that belong in generated output rather than in the model's instructions.
    
    - **Examples:** `assets/logo.png`, `assets/slides.pptx`, `assets/font.ttf`, or `assets/frontend-template/`.
    - **Useful for:** Templates, images, fonts, icons, boilerplate projects, and other files copied or adapted into the result.
    - **Context:** Do not load assets as instructions unless the task requires inspecting them.
    
    ### UI Metadata and Invocation Policy
    
    `agents/openai.yaml` can provide UI-facing metadata such as `display_name`, `short_description`, and `default_prompt`, along with invocation policy. When creating or updating those settings, read [references/openai_yaml.md](references/openai_yaml.md) and keep the values consistent with the skill.
    
    Automatic skill selection is allowed by default. Change that default only when the user explicitly requests an explicit-only skill:
    
    ```yaml
    policy:
      allow_implicit_invocation: false
    ```
    
    This keeps the skill available when explicitly invoked as `$skill-name` without adding it to the model context automatically. Preserve unrelated existing UI, policy, and dependency fields when updating `agents/openai.yaml`.
    
    The initializer creates this file automatically. For new or interface-only metadata, generate it with:
    
    ```bash
    scripts/generate_openai_yaml.py <path/to/skill-folder> --interface key=value
    ```
    
    The generator replaces the entire file. If an existing file contains `policy` or `dependencies`, update only the intended fields in place instead of regenerating it.
    
    Include optional interface fields only when the user provides or requests them.
    
    ### What Not to Include
    
    Include files that directly support the skill's work. Avoid adding a `README.md`, installation guide, changelog, duplicated quick reference, or other auxiliary documentation unless a specific task or packaging requirement calls for it.
    
    ## Progressive Disclosure in Practice
    
    For a skill with multiple substantial modes, keep the shared guidance and mode-selection criteria in `SKILL.md`. Link each supporting reference where its use becomes relevant. Do not load every reference by default, duplicate reference content in the entrypoint, or add a routing layer when there is nothing meaningful to route.
    
    For example, a deployment skill can keep provider selection in `SKILL.md` and separate provider details:
    
    ```text
    cloud-deploy/
    |-- SKILL.md
    `-- references/
        |-- aws.md
        |-- gcp.md
        `-- azure.md
    ```
    
    When the user chooses AWS, read `references/aws.md`; do not also load the GCP and Azure guides. The same pattern can separate business domains, deliverable types, or other genuinely distinct operating modes.
    
    A short skill can instead route to details only when an advanced operation needs them:
    
    ```markdown
    ## Documents
    
    Handle ordinary edits directly.
    
    - For tracked changes, read [references/redlining.md](references/redlining.md).
    - For document internals, read [references/ooxml.md](references/ooxml.md).
    ```
    
    These examples illustrate options, not a required structure. Choose the organization that makes the skill easier to use without loading irrelevant material.
    
    ## Create or Update a Skill
    
    Adapt the work to the request. Creating a complex new skill may involve understanding realistic use cases, choosing supporting resources, initializing files, writing instructions, and validating the result. A narrow update to an existing skill may require only a focused edit and validation.
    
    Ask clarifying questions only when the missing information matters and cannot be reasonably inferred. Respect a user-specified location; otherwise create discoverable skills in `$CODEX_HOME/skills`, or `~/.codex/skills` when `CODEX_HOME` is unset.
    
    Keep automatic skill selection enabled unless the user explicitly requests an explicit-only skill. When the intended invocation mode is genuinely unclear and matters to the requested workflow, ask whether the user wants normal automatic discovery or explicit-only invocation; otherwise preserve the default. Do not infer explicit-only invocation from sensitive operations or required approvals: keep the skill discoverable and require authorization immediately before the actual mutation. Preserve an existing skill's invocation policy unless the user asks to change it.
    
    For a new or substantially revised skill, consider the actual requests it should handle and which reusable resources would improve those tasks:
    
    - A repeated PDF transformation may justify a `scripts/rotate_pdf.py` helper.
    - An application-building workflow may benefit from an `assets/frontend-template/` starter.
    - A data-analysis skill may need a `references/schema.md` guide to avoid rediscovering table relationships.
    
    Create those resources only when their concrete benefit justifies them. If the user has already explained the task clearly, proceed without requesting additional examples.
    
    ### Naming
    
    - Use lowercase letters, digits, and hyphens.
    - Keep names under 64 characters and prefer short action-oriented names.
    - Namespace by tool or domain when doing so improves discovery.
    - Name the skill folder after the skill.
    
    ### Initialize a New Skill
    
    For a new skill, use the bundled initializer when it helps create the required files consistently:
    
    ```bash
    scripts/init_skill.py <skill-name> --path <output-directory> [--resources scripts,references,assets] [--examples]
    ```
    
    For example:
    
    ```bash
    scripts/init_skill.py my-skill --path "${CODEX_HOME:-$HOME/.codex}/skills"
    scripts/init_skill.py my-skill --path "${CODEX_HOME:-$HOME/.codex}/skills" --resources references
    ```
    
    Request only the resource directories the skill needs. Use `--examples` only when concrete placeholders would help, and replace or remove them before finishing. Do not initialize an existing skill again.
    
    The initializer creates the skill directory, a concise `SKILL.md` starter, and `agents/openai.yaml`. It creates resource directories and example files only when requested. Pass generated UI values as `--interface key=value` when needed.
    
    ### Write the Instructions
    
    The frontmatter `description` should briefly explain what the skill does and when it applies. Include a meaningful boundary when similar requests should not activate the skill.
    
    For example:
    
    ```yaml
    description: Create or edit Word documents when formatting, tracked changes, or comments require document-specific handling.
    ```
    
    Put detailed workflows, tool choices, examples, and operating modes in the body or relevant references rather than listing them all in the description. Preserve supported optional frontmatter, such as existing `metadata`, when appropriate.
    
    Write only the instructions needed for another Codex instance to perform the task well. State the desired outcome, non-obvious context, real constraints, and relevant references or tools. Preserve the user's explicit choices and existing authorization boundaries. Avoid prescribing a fixed structure, process, or number of steps when the task does not require one.
    
    ### Validate and Iterate
    
    Validate the completed skill with:
    
    ```bash
    scripts/quick_validate.py <path/to/skill-folder>
    ```
    
    The validator checks frontmatter, naming, and unfinished scaffold placeholders; it does not prove that the skill makes good decisions. Also check that descriptions remain discriminating, instructions preserve user intent, references are discoverable, and any added scripts actually work.
    
    When testing is warranted, verify observable behavior or meaningful invariants. Avoid tests that merely match generated wording, headings, or regex patterns.
    
    Improve the skill based on real usage or demonstrated failures. Prefer a narrow correction to accumulating universal rules for every observed example.
    
    ## Independent Forward-Testing
    
    Use an independent subagent pass when a skill is sufficiently complex or risky that realistic behavioral validation would add meaningful confidence, and when delegation is available and authorized. Ordinary creation or small edits do not automatically require subagents.
    
    Give the evaluating agent a realistic user request, the skill, and the minimum raw artifacts needed to perform the task. Do not provide the intended answer, suspected bug, proposed fix, or prior conclusions unless the evaluation genuinely requires them.
    
    For example:
    
    ```text
    Use $skill-name at /path/to/skill-name to complete this realistic request.
    ```
    
    Keep the evaluation scoped to permitted resources and side effects. Use an isolated temporary workspace for generated artifacts so they do not enter the working tree or contaminate later evaluations. Ask for approval when the proposed evaluation would require additional authorization, affect a live production system, or impose substantial time or cost. Review the actual outcome and artifacts, then make only changes supported by the observed behavior.
    ✓ • 0ms

## Activity

    $ cat .codex/skills/spec-driven-development/SKILL.md && cat .codex/skills/test-driven-development/SKILL.md
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
    ✓ • 0ms

## Activity

    $ git status --short && rg --files specs/design specs/features | head -80
    fatal: not a git repository (or any of the parent directories): .git
    ✗ (128) • 0ms

## Activity

    $ pwd && rg --files -g 'AGENTS.md' -g 'SKILL.md' -g 'phase-1-prd.md' -g 'architecture-tech-stack.md' specs .codex | head -80
    /Users/pasivuorio/training/signal-scout
    specs/phase-1-prd.md
    specs/architecture-tech-stack.md
    .codex/skills/spec-driven-development/SKILL.md
    .codex/skills/test-driven-development/SKILL.md
    ✓ • 0ms

## Assistant

I’m using the skill-creator guidance for the new skill and the project’s spec-driven guidance for where it fits. I found the existing skill format; next I’m checking the repository layout and reviewable product references so the instructions point to the right sources.

## Activity

    $ rg --files specs | head -120
    specs/phase-1-prd.md
    specs/architecture-tech-stack.md
    specs/features/monitoring-profile/test_plan.md
    specs/features/monitoring-profile/technical_spec.md
    specs/features/monitoring-profile/task_spec.md
    specs/features/signal-collection/test_plan.md
    specs/features/signal-collection/technical_spec.md
    specs/features/signal-collection/task_spec.md
    specs/features/signal-feed-triage/test_plan.md
    specs/features/signal-feed-triage/technical_spec.md
    specs/features/signal-feed-triage/task_spec.md
    specs/features/README.md
    specs/features/application-core/test_plan.md
    specs/features/application-core/technical_spec.md
    specs/features/application-core/task_spec.md
    specs/design/README.md
    specs/design/index.html
    ✓ • 0ms

## Activity

    $ sed -n '1,200p' specs/architecture-tech-stack.md
    # SignalScout — MVP architecture and tech stack
    
    **Status:** Proposed implementation specification
    **Product scope:** [Phase 1 MVP PRD](phase-1-prd.md)
    **UI reference:** [Approved HTML prototype](design/index.html)
    **Last updated:** 2026-09-29
    
    ## Architecture decision
    
    Build one Python codebase with three long-running local services: a FastAPI web process, a collection worker, and PostgreSQL. A one-shot migration task prepares the database before web and worker start. The web process serves the approved HTML/CSS/JavaScript UI and a small JSON API. The worker performs scheduled and manual collection. Both Python processes share models and source adapters. PostgreSQL holds the profile, run history, source items, signals, and triage state.
    
    ```mermaid
    flowchart LR
        B[Browser UI] -->|same-origin JSON API| W[FastAPI web process]
        W --> P[(PostgreSQL)]
        C[Collection worker] --> P
        C --> S[X, web, HN, Reddit, GitHub, RSS/APIs]
        C --> A[xAI and optional Gemini]
    ```
    
    This avoids a frontend build system, Redis, and a separate queue while keeping slow external calls out of web requests. FastAPI can [serve static files](https://fastapi.tiangolo.com/tutorial/static-files/) and define validated [response models](https://fastapi.tiangolo.com/tutorial/response-model/). Its [background task guidance](https://fastapi.tiangolo.com/tutorial/background-tasks/) is aimed at smaller in-process work, so collection has its own worker.
    
    ## Stack
    
    | Layer | Choice | Reason |
    |---|---|---|
    | UI | Existing HTML/CSS, vanilla JavaScript, `fetch` | Reuse the approved prototype. Replace hard-coded arrays with API data. |
    | Web/API | Python 3.12+ and FastAPI | One small API with request validation and clear contracts. |
    | Database | PostgreSQL 17+ | Persistent store with constraints, indexes, JSONB, and transactional job claims. |
    | Data access | SQLAlchemy 2.x with `psycopg` 3 | Explicit PostgreSQL driver and synchronous code path for this small app. [Dialect reference](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg). |
    | Migrations | Alembic | Versioned database schema changes. [Official tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html). |
    | HTTP providers | `httpx` and thin source adapters; official SDK where a search tool requires it | Keep provider details behind one interface. |
    | Local runtime | Docker Compose: `web`, `worker`, `db`, plus one-shot `migrate` | One command to run the stack locally with a persistent database volume. Compose can wait for a [healthy database](https://docs.docker.com/compose/how-tos/startup-order/). |
    
    Pin compatible package and container versions when implementation begins; do not depend on floating `latest` tags.
    
    ## Deployment and process behavior
    
    - **Local-only MVP:** Publish the web port on `127.0.0.1`, keep PostgreSQL private to Compose, and assume one trusted operator. Hosting or shared access requires authentication and a separate deployment design.
    - **Web process:** Serves `/` and static assets, reads and writes PostgreSQL through the API, and does not call slow source APIs during a request.
    - **Worker process:** Polls queued jobs, schedules one run every four hours, executes enabled source adapters, and persists source results and status. Deploy exactly one worker instance for the MVP.
    - **Migrations:** A one-shot Compose task runs Alembic before web and worker start, after the database health check passes.
    - **Time:** Store UTC timestamps and render local time in the browser. Use fixed four-hour UTC slots for scheduled jobs.
    - **First run:** Saving a non-empty profile for the first time queues collection immediately, independent of the next scheduled slot.
    
    ## API contract
    
    All endpoints use JSON except the static UI. Mutations require a same-origin request; local binding is not a substitute for validation.
    
    | Endpoint | Purpose |
    |---|---|
    | `GET /api/profile` | Profile rules, source toggles, and schedule. |
    | `PUT /api/profile` | Replace the singleton profile atomically after validation. |
    | `GET /api/signals` | Paginated feed; `source`, `topic`, `from`, `to`, `min_engagement`, and `state` filters; newest first. |
    | `GET /api/signals/{id}` | Detail, matched rules, metrics, and contributing source items. |
    | `PATCH /api/signals/{id}/state` | Set saved, dismissed, and interesting flags. |
    | `GET /api/summary` | Feed counts and last review time for the top cards. |
    | `POST /api/feed-reviewed` | Record that the current feed has been displayed so the next visit can count new signals. |
    | `GET /api/collection-runs` | Recent runs with per-source status and safe error summaries. |
    | `POST /api/collection-runs` | Queue manual collection; return an existing active run if one exists. |
    | `GET /api/health` | Process and database readiness. |
    
    Use bounded pagination (for example, 50 signals per page). Return stable IDs and ISO 8601 timestamps. Show useful empty states when no source is available or no signal matches the filters.
    
    For a grouped signal, use the most recently published linked source item as its displayed timestamp and primary metric. A source filter matches any linked source item, while the engagement filter uses that displayed primary metric. Capture the previous `last_reviewed_at` before recording a new feed view so the “new since last visit” card remains stable during that visit.
    
    ## PostgreSQL data model
    
    | Table | Important fields and constraints |
    |---|---|
    | `monitor_profile` | Singleton ID, created/updated timestamps, last reviewed timestamp. |
    | `monitor_rule` | Profile ID, kind (`topic`, `include`, `exclude`, `competitor`, `person`), value, normalized value; unique `(profile_id, kind, normalized_value)`. |
    | `source_config` | Profile ID, source key, enabled flag; unique `(profile_id, source_key)`. No credentials. |
    | `collection_run` | ID, trigger (`initial`, `scheduled`, `manual`), status (`queued`, `running`, `complete`, `partial`, `failed`), optional unique scheduled slot, profile snapshot JSONB, queued/started/finished timestamps. |
    | `source_run` | Run ID, source key, status (`complete`, `failed`, `unavailable`, `skipped`), hit/accepted/error counts, started/finished timestamps, safe error code/message. |
    | `source_item` | Source key, stable external ID (or canonical URL hash when no ID exists), source URL, canonical content URL, title, snippet, published time, metric name/value, fetched time, linked signal ID; unique `(source_key, external_id)`. |
    | `signal` | ID, canonical URL key, title, snippet, published time, created/updated timestamps. The primary source is derived from linked source items. |
    | `signal_topic` | Signal ID and topic rule ID; unique pair. |
    | `signal_state` | Signal ID (unique for this one operator), saved/dismissed/interesting booleans and their timestamps. |
    
    Index `signal(published_at DESC, id DESC)`, `source_item(signal_id, source_key)`, `signal_topic(topic_rule_id, signal_id)`, and `collection_run(queued_at DESC)`. Use migrations for constraints; do not rely on application checks alone. Keep source-specific metrics in a small JSONB field only when a standard metric name/value is insufficient.
    
    ## Collection pipeline
    
    1. **Create run:** A scheduled slot or manual request inserts a queued run. The API returns quickly. If a run is queued or running, manual refresh returns that run instead of enqueueing another.
    2. **Build queries:** Expand saved topics, include/exclude terms, competitors, and people into a bounded set of source-specific searches. Disabled sources are skipped.
    3. **Fetch:** Each adapter returns normalized candidate items with a stable URL and provenance. Enforce per-source timeouts, pagination caps, and retries only for transient failures.
    4. **Filter and enrich:** Apply exclude rules first, attach matched topics, and optionally ask Gemini to classify borderline web results or extract structured page fields. Validate model output and keep its cost budget small.
    5. **Deduplicate:** Upsert `(source_key, external_id)`. Resolve a canonical content URL by stripping known tracking parameters and honoring a trusted canonical link where available. Match an existing signal by canonical URL; otherwise use normalized title plus target host and a short published-time window. If uncertain, keep separate signals. Every source item remains linked to its signal.
    6. **Persist and report:** Commit successful source batches, update feed records, and record counts and safe errors per source. Mark the run complete, partial, or failed based on those outcomes.
    
    Do not create a feed item from an AI-written answer alone. xAI's documented [Web Search](https://docs.x.ai/developers/tools/web-search) and [X Search](https://docs.x.ai/developers/tools/x-search) tools can discover current items; the adapter must extract and retain real source URLs. Gemini supports [structured output](https://ai.google.dev/gemini-api/docs/structured-output), which should be schema validated after receipt.
    
    ### Source adapter plan
    
    | Source | Adapter plan | Availability rule |
    |---|---|---|
    | X | xAI X Search for recent matching public posts. | Requires configured xAI key and permitted use. |
    | Web / news | xAI Web Search for discovery, page fetch where permitted, optional Gemini extraction. | Requires configured xAI key; Gemini failure should not discard otherwise usable items. |
    | Hacker News | Read recent items from the [official HN API](https://github.com/HackerNews/API), then match locally; the API is not a keyword search service. | Available without a key, subject to normal request limits. |
    | Reddit | Use approved Reddit API access to search posts and comments for the saved terms; no subreddit configuration UI. | Mark unavailable if credentials or permission are missing; do not scrape as a fallback. [API terms](https://redditinc.com/policies/data-api-terms). |
    | GitHub | Use documented REST search/list endpoints for public repos and issues; include discussions only where a supported endpoint and access exist. | Respect API limits; token is optional where anonymous requests suffice. [GitHub REST docs](https://docs.github.com/en/rest/using-the-rest-api). |
    | RSS / selected APIs | Poll configured RSS URLs; add a named API adapter only when its key and contract are known. | A missing feed list or API key disables only that source. |
    
    ## Failure, cost, and security rules
    
    - A source timeout or unavailable credential records a source-level error. Successful sources still publish results. Previously stored results stay visible with their original timestamps.
    - Store only safe error codes and summaries in PostgreSQL and the UI; redact headers, tokens, query secrets, and provider payloads from logs.
    - Keep provider keys in local `.env` or deployment secrets, never in PostgreSQL or browser responses. Required: `DATABASE_URL`. Optional by source: `XAIGROK_API_KEY`, `GEMINI_API_KEY`, `GITHUB_TOKEN`, approved Reddit credentials, and `RSS_FEED_URLS`. Provide `.env.example` with names and no values.
    - Budget external queries per source and run. Cache repeated search requests briefly and use published-time cursors where providers support them. Record request counts and duration per source run.
    - Treat fetched content as untrusted data. Escape it in the UI, validate URLs before linking or fetching, and never obey instructions embedded in source content.
    - Reject cross-origin mutating requests and bind only to localhost for the MVP. Do not expose this no-auth build on a public interface.
    - Before shipping each connector, confirm its current API access, rate limits, and retention terms. Retain normalized metadata and snippets needed for the feed rather than full external payloads by default.
    
    ## Build sequence
    
    1. Build the [Application Core](features/application-core/task_spec.md): shared Python package, Compose services, PostgreSQL connection, migrations, static UI, health endpoint, and idle worker entry point.
    2. Add the Monitoring profile tables and API together with the minimal Collection run table needed for first-run enqueue.
    3. Add Feed storage, deduplication, filters, detail, and triage using fixed source-item fixtures; connect the UI to the API.
    4. Add the Collection worker loop and one source adapter end to end.
    5. Add remaining source adapters, per-source status, partial failures, and the four-hour schedule.
    
    The MVP is ready when the [PRD acceptance criteria](phase-1-prd.md#functional-acceptance-criteria) hold with configured source access. Detailed work is listed in the [feature index](features/README.md). Trend computation, a frontend framework, Redis/Celery, user accounts, and hosted deployment are outside this architecture.
    ✓ • 0ms

## Activity

    $ find .codex/skills -maxdepth 3 -type f -print
    .codex/skills/test-driven-development/SKILL.md
    .codex/skills/spec-driven-development/SKILL.md
    ✓ • 0ms

## Activity

    $ sed -n '1,180p' specs/phase-1-prd.md
    # SignalScout — Phase 1 MVP PRD
    
    **Product:** SignalScout
    **Status:** Scope agreed from the [UI prototype](design/index.html)
    **Last updated:** 2026-09-29
    
    ## Summary
    
    SignalScout helps a content or communications lead find timely conversations for thought leadership. The MVP lets one operator configure what to watch, collect signals from several sources, and review one deduplicated feed. The operator can filter signals and save, dismiss, or mark them interesting. It does not generate or publish content.
    
    The MVP has three screens: **Signal feed**, **Monitoring**, and **Collection**. The [architecture specification](architecture-tech-stack.md) describes the product-wide implementation. Smaller feature specifications are listed in the [feature index](features/README.md).
    
    ## Product decisions for this MVP
    
    | Decision | MVP choice |
    |---|---|
    | Operator and deployment | One default workspace and one trusted operator, run locally. No sign-in or team management. |
    | Collection cadence | Every four hours, plus manual refresh. Saving the first monitoring profile queues an initial run. |
    | Feed order | Newest published signal first. |
    | Engagement threshold | One optional numeric feed filter. Each card displays its source's unit (likes, points, stars, etc.); no cross-source score or collection-time cutoff. |
    | Interesting signals | Mark and filter in the UI. Export is deferred. |
    | Trends | Trend, velocity, and acceleration calculations and screens are deferred. |
    
    ## Problem and users
    
    Signals are scattered across X, news, forums, code communities, and feeds. Manual review is slow, and the same story often appears in several places.
    
    - **Primary user:** A content or communications lead who owns monitoring and follow-up.
    - **Secondary user:** A founder or subject-matter expert using the same single-operator workflow.
    
    ## MVP goals
    
    | Goal | Expected outcome |
    |---|---|
    | Configurable monitoring | Topics, include/exclude keywords, competitors, people, and source toggles guide collection. |
    | Unified feed | One chronological list with source provenance and duplicate hits grouped. |
    | Useful triage | Save, dismiss, and mark interesting actions persist between sessions. |
    | Visible collection health | The operator sees the last run, per-source status, and partial failures. |
    
    ## Product scope
    
    ### Monitoring
    
    - Add and remove topics, include keywords, exclude keywords, competitors, and influential people. Changing an entry can be done by removing and adding it again; a separate edit dialog is not required.
    - Competitors may use a name, domain, or handle. People may use a name, handle, or profile URL.
    - Enable or disable each supported source. The saved profile persists in PostgreSQL.
    - Keep API credentials outside the UI and database. Missing credentials appear as an unavailable source in Collection.
    
    ### Collection
    
    | Source | MVP collection expectation |
    |---|---|
    | X | Recent public posts matching configured topics and tracked entities through a permitted search integration. |
    | Web / news | Current pages and articles discovered by web search; fetch and extract enough text for a useful signal. |
    | Hacker News | Recent stories and comments checked against configured terms. |
    | Reddit | Posts and comments found by search for configured terms, subject to approved API access. No subreddit picker is required. |
    | GitHub | Relevant public repositories, issues, and discussions where the selected API supports them. |
    | RSS / selected APIs | Items from feeds configured in the environment and selected APIs with available credentials. |
    
    - A scheduled run starts every four hours. The operator can request a manual run. An already queued or running collection is reused rather than duplicated.
    - A run records start/end time, trigger, status, and per-source counts and errors. A source failure makes the run **partial**, while successful sources still update the feed.
    - A failed provider may leave its last successfully collected results visible. The UI must label the source failure and must not imply those results are fresh.
    - Store title, snippet, URL, source, published time, source-specific engagement, matched topics, and provenance for each accepted result. Discard items without a stable source URL.
    - Apply practical query budgets, rate limits, and incremental fetches to control provider cost.
    
    ### Signal feed and detail
    
    - Show one chronological feed of deduplicated signals, with contributing sources available in detail.
    - Group repeated hits by canonical content URL first; use normalized titles and a short time window for conservative cross-source matching. Keep underlying source items so provenance is not lost.
    - Filter by source, topic, date range, and minimum engagement. The engagement threshold applies to the displayed primary metric of each source and does not imply comparable popularity across sources.
    - Detail shows the full available snippet, why the signal matched, source metrics, contributing sources, and a link to the original item.
    - **Save:** bookmark for later. **Dismiss:** hide from the default feed but retain in a Dismissed view. **Interesting:** mark as a positive follow-up signal. These flags can coexist and can be reversed.
    - Include All, Saved, Interesting, and Dismissed views. The default All view excludes dismissed signals.
    
    ## Core user flows
    
    1. **Set up monitoring:** Add topics and terms, optionally add competitors and people, select sources, and save. The first run is queued.
    2. **Collect:** Wait for the four-hour schedule or select manual refresh. See running, complete, partial, or failed status by source.
    3. **Review:** Filter the feed, open a signal, follow its original link, and save, dismiss, or mark it interesting.
    4. **Return later:** See new signals since the last review and revisit Saved, Interesting, or Dismissed items.
    
    ## AI-assisted search
    
    | Capability | Environment variable | MVP use |
    |---|---|---|
    | Web and X discovery | `XAIGROK_API_KEY` | xAI web and X search tools discover recent source items and URLs. |
    | Page understanding | `GEMINI_API_KEY` | Optional extraction or relevance check for ambiguous web results; output must be validated before storage. |
    
    Credentials load from `.env` at runtime and are never committed. If either provider is unavailable, the affected source reports an error and other sources continue. Query expansion and relevance checks are bounded by per-run budgets. Generated text is never accepted as a signal without a verifiable source URL.
    
    ## Functional acceptance criteria
    
    - [ ] Monitoring entries and source toggles can be changed and survive a restart.
    - [ ] An initial, scheduled, and manual collection can be observed in the Collection screen.
    - [ ] Each enabled source with configured, permitted access can contribute normalized signals; unavailable sources show a clear reason.
    - [ ] Repeated source items do not create repeated feed cards, and grouped items retain provenance.
    - [ ] Source, topic, date, and engagement filters work together.
    - [ ] Save, dismiss, and interesting actions persist and can be reversed.
    - [ ] A partial run retains successful results and reports the failing source.
    - [ ] No API key appears in the browser, logs, or committed files.
    
    ## Conceptual data
    
    - **Monitoring profile and rules:** The single workspace's topics, terms, competitors, people, and enabled sources.
    - **Collection run and source run:** Trigger, status, timestamps, counts, and safe error summaries.
    - **Source item:** A normalized result from one external source, including URL, source ID, time, metric, and matched rules.
    - **Signal:** The deduplicated feed item linked to one or more source items.
    - **Signal state:** Saved, dismissed, and interesting flags with timestamps for the default operator.
    
    ## Success measures
    
    - First useful feed within 15 minutes of saving the initial profile, assuming at least one source is configured and available.
    - Qualitative beta feedback on the share of saved or interesting signals the operator would not have found manually.
    - Duplicate hits grouped per 100 raw hits, with manual review of mistaken merges.
    - Per-source collection success rate and p95 run duration.
    
    ## Risks and handling
    
    | Risk | Handling |
    |---|---|
    | Provider access, limits, or terms change | Keep a separate adapter per source, use only permitted access, and show unavailable/partial status. |
    | Search cost | Four-hour batches, query budgets, caching, and incremental fetches. |
    | Noisy results | Include/exclude rules and an optional bounded Gemini relevance check. |
    | Mistaken duplicate grouping | Conservative matching and retained source items. |
    | Stale results after a failure | Keep last good items but surface the source's latest failure and run time. |
    
    ## Deferred scope
    
    Trends and acceleration; exports and webhooks; content briefs, drafting, and publishing; outreach and CRM; team workflows and alerts; hosted multi-user access, SSO, billing, and advanced roles; sub-second streaming.
    ✓ • 0ms

## Activity

    $ ls -la && if [ -f AGENTS.md ]; then cat AGENTS.md; fi
    total 80
    drwxr-xr-x@ 19 pasivuorio  staff   608 Sep 29 11:14 .
    drwxr-xr-x@  4 pasivuorio  staff   128 Sep 29 09:49 ..
    drwxr-xr-x@  3 pasivuorio  staff    96 Sep 29 10:49 .codex
    -rw-r--r--@  1 pasivuorio  staff    65 Sep 29 11:13 .dockerignore
    -rw-r--r--@  1 pasivuorio  staff   155 Sep 29 09:53 .env
    -rw-r--r--@  1 pasivuorio  staff   509 Sep 29 11:13 .env.example
    -rw-r--r--@  1 pasivuorio  staff    73 Sep 29 11:13 .gitignore
    drwxr-xr-x@  6 pasivuorio  staff   192 Sep 29 11:09 .pytest_cache
    drwxr-xr-x@  8 pasivuorio  staff   256 Sep 29 11:09 .venv
    -rw-r--r--@  1 pasivuorio  staff  2519 Sep 29 11:00 AGENTS.md
    -rw-r--r--@  1 pasivuorio  staff   394 Sep 29 11:13 Dockerfile
    -rw-r--r--@  1 pasivuorio  staff  2748 Sep 29 11:14 README.md
    -rw-r--r--@  1 pasivuorio  staff   487 Sep 29 11:12 alembic.ini
    -rw-r--r--@  1 pasivuorio  staff  1513 Sep 29 11:13 compose.yaml
    drwxr-xr-x@  5 pasivuorio  staff   160 Sep 29 11:13 migrations
    -rw-r--r--@  1 pasivuorio  staff   637 Sep 29 11:09 pyproject.toml
    drwxr-xr-x@  6 pasivuorio  staff   192 Sep 29 10:57 specs
    drwxr-xr-x@  4 pasivuorio  staff   128 Sep 29 11:10 src
    drwxr-xr-x@  7 pasivuorio  staff   224 Sep 29 11:11 tests
    # SignalScout project workflow
    
    Apply this workflow to every request in this repository. The latest explicit user instruction takes precedence if it changes the requested scope or process.
    
    ## Start from the product and feature specs
    
    Keep the product-wide PRD at `specs/phase-1-prd.md`, architecture at `specs/architecture-tech-stack.md`, and design in `specs/design/`. Do not move or replace these with feature documents. Read the relevant product-wide documents and feature folder, and use `.codex/skills/spec-driven-development/SKILL.md` for spec work.
    
    Each smaller feature has one folder, `specs/features/<feature-slug>/`, with three required Markdown files:
    
    - `task_spec.md`: intended behavior, scope, and acceptance criteria.
    - `technical_spec.md`: implementation design and material technical decisions.
    - `test_plan.md`: meaningful verification cases and exit criteria.
    
    Keep feature-specific prototypes and extra documents in that feature folder; shared product design remains in `specs/design/`. Before implementation, reconcile the request with the product-wide and feature documents. Update the root documents for product-wide decisions and the feature documents for local behavior. For a new feature, create the three documents before writing behavior. For a question or review, read the relevant specs and answer without creating placeholder documents.
    
    ## Implement with TDD
    
    For every change to runnable behavior, use `.codex/skills/test-driven-development/SKILL.md`. The standing project instruction is to write a meaningful failing test for the next observable behavior, confirm the intended failure, make the smallest code change to pass it, and refactor while green. Repeat for each distinct behavior. Use existing test conventions and keep external calls out of the normal test loop.
    
    If no test harness exists, add only what is needed to exercise the behavior. If a failing test cannot be run because of an environment blocker, report that limitation and do not claim a completed TDD cycle. Documentation-only, research, and status requests do not require test execution; keep `test_plan.md` aligned when they change acceptance criteria.
    
    ## Finish against the contract
    
    Compare the result with the PRD, architecture, and relevant feature's `task_spec.md`, `technical_spec.md`, and `test_plan.md`. Report completed behavior, verification performed, and any unmet or unverified acceptance criteria. Update the appropriate root or feature document when implementation changes an agreed decision.
    ✓ • 0ms

## Activity

    Opened https://owasp.org/www-project-top-ten/

## Activity

    $ cat specs/design/README.md
    # SignalScout Phase 1 UI prototype
    
    Open `index.html` in a browser. It is a standalone, local scope prototype with illustrative data and session-only interactions.
    
    ## Included flows
    
    - **Signal feed:** a chronological, deduplicated feed with source, topic, date, and engagement filters; detail view; save, interesting, and dismiss actions.
    - **Monitoring:** edit topics, include and exclude keywords, competitors, people, and enabled sources.
    - **Collection:** scheduled and manual batch concept, source level status, and partial result handling.
    
    ## Scope assumptions shown in the UI
    
    - A single default workspace and user are shown for Phase 1.
    - The example schedule is every four hours. Manual refresh is available.
    - The engagement filter uses one numeric threshold against each signal's displayed source metric; the unit remains visible on the card.
    - Web search failure leaves other source results visible and shows the last cached web results.
    - Source URLs and content are fictional examples. No provider or backend is connected.
    
    ## MVP decisions reflected in the PRD
    
    - One local workspace and trusted operator, without sign-in.
    - Collection every four hours, plus manual refresh.
    - One numeric feed engagement filter; source-specific units remain visible and there is no collection-time threshold.
    - Interesting signals can be marked and filtered. Export is deferred.
    
    See the [Phase 1 PRD](../phase-1-prd.md) and [architecture specification](../architecture-tech-stack.md) for product-wide scope. Smaller specifications are listed in the [feature index](../features/README.md).
    
    Trend and acceleration views are deferred from this MVP prototype. Content drafting, publishing, outreach, team workflows, alerts, SSO, billing, and advanced roles are also outside this scope.
    ✓ • 0ms

## Activity

    $ sed -n '1,180p' specs/features/application-core/task_spec.md && sed -n '1,160p' specs/features/application-core/test_plan.md
    # Application core — task spec
    
    **Parent architecture:** [MVP architecture and stack](../../architecture-tech-stack.md)
    **Order:** Build this foundation before [Monitoring](../monitoring-profile/task_spec.md), [Collection](../signal-collection/task_spec.md), and [Feed](../signal-feed-triage/task_spec.md).
    
    ## Outcome
    
    Start SignalScout locally as a web process, a worker process, and PostgreSQL from one codebase. The web process serves the approved UI as clearly labeled sample data, connects to PostgreSQL, and reports readiness. The worker starts and waits for future collection work. Feature APIs and source integrations are built on this foundation afterward.
    
    ## Implementation tasks
    
    1. [x] Create the Python project, pinned dependency manifest, and shared package layout for web, worker, configuration, and database access.
    2. [x] Add typed configuration loaded from environment variables, plus `.env.example` containing names but no secrets.
    3. [x] Configure SQLAlchemy with `psycopg` and Alembic. Make migrations run before either long-running process starts; leave feature tables to their own feature migrations.
    4. [x] Create the FastAPI entry point, serve the approved static prototype at `/`, and expose `GET /api/health` with a real PostgreSQL readiness check.
    5. [x] Create a separate worker entry point that starts, connects to PostgreSQL, stays alive while idle, and shuts down cleanly. It does not poll collection jobs yet.
    6. [x] Add Dockerfile and Compose setup for PostgreSQL, a one-shot migration task, web, and worker. Persist PostgreSQL data and publish only the web port to `127.0.0.1`.
    7. [x] Document the exact local start, stop, migration, and environment setup commands in the repository README.
    
    ## Acceptance criteria
    
    - A new developer can start the local stack from documented commands after supplying a local database password. PostgreSQL is persistent; the web and worker share one configured database.
    - Database readiness and migrations complete before web and worker are marked ready. Restarting the stack does not rerun destructive setup or erase data.
    - `/` renders the approved prototype with its sample-data labeling. No mock interaction is presented as persisted functionality.
    - `GET /api/health` returns success only when the web process can query PostgreSQL; it returns an error status when the database is unavailable.
    - The worker starts without source credentials, remains healthy while idle, and exits cleanly on shutdown.
    - Secrets stay out of tracked files, browser responses, and normal logs. The database has no host-exposed port, and the web port binds to localhost.
    
    ## Boundaries
    
    The core does not add profile CRUD, collection jobs or adapters, normalized signals, feed APIs, triage persistence, authentication, or hosted deployment. Those belong to the later feature specifications. No placeholder domain tables are needed solely to prove migrations work.
    # Application core — test plan
    
    **Delivery contract:** [Task spec](task_spec.md)
    **Status:** Implemented and verified on 2026-09-29 with a disposable PostgreSQL 17 database and local Docker Compose stack.
    
    Follow the repository's TDD rule when implementation begins. The first runnable behavior should have a failing test before production code. Use a disposable PostgreSQL instance for integration checks and keep provider credentials out of the test environment.
    
    | Case | Level | Scenario | Expected result |
    |---|---|---|---|
    | CORE-01 | Integration | Start the web app with a reachable migrated PostgreSQL database. | `GET /api/health` returns `200`; the request opens and closes a DB session cleanly. |
    | CORE-02 | Integration | Make PostgreSQL unavailable after startup. | `GET /api/health` returns `503` and a safe fixed error; no connection string or password appears. |
    | CORE-03 | HTTP/UI | Request `/` and its static assets. | The approved prototype renders with sample-data labeling and no broken local asset path. |
    | CORE-04 | Configuration | Omit `DATABASE_URL`, then provide a malformed value. | Startup fails clearly without logging the secret. Missing optional provider keys do not block startup. |
    | CORE-05 | Migration | Apply migrations to a fresh database and then apply them again. | Both commands succeed; the second is idempotent and no user data is deleted. |
    | CORE-06 | Process | Start the worker against the migrated database, leave it idle, then terminate it. | It remains alive without source keys, logs readiness, and exits cleanly. |
    | CORE-07 | Compose | Start the full stack from documented commands with a fresh volume. | DB health precedes migration; migration precedes web/worker; only the web port is reachable from the host. |
    | CORE-08 | Persistence | Restart the stack without deleting the named volume. | Database state and Alembic revision persist. |
    
    ## Exit criteria
    
    CORE-01 through CORE-06 pass in targeted automated checks. CORE-07 and CORE-08 pass as local Compose integration checks. The documented start command reproduces the working stack on a clean checkout. No feature behavior is claimed complete by these core checks.
    
    ## Verification record
    
    - `TEST_DATABASE_URL=... .venv/bin/python -m pytest -q`: 11 passed. The integration database ran in a disposable PostgreSQL 17 container.
    - `docker compose --env-file <temporary-test-env> up --build -d --wait`: PostgreSQL, web, and worker became healthy. Migration completed before web and worker started. `/api/health` returned 200 and `/` served the sample prototype.
    - `docker compose ps`: PostgreSQL had no published host port; the web port was bound to `127.0.0.1`.
    - Stopping PostgreSQL after startup changed `/api/health` to 503 with the fixed body `{"detail":"Database unavailable"}`.
    - A full `docker compose down` followed by `up -d --wait` retained the Alembic revision and a temporary marker row. Normal service logs contained no temporary password or database URL.
    ✓ • 0ms

## Activity

    $ ls -la /Users/pasivuorio/.codex/skills/.system/skill-creator/scripts && sed -n '1,160p' /Users/pasivuorio/.codex/skills/.system/skill-creator/scripts/quick_validate.py
    total 56
    drwxr-xr-x@ 5 pasivuorio  staff    160 Sep 12 18:45 .
    drwxr-xr-x@ 8 pasivuorio  staff    256 Sep 12 18:45 ..
    -rw-r--r--@ 1 pasivuorio  staff   6669 Sep 12 18:45 generate_openai_yaml.py
    -rw-r--r--@ 1 pasivuorio  staff  10314 Sep 12 18:45 init_skill.py
    -rw-r--r--@ 1 pasivuorio  staff   4249 Sep 12 18:45 quick_validate.py
    #!/usr/bin/env python3
    """
    Quick validation script for skills - minimal version
    """
    
    import re
    import sys
    from pathlib import Path
    
    import yaml
    
    MAX_SKILL_NAME_LENGTH = 64
    
    
    def validate_skill(skill_path):
        """Basic validation of a skill"""
        skill_path = Path(skill_path)
    
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return False, "SKILL.md not found"
    
        content = skill_md.read_text()
        if not content.startswith("---"):
            return False, "No YAML frontmatter found"
    
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return False, "Invalid frontmatter format"
    
        frontmatter_text = match.group(1)
    
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
            if not isinstance(frontmatter, dict):
                return False, "Frontmatter must be a YAML dictionary"
        except yaml.YAMLError as e:
            return False, f"Invalid YAML in frontmatter: {e}"
    
        allowed_properties = {"name", "description", "license", "allowed-tools", "metadata"}
    
        unexpected_keys = set(frontmatter.keys()) - allowed_properties
        if unexpected_keys:
            allowed = ", ".join(sorted(allowed_properties))
            unexpected = ", ".join(sorted(unexpected_keys))
            return (
                False,
                f"Unexpected key(s) in SKILL.md frontmatter: {unexpected}. Allowed properties are: {allowed}",
            )
    
        if "name" not in frontmatter:
            return False, "Missing 'name' in frontmatter"
        if "description" not in frontmatter:
            return False, "Missing 'description' in frontmatter"
    
        name = frontmatter.get("name", "")
        if not isinstance(name, str):
            return False, f"Name must be a string, got {type(name).__name__}"
        name = name.strip()
        if name:
            if not re.match(r"^[a-z0-9-]+$", name):
                return (
                    False,
                    f"Name '{name}' should be hyphen-case (lowercase letters, digits, and hyphens only)",
                )
            if name.startswith("-") or name.endswith("-") or "--" in name:
                return (
                    False,
                    f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens",
                )
            if len(name) > MAX_SKILL_NAME_LENGTH:
                return (
                    False,
                    f"Name is too long ({len(name)} characters). "
                    f"Maximum is {MAX_SKILL_NAME_LENGTH} characters.",
                )
    
        description = frontmatter.get("description", "")
        if not isinstance(description, str):
            return False, f"Description must be a string, got {type(description).__name__}"
        description = description.strip()
        if description.startswith("[TODO:"):
            return False, "Description contains an unfinished TODO placeholder"
        if description:
            if "<" in description or ">" in description:
                return False, "Description cannot contain angle brackets (< or >)"
            if len(description) > 1024:
                return (
                    False,
                    f"Description is too long ({len(description)} characters). Maximum is 1024 characters.",
                )
    
        body = content[match.end() :]
        fence_marker = None
        fence_length = 0
        for line in body.splitlines():
            fence = re.match(r"^[ \t]*(?:(?:[-+*]|\d+[.)])[ \t]+)?(`{3,}|~{3,})(.*)$", line)
            if fence:
                marker = fence.group(1)
                if fence_marker is None:
                    fence_marker = marker[0]
                    fence_length = len(marker)
                elif (
                    marker[0] == fence_marker
                    and len(marker) >= fence_length
                    and not fence.group(2).strip()
                ):
                    fence_marker = None
                    fence_length = 0
                continue
    
            if fence_marker is None and re.fullmatch(
                r"[ ]{0,3}\[TODO:[^\n]*\][ \t]*", line
            ):
                return False, "Skill instructions contain an unfinished TODO placeholder"
    
        return True, "Skill is valid!"
    
    
    if __name__ == "__main__":
        if len(sys.argv) != 2:
            print("Usage: python quick_validate.py <skill_directory>")
            sys.exit(1)
    
        valid, message = validate_skill(sys.argv[1])
        print(message)
        sys.exit(0 if valid else 1)
    ✓ • 0ms

## Assistant

The MVP specs explicitly define a local, single-operator app without sign-in, so the security review will check that trust boundary and require authentication review when a feature changes it. I’m adding a review step that records evidence for each acceptance case, uses browser screenshots for UI work, and checks the current OWASP Top 10 where applicable.

## Activity

    file changes: Completed · 2 changes
    Add: /Users/pasivuorio/training/signal-scout/.codex/skills/feature-review/SKILL.md
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
    Update { move_path: None }: /Users/pasivuorio/training/signal-scout/AGENTS.md
    @@ -22,2 +22,6 @@
     
    +## Review the feature
    +
    +After implementing a feature with the spec-driven and test-driven workflows, use `.codex/skills/feature-review/SKILL.md` to validate it against the specs, test cases, approved design, security and privacy requirements, architecture, and feature-specific risks. For UI work, inspect the running app and prototype in a browser and save comparison screenshots in a temporary folder. Record findings and any acceptance criteria that remain unverified. An explicit review request uses the same skill without requiring implementation first.
    +
     ## Finish against the contract

## Activity

    $ sed -n '1,240p' .codex/skills/feature-review/SKILL.md && sed -n '20,80p' AGENTS.md
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
    
    If no test harness exists, add only what is needed to exercise the behavior. If a failing test cannot be run because of an environment blocker, report that limitation and do not claim a completed TDD cycle. Documentation-only, research, and status requests do not require test execution; keep `test_plan.md` aligned when they change acceptance criteria.
    
    ## Review the feature
    
    After implementing a feature with the spec-driven and test-driven workflows, use `.codex/skills/feature-review/SKILL.md` to validate it against the specs, test cases, approved design, security and privacy requirements, architecture, and feature-specific risks. For UI work, inspect the running app and prototype in a browser and save comparison screenshots in a temporary folder. Record findings and any acceptance criteria that remain unverified. An explicit review request uses the same skill without requiring implementation first.
    
    ## Finish against the contract
    
    Compare the result with the PRD, architecture, and relevant feature's `task_spec.md`, `technical_spec.md`, and `test_plan.md`. Report completed behavior, verification performed, and any unmet or unverified acceptance criteria. Update the appropriate root or feature document when implementation changes an agreed decision.
    ✓ • 0ms

## Activity

    $ rg -n 'feature-review|## Review the feature|## Finish against the contract' AGENTS.md .codex/skills/feature-review/SKILL.md && find .codex/skills/feature-review -maxdepth 2 -type f -print
    .codex/skills/feature-review/SKILL.md:2:name: feature-review
    AGENTS.md:23:## Review the feature
    AGENTS.md:25:After implementing a feature with the spec-driven and test-driven workflows, use `.codex/skills/feature-review/SKILL.md` to validate it against the specs, test cases, approved design, security and privacy requirements, architecture, and feature-specific risks. For UI work, inspect the running app and prototype in a browser and save comparison screenshots in a temporary folder. Record findings and any acceptance criteria that remain unverified. An explicit review request uses the same skill without requiring implementation first.
    AGENTS.md:27:## Finish against the contract
    .codex/skills/feature-review/SKILL.md
    ✓ • 0ms

## Activity

    $ python /Users/pasivuorio/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/feature-review
    Skill is valid!
    ✓ • 95ms

## Assistant

Created [feature-review](/Users/pasivuorio/training/signal-scout/.codex/skills/feature-review/SKILL.md) and added it after the spec-driven and TDD steps in [AGENTS.md](/Users/pasivuorio/training/signal-scout/AGENTS.md:23).

The skill covers acceptance criteria and test-plan evidence, browser comparison with temporary screenshots for UI features, security and privacy using the [OWASP Top 10](https://owasp.org/projects/top-ten), architecture, and feature-specific risks. Skill validation passed. This was a documentation-only change, so no feature review or browser comparison was run.
