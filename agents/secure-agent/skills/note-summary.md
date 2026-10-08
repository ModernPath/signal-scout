---
name: note-summary
description: Summarize all notes or one tag by delegating to the note_summarizer subagent
tools: [summarize_notes]
---

## Purpose
Give the user a short overview of their notes: themes and open action items.

## When to Use
- The user asks for a summary, overview, recap, or "what's on my plate"

## Tools Required
- `summarize_notes(tag)` — runs `subagents/note_summarizer.py` as a separate process for this
  user's notes only. The subagent has no tools, so it can only return text.
