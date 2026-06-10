---
name: engram
description: |
  Use Engram MCP tools to save and semantically retrieve thoughts from the user's
  local knowledge base. Trigger on: "remember this", "save this", "note that",
  "add to my brain", "what do I know about X", "search my notes", "find my thoughts
  on Y", "do I have anything about Z", "show recent thoughts", "what did I save".
  Always search Engram before answering from memory when the user references their
  own notes, ideas, or previously saved content.
license: MIT
metadata:
  version: v1
  publisher: engram
---

# Engram — Local Knowledge Base

You have access to an **Engram MCP server** that stores and semantically searches
the user's personal knowledge base. Everything runs locally — no cloud, no API costs.

## When to Use Engram

| Trigger phrase | Action |
|---|---|
| "remember this", "save this", "note that", "add to my brain" | `save_thought` |
| "what do I know about X", "find my thoughts on Y", "do I have anything about Z" | `search_engram` |
| "search my notes", "look in my brain", "check my knowledge base" | `search_engram` |
| "show recent thoughts", "what did I save lately", "my last N entries" | `list_recent_thoughts` |
| "delete thought ID N", "remove that thought" | `delete_thought` |
| "how many thoughts", "brain stats", "knowledge base stats" | `engram_stats` |

**Proactive rule**: if the user asks a question and references their own notes/ideas/memory,
always call `search_engram` first before answering from your own training data.

---

## Tools Reference

### `search_engram`

Semantic similarity search — finds thoughts by meaning, not keywords.

```json
{
  "query": "ideas about developer productivity",
  "limit": 10,
  "threshold": 0.3
}
```

- `query` *(required)* — natural language description of what you're looking for.
  Longer, descriptive queries work better than single keywords.
- `limit` — max results (1–50, default 10)
- `threshold` — minimum similarity score (0.0–1.0, default 0.3). Lower = more
  results but less relevant. Raise to 0.6+ when you want only high-confidence matches.

**Examples:**
- User: "what have I thought about AI pricing?" → `{"query": "AI pricing cost models"}`
- User: "find my notes on React" → `{"query": "React frontend development"}`
- User: "do I have anything about my sleep?" → `{"query": "sleep health habits"}`

---

### `save_thought`

Embeds and stores a thought locally. Called when the user wants to capture something.

```json
{
  "content": "The key insight from today's standup: ship small, get feedback fast.",
  "tags": "process,agile"
}
```

- `content` *(required)* — the full text to save. Be specific — more detail = better search recall.
- `tags` — optional comma-separated tags for filtering (e.g. `ai,productivity,ideas`)

**Examples:**
- User: "remember: GraphQL subscriptions cause memory leaks if you forget to unsubscribe"
  → save with tag `graphql,bugs`
- User: "note that the Postgres EXPLAIN ANALYZE output showed a seq scan on the users table"
  → save with tag `postgres,performance`

---

### `list_recent_thoughts`

Browses entries in reverse chronological order. Use when the user wants to review
what they've saved without a specific query.

```json
{
  "limit": 20,
  "offset": 0
}
```

- `limit` — entries to return (1–100, default 20)
- `offset` — pagination offset (default 0)

---

### `delete_thought`

Permanently removes a thought by its numeric ID (shown in search/list results).

```json
{ "id": 42 }
```

Always confirm the ID with the user before deleting — deletion is permanent.

---

### `engram_stats`

Returns total count, date range, and unique tag count. No parameters needed.

```json
{}
```

---

## Behavior Guidelines

1. **Search before answering** — when the user says "what did I think about X" or
   "what do I know about Y", call `search_engram` first. Do not answer from training
   data alone.

2. **Save verbatim when instructed** — when the user says "remember this: [content]",
   save their exact words. Don't paraphrase unless they ask you to.

3. **Confirm saves** — after `save_thought` succeeds, echo the content back briefly
   so the user knows what was stored and at what ID.

4. **Lower threshold when results are sparse** — if `search_engram` returns 0 results,
   retry with threshold 0.1 before telling the user nothing was found.

5. **Suggest saving mid-conversation** — if the user shares a decision, insight, or
   fact that seems worth keeping, proactively offer: "Want me to save this to Engram?"
