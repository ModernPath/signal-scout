---
name: note-taking
description: Save or delete a note when the user wants to remember or forget something
tools: [add_note, delete_note]
---

## Purpose
Capture information the user wants to keep, and remove notes they no longer need.

## When to Use
- The user says "remember", "note", "save", or "add" followed by content
- The user asks to delete or remove a note

## Tools Required
- `add_note.py --title TEXT [--body TEXT] [--tags "a, b"]` — creates a note, returns it with its id
- `delete_note.py --id NOTE_ID` — deletes by exact id; search first if you only know the title

## Example
```bash
python tools/add_note.py --title "Call Bob" --body "About the renewal offer" --tags "work, sales"
python tools/delete_note.py --id note_ab12cd34ef
```
