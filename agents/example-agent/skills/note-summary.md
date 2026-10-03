---
name: note-summary
description: Summarize all notes or one tag by delegating to the note_summarizer subagent
tools: [note_summarizer]
---

## Purpose
Give the user a short overview of their notes: themes and open action items.

## When to Use
- The user asks for a summary, overview, recap, or "what's on my plate"

## Tools Required
- `subagents/note_summarizer.py [--tag TAG] [--offline]` — runs as a separate process,
  uses Gemini when an API key is set, otherwise returns a deterministic summary

## Example
```bash
python subagents/note_summarizer.py --tag work
```
