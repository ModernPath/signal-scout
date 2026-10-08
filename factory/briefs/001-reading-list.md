# 001 Reading list agent
Agent: reading-list
Role: Saves articles to a local reading list, tags and ranks them by interest
Purpose: A single local operator keeps a reading list of article links with a short note and tags, and asks which items to read next.
Inputs: Article title, URL, optional note and tags, typed in chat or passed to a tool CLI.
Outputs: The stored list, a "read next" ranking with the reason for each rank, and a summary count by tag.
Permissions: Reads and writes only its own data directory. Never fetches a URL, never calls the network except the optional model provider for chat.
Side effects: None outside its data directory.
Offline behavior: Chat commands (add, list, tag, rank, summarize) and every tool CLI work with no provider key. Ranking is deterministic: oldest unread first, boosted by the operator's most used tags.
Memory: One JSON record per item (id, title, url, note, tags, added_at, read_at) in the agent data directory. Kept until the operator deletes the item; deleting clears it from the file.
Surfaces: cli, tools, api
Subagents: none
Out of scope: Fetching or summarizing page content, accounts, sharing, authentication, a UI, publishing.
Verification: bash factory/check.sh reading-list
