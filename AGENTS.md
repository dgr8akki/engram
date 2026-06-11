# Engram — Agent Reference

Engram is a local semantic knowledge base. It stores and retrieves personal notes,
decisions, and session history using vector embeddings — all on-device, no cloud.

## Project Structure

```
engram/
├── engram_db.py            # SQLite + sqlite-vec storage layer
├── engram_embeddings.py    # sentence-transformers / Ollama embedding backends
├── engram_mcp_server.py    # MCP server (stdio transport)
├── engram_http_server.py   # HTTP REST fallback server
├── engram_cli.py           # CLI entry point (click)
├── engram_install.py       # Multi-tool installer (MCP + skill + hooks)
├── engram                  # Shell wrapper: ./engram <command>
├── config.yaml             # Runtime configuration
├── skill/
│   └── SKILL.md            # Agent skill — loaded by Claude Code, Antigravity, etc.
└── scripts/
    ├── engram_session_start.py   # Hook: inject memories at session start
    ├── engram_user_prompt.py     # Hook: auto-save on "remember: ..."
    ├── engram_session_end.py     # Hook: save session topic at end
    └── engram_windsurf_update.py # Windsurf-specific: write to .windsurfrules
```

## MCP Tools

| Tool | Description |
|---|---|
| `search_engram` | Semantic similarity search — finds thoughts by meaning |
| `save_thought` | Embed and store a new thought |
| `list_recent_thoughts` | Browse entries in reverse chronological order |
| `delete_thought` | Remove a thought by ID |
| `engram_stats` | Total count, date range, tag diversity |

### Tool Details

**`search_engram`**
```json
{ "query": "ideas about developer productivity", "limit": 10, "threshold": 0.3 }
```
- Always call this before answering questions about the user's own notes or memory.
- If results are empty, retry with `"threshold": 0.1`.

**`save_thought`**
```json
{ "content": "The thought text", "tags": "optional,comma,tags" }
```
- Save verbatim when the user says "remember this".
- Confirm back: echo the content and ID after saving.

**`list_recent_thoughts`**
```json
{ "limit": 20, "offset": 0 }
```

**`delete_thought`**
```json
{ "id": 42 }
```
Always confirm the ID before deleting.

**`engram_stats`** — no parameters.

## Memory Hook System

Three hook scripts run automatically at session boundaries:

| Script | Event | What it does |
|---|---|---|
| `engram_session_start.py` | Session start | Reads last 15 thoughts → injects as `additionalContext` |
| `engram_user_prompt.py` | Before each user message | Detects "remember: …" / "note: …" patterns → auto-saves |
| `engram_session_end.py` | Session end | Parses transcript → saves first user message as session record |
| `engram_windsurf_update.py` | Windsurf only | Writes memories to `.windsurfrules` (Windsurf can't inject context directly) |

Auto-save trigger phrases (case-insensitive):
- `remember: <content>`
- `note: <content>` / `note that: <content>`
- `save: <content>` / `save this: <content>`
- `add to my brain: <content>`
- `engram: <content>`

## Setup Commands

```bash
./engram init             # initialise the database
./engram install          # register MCP + install skill + install hooks (all tools)
./engram skill install    # skill only
./engram hooks install    # hooks only
./engram serve            # start HTTP server (port 7823)
```

## Configuration (`config.yaml`)

```yaml
database:
  path: "data/engram.db"

embeddings:
  backend: "sentence-transformers"   # or "ollama"
  model: "sentence-transformers/all-MiniLM-L6-v2"
  dimensions: 384
  device: "cpu"
  ollama_url: "http://localhost:11434"
  ollama_model: "nomic-embed-text"
  ollama_dimensions: 768

search:
  default_limit: 10
  similarity_threshold: 0.3

http:
  host: "127.0.0.1"
  port: 7823
```

## Behaviour Rules for Agents

1. **Search before answering** — when the user asks "what do I know about X" or "find my notes on Y", call `search_engram` first.
2. **Save verbatim** — when the user says "remember this", save their exact words.
3. **Confirm saves** — echo back the content and ID after `save_thought`.
4. **Lower threshold on empty results** — retry with `threshold: 0.1` before reporting no results.
5. **Proactively offer to save** — if a user shares a decision or insight mid-conversation, offer: "Want me to save this to Engram?"

## Embedding Backends

- **sentence-transformers** (default): downloads `all-MiniLM-L6-v2` (~90MB) on first run, 384-dim
- **ollama**: uses a running Ollama instance (`nomic-embed-text` = 768-dim). Set `backend: ollama` in `config.yaml`.

Changing backends requires reinitialising the database (`engram init`) because the vector dimension changes.
