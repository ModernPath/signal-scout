# Agent memory

All agent memory lives in the SignalScout PostgreSQL database. The application
owns migrations `0005_intelligence` and `0006_agent_memory`. `memory.py` is the persistence
adapter. It reads Phase 1 signals and source items and writes only Phase 2 tables.

The active company brief and content library feed new analyses. Replacing a
content item creates a new row and deactivates the old one; deleting an item
scrubs private text throughout its replacement lineage. Deleting the brief
scrubs all its versions. Analysis runs retain their source IDs and input hash.
Chat sessions expire 90 days after their last turn. A cleanup command deletes
expired chat sessions and redacts expired research excerpts while retaining
source URL and retrieval time for audit. Drafts remain until an operator
deletion workflow is added; never store provider request/response payloads.
