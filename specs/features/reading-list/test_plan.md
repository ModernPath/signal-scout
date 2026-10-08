# Reading list agent — test plan

**Behavior:** [Task spec](task_spec.md)

All cases run offline against a throwaway `READING_LIST_DATA_DIR` with
provider keys removed from the environment — exactly what
`bash factory/check.sh reading-list` does. No test starts the web server,
calls a real provider, or performs a network request; the API is exercised
with FastAPI's `TestClient` against an injected store.

| Case | Scenario | Expected result |
|---|---|---|
| R-01 | Add items through core/service with a valid title/URL/note/tags; then an empty title, a non-http(s) URL, a note over 500 chars, and messy tags `" Dev ,DEV, #dev"` | Valid add stores a record with `item_*` id, stripped title, `read_at` null, `added_at` set, tags `["dev"]`; each invalid add raises `ValueError` and stores nothing |
| R-02 | `read_next` over a fixed set with controlled `added_at`: mixed read/unread items, tag usage concentrated on one tag, two unread items with equal boost but different `added_at`, and more unread items than the limit | Read items are excluded; order is boost desc, then oldest `added_at`, then id; each entry has `rank`, `tag_boost`, and a deterministic `reason` naming the contributing tags (or "no tag boost"); `limit` truncates the ordering, not the score |
| R-03 | `summarize` over the same fixed set | `total`, `unread`, `read` counts and per-tag counts over the whole list agree with the stored items |
| R-04 | Add, mark read, and delete items through two store instances sharing one temp data dir | `items.json` contains only schema fields and only surviving records; the second instance sees all writes; delete removes the record from the file; nothing is written outside the data dir |
| R-05 | `tag_item` adding a duplicate in another case and a new tag; with an unknown id; with a tag list that normalizes to nothing | Merge deduplicates case-insensitively and keeps existing order; unknown id raises `NotFoundError`; no valid tag raises `ValueError` and leaves the item unchanged |
| R-06 | `mark_read_item` on one item, then the same item again | First call sets `read_at`; the second keeps the original value (idempotent); the item no longer appears in `rank_items` |
| R-07 | Offline chat (no key, `READING_LIST_OFFLINE=1`): run `add`, `list`, `list unread`, `tag`, `rank`, `summarize`, `read`, `delete` in sequence; then an unrecognized command | Each reply reflects the stored state (ids, tags, ranks, counts) and matches the service result for the same input; the unrecognized command returns help text listing the supported commands with no traceback |
| R-08 | Run every tool CLI in a subprocess (inherited offline env and temp data dir): valid arguments, bad input, and an unknown id | Each run prints exactly one parseable JSON object on stdout; success is `{"status": "success", …}` with exit 0; failures are `{"status": "error", "error": …}` with exit 1 |
| R-09 | API via `TestClient` with an injected store on a temp dir: create, list (filters), get, tag, read, rank, summary, delete; a malformed body; a request for an unknown id | Every route agrees with the service state the tools and chat see; `ValueError` maps to 400 and unknown ids to 404; `/health` returns ok |
| R-10 | Set a fake provider key plus `READING_LIST_OFFLINE=1`; point `READING_LIST_DATA_DIR` at a fresh dir; check `agent_env` behavior | Chat reports offline mode (`used_llm` False) and routes commands; all reads/writes land in the overridden dir; environment loading reads no `.env` file from a parent directory |

**Named tests** (created by the test stage; see `factory/runs/001-reading-list/spec.md`):
one per distinct behavior — core validation/ranking/summary (R-01…R-03),
persistence and item updates (R-04…R-06), offline chat (R-07), tool CLI
envelopes (R-08), and API mapping (R-09).

**Exit criteria:** `bash factory/check.sh reading-list` passes with provider
keys unset; every named test in the run spec passes; no secret, key, or live
record appears in committed files; the offline path needs no network.