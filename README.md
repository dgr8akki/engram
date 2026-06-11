# Engram

A local-first personal knowledge base with semantic search, built to work natively with Claude Code, Cursor, Antigravity, and Windsurf via MCP.

Everything runs on your machine — no cloud, no API costs, no data leaving your computer.

## Features

- **Semantic search** — find thoughts by meaning, not keywords
- **MCP integration** — Claude Code, Cursor, and Antigravity can read and write your knowledge base mid-conversation
- **Auto-memory hooks** — sessions automatically inject recent memories on start and save notes on end
- **Auto-save triggers** — say "remember: ..." and your note is saved instantly
- **HTTP REST server** — fallback for tools that don't support MCP
- **Dual embedding backends** — sentence-transformers (offline) or Ollama

## Quick Start

```bash
git clone https://github.com/dgr8akki/engram
cd engram
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
./engram init
./engram install
```

`engram install` does three things in one shot:
1. Registers the MCP server for each detected tool
2. Installs the agent skill (tells LLMs how to use Engram)
3. Installs session-lifecycle hooks (auto memory read/write)

Then restart your IDE and Engram is active.

## CLI Usage

```bash
./engram add "GraphQL subscriptions leak memory if you forget to unsubscribe"
./engram add "Prefer useReducer over useState for complex form state" --tags react,patterns
./engram search "memory leak javascript"
./engram list --limit 20
./engram delete 42
./engram stats
./engram -h          # help
./engram -V          # version
```

## AI Tool Usage

Once installed, your AI coding tool can use Engram through natural conversation:

| You say | What happens |
|---|---|
| "remember: prefer Zod over Yup for schema validation" | Auto-saved immediately |
| "what do I know about React patterns?" | Searches your knowledge base |
| "show my recent thoughts" | Lists last 20 entries |
| "save this: always check for null before accessing .data" | Saved to Engram |

## Session Memory Hooks

Hooks run automatically at session boundaries — no configuration needed after `engram install`.

| When | What happens |
|---|---|
| Session starts | Last 15 memories injected into context |
| You say "remember: ..." | Content saved to Engram before LLM processes the message |
| Session ends | First user message saved as a session record |

## Multi-Tool Setup

`engram install` auto-detects and configures:

| Tool | MCP Config | Skill | Hooks |
|---|---|---|---|
| Claude Code | `~/.claude/settings.json` via `claude mcp add` | `~/.claude/skills/engram` | `SessionStart`, `UserPromptSubmit`, `Stop` |
| Antigravity CLI | `~/.gemini/config/mcp_config.json` | `~/.gemini/antigravity/skills/engram` | `SessionStart`, `BeforeAgent`, `SessionEnd` |
| Cursor | `~/.cursor/mcp.json` | `~/.cursor/skills/engram` | `sessionStart`, `beforeSubmitPrompt`, `sessionEnd` |
| Windsurf | `~/.codeium/windsurf/mcp.json` | `~/.windsurf/skills/engram` | `pre_user_prompt`, `post_cascade_response_with_transcript` |

## HTTP Server

For tools without MCP support:

```bash
./engram serve                   # start on http://127.0.0.1:7823
./engram autostart install       # start automatically at login (macOS LaunchAgent)
./engram autostart remove        # disable autostart
./engram autostart status        # check if running
```

| Endpoint | Description |
|---|---|
| `GET /thoughts?limit=20` | List recent thoughts |
| `GET /thoughts/search?q=...` | Semantic search |
| `POST /thoughts` | Save a thought `{"content": "...", "tags": "..."}` |
| `GET /thoughts/{id}` | Get by ID |
| `DELETE /thoughts/{id}` | Delete by ID |
| `GET /stats` | Statistics |

## Configuration

Edit `config.yaml` to customise behaviour:

```yaml
embeddings:
  backend: "sentence-transformers"   # or "ollama"
  model: "sentence-transformers/all-MiniLM-L6-v2"
  dimensions: 384
  device: "cpu"                      # or "cuda"

  # Ollama (when backend: "ollama")
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

Switch to Ollama if you already have it running — no model download needed and better quality embeddings.

## Troubleshooting

**sqlite-vec install fails** — use system Python or Homebrew Python instead of pyenv:
```bash
brew install python
/opt/homebrew/bin/python3 -m venv venv
```

**MCP server not appearing** — run `claude mcp list` (Claude Code) or check your tool's MCP config. Make sure paths are absolute. Restart the IDE.

**Hooks not firing** — confirm with `engram install -v` that hooks were written. For Claude Code, check `~/.claude/settings.json` for a `hooks` block.

**Empty search results** — lower the threshold: `engram search "query" --threshold 0.1`
