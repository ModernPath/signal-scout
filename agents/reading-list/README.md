# Reading List agent

A local reading list: save links with a title, note and tags, mark them read, and get a deterministic "read next" ranking.

## Contract

- **Purpose:** keep a personal list of http(s) links and suggest what to read next.
- **Inputs:** title (required), http(s) URL (required), note (max 500 chars), tags (normalized to lowercase slugs, deduplicated, order preserved), item ids for tag/read/delete.
- **Outputs:** item records `{id, title, url, note, tags, added_at, read_at}`; ranking entries add `rank`, `tag_boost`, `reason`; summary `{total, unread, read, tags}`.
- **Ranking:** unread items only, ordered by tag boost (sum over the item's tags of each tag's usage count across the whole list), ties by oldest `added_at`, then id. `reason` names the contributing tags with counts and the added date. No model is involved.
- **Permissions / side effects:** reads and writes only `items.json` in the data directory. No page fetching, no network calls except the optional Gemini chat.
- **Offline behavior:** with `READING_LIST_OFFLINE=1` or no provider key, every surface works with no network. Provider failures fall back to the offline router.
- **Memory retention:** items live in `memory/data/items.json` (or `READING_LIST_DATA_DIR`) until deleted; no expiry or other removal. Live data is git-ignored.
- **Surfaces:** chat CLI, tool CLIs (JSON envelope), REST API on `127.0.0.1:8013`. No UI. The API has no authentication.

## Surfaces

Chat commands (offline router): `add Title https://… note: why #tag`, `list [unread]`, `tag <id> a, b`, `rank`, `read <id>`, `delete <id>`, `summarize`. Anything else prints help.

Tools (each prints one `{"status": "success", "data": …}` object and exits 0, or `{"status": "error", "error": …}` and exits 1): `tools/add_item.py`, `list_items.py`, `tag_item.py`, `rank_items.py`, `mark_read_item.py`, `delete_item.py`, `summarize_items.py`; `memory/memory.py` inspects the store.

API: `GET /health`, `GET/POST /items`, `GET/DELETE /items/{id}`, `POST /items/{id}/tags`, `POST /items/{id}/read`, `GET /rank`, `GET /summary`, `POST /chat`. `ValueError` → 400, not found → 404.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # keep the venv out of version control
pip install -r requirements.txt
```

## Environment variables

Loaded only from this folder's `.env` / `.env.local`, never from parent directories. See `.env.example`.

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Optional; enables LLM chat |
| `READING_LIST_OFFLINE` | `1` forces offline mode |
| `READING_LIST_MODEL` | Optional model override |
| `READING_LIST_DATA_DIR` | Data directory (default `memory/data`) |
| `API_PORT` | API port (default 8013) |

## Run and test

```bash
python reading_list.py --offline "add Great read https://example.com #dev"
python reading_list.py --chat
python api/main.py            # http://127.0.0.1:8013/docs
python -m pytest              # offline, uses a temporary data directory
```

## Safe copy

Copy the folder without `.env*`, `.venv`, `__pycache__`, and `memory/data/*.json` so no live data or credentials travel with it.
