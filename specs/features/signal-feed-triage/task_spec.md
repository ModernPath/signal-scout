# Signal feed and triage — task spec

**Parent scope:** [Phase 1 MVP PRD](../../phase-1-prd.md)  
**Related design:** [Signal feed screen](../../design/index.html)

## Outcome

The operator reviews one chronological, deduplicated feed, sees why a signal appeared, and keeps or hides items for follow-up.

## In scope

- Group repeated source hits into one signal while retaining every contributing source item.
- Show title, snippet, primary source and its engagement unit, topic, publication time, and contributing-source count.
- Filter the feed by source, topic, date range, minimum engagement, and triage state. Sort newest first.
- Open detail to see matched terms, metrics, contributing sources, and an original-item link.
- Save, mark interesting, dismiss, and reverse each action. The flags can coexist and persist across sessions.
- Show All, Saved, Interesting, and Dismissed views. All excludes dismissed items by default.
- Show summary cards for found signals, new since last visit, and grouped duplicate hits.

## Boundaries

There is no trends page, cross-source popularity score, content drafting, or export. The numeric engagement filter uses the displayed primary source metric; unlike metrics from different sources are not presented as comparable.

## Acceptance criteria

1. Canonical URL matches and conservative same-target title matches group correctly; uncertain items remain separate.
2. Detail preserves provenance from all contributing source items and links to an original URL.
3. Source, topic, date, engagement, and state filters compose correctly with pagination and newest-first order.
4. Triage flags persist independently; dismissed items can be restored.
5. Malicious source text is rendered as text, and external links open safely.
