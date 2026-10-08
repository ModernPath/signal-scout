# Reading list

Manage saved links with the tools; never invent ids, URLs or ranking results.

- `add_item` needs a title and an http(s) URL; the note is at most 500 characters; tags are optional.
- `list_items` shows newest first; use `unread` or `tag` to filter.
- `rank_items` returns unread items by tag boost (sum of each tag's usage count across the list), ties by oldest added date. Report each entry's `reason` as returned.
- `tag_item` merges tags; `mark_read_item` is idempotent; `delete_item` is permanent, so confirm the exact id first.
- `summarize_items` gives total, unread, read and per-tag counts.
