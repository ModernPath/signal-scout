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
