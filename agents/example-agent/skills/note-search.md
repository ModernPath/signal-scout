---
name: note-search
description: Find notes by keyword or tag, or list the most recent ones
tools: [search_notes]
---

## Purpose
Answer questions about what the user has saved, using stored notes only.

## When to Use
- The user asks "what did I note about…", "find…", or "show my notes"
- You need a note id before deleting it

## Tools Required
- `search_notes.py [--query KEYWORDS] [--tag TAG] [--limit N]` — ranked by relevance
  (title > tag > body), newest first on ties; no arguments lists recent notes

## Example
```bash
python tools/search_notes.py --query "bob offer"
python tools/search_notes.py --tag work --limit 5
```
