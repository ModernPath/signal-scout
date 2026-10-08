# Decisions

## 2026-10-08 — Operating policy for the agent factory

**The factory may do unattended:** turn a brief in `factory/briefs/` into feature
specs, a scaffold copied from `agents/example-agent/`, failing tests, an
implementation and a review on its own branch `factory/<run id>`, add a
"Factory draft" row to `agents/AGENTS.md`, and write `pr.md` or open a **draft**
pull request. It stops by itself on any failed gate, on running out of turns,
time (1800 s per stage) or budget ($15 per run), and when the reviewer still asks for
changes after `FACTORY_REVIEW_ROUNDS` fix rounds (default 2).

**Always needs a person:**

- merging a factory branch or marking its PR ready for review;
- the real-browser check of any UI and chat that `agents/AGENTS.md` requires before acceptance;
- running the agent against a real provider key, and anything involving secrets, credentials, CI or dependencies;
- changing gates, prompts or anything else under `factory/`;
- changing `agents/example-agent/`, the application in `src/`, or migrations;
- an agent that needs a database, network access beyond loopback, authentication or publishing: those are designed by hand, not generated;
- deciding what a stop report asks.

**Why:** the gates check what a machine can check: that tests failed first, that
the offline suite passes, that only allowed files changed, that the copy is not
wired to the example's names or the repository's credentials, and that a
read-only reviewer approved. Whether the agent is worth having and behaves well
is a human decision.

**Revisit when:** the factory has produced five real agents. Count accepted PRs,
stops by gate, review time and cost per accepted PR.
