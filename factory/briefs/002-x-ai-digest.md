# 002 X AI posts daily digest agent
Agent: x-ai-digest
Role: Builds a daily digest of the most popular AI posts on X from imported post data
Purpose: A single local operator wants each day's most popular AI-related posts from X, ranked and summarized, and can ask about them in chat.
Inputs: Post records (post id, author handle, text, URL, posted_at, like/repost/reply/view counts) imported from a JSON file through a tool CLI or chat command. A pluggable source interface (`x_ai_digest_sources.py`) lets the operator wire in an X API fetcher later; the shipped sources are the JSON file importer and a deterministic fixture source for tests.
Outputs: A daily digest for a given date (default today): top N posts ranked by a documented engagement score, each with author, URL, counts and a one-line reason for its rank; a list of days with digests; a digest rendered as Markdown.
Permissions: Reads and writes only its own data directory and the JSON file the operator names. Makes no network call to X. The only network use is the optional model provider for chat summaries. Never posts, likes, follows or messages on X.
Side effects: None outside its data directory.
Offline behavior: Import, dedupe, AI-topic filtering, ranking, digest generation and Markdown rendering are deterministic and work with no provider key. AI relevance uses a documented keyword/phrase list the operator can extend. Model summaries are optional and clearly marked as model-written; offline chat never invents posts or counts.
Memory: One JSON record per post (id, handle, text, url, posted_at, metrics, imported_at, matched_topics) and one record per generated digest (date, post ids, score version) in the agent data directory. Posts and digests older than 90 days are removed by an explicit `prune` command; the operator can delete any post.
Surfaces: cli, tools, api
Subagents: none
Out of scope: Calling the X API or scraping x.com, scheduling (the operator runs the digest command from cron or launchd), accounts or authentication, a UI, posting or engaging on X, sentiment analysis, sharing digests externally.
Verification: bash factory/check.sh x-ai-digest
