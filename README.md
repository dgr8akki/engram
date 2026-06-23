# Engram

A local-first personal knowledge base with semantic search, built to work natively with Claude Code, Cursor, Antigravity, and Windsurf via MCP.

Everything runs on your machine — no cloud, no API costs, no data leaving your computer.

## Features

- **Auto-retrieval** — every prompt is silently searched against your knowledge base; relevant memories are injected as context before the LLM responds
- **Auto-save triggers** — say "remember: ..." mid-conversation and your note is saved instantly
- **Proactive capture** — Claude saves architectural decisions, bug root causes, and codebase gotchas without being asked
- **Semantic search** — find thoughts by meaning, not keywords
- **MCP integration** — Claude Code, Cursor, and Antigravity can read and write your knowledge base mid-conversation
- **HTTP REST server** — always-on background server keeps the embedding model warm for fast retrieval
- **Dual embedding backends** — sentence-transformers (offline, ~90MB) or Ollama

## Quick Start

### macOS — Homebrew (recommended)

```bash
brew tap dgr8akki/tap
brew install engram
engram init
engram install
engram autostart install
```

### Any platform — git clone

```bash
git clone https://github.com/dgr8akki/engram
cd engram
bash setup.sh
./engram autostart install
```

`setup.sh` handles Python, venv, dependencies, `engram init`, and `engram install` in one shot.

**Then restart your IDE.** Engram is active from the next session.

> `engram autostart install` registers a macOS LaunchAgent so the HTTP server starts at login and stays running. This is required for auto-retrieval to work on every prompt — without it the server only starts inside a Claude session and the first prompt of a fresh login won't have retrieval.

---

`engram install` does three things:
1. Registers the MCP server for each detected AI tool
2. Installs the agent skill (tells the LLM how to use Engram)
3. Installs session-lifecycle hooks (auto retrieve, auto save, auto summarise)

## How It Works

Once installed, Engram runs silently in the background on every conversation:

| When | What Engram does |
|---|---|
| Session starts | Last 15 memories injected into context |
| Every prompt | Searches your knowledge base; injects semantically matching memories above 0.40 similarity |
| You say "remember: …" | Content saved before the LLM even sees the message |
| Session ends | Up to 5 of your messages are collected and saved as a session record |
| Claude finds a key insight | Saves architectural decisions, bug root causes, and gotchas proactively |

You don't have to do anything — relevant context surfaces automatically.

## CLI Usage

```bash
engram add "GraphQL subscriptions leak memory if you forget to unsubscribe"
engram add "Prefer useReducer over useState for complex form state" --tags react,patterns
engram search "memory leak javascript"
engram list --limit 20
engram delete 42
engram stats
engram -h          # help
engram -V          # version
```

(Replace `engram` with `./engram` if using the git-clone install without an alias.)

## AI Tool Usage

Once installed, your AI coding tool uses Engram automatically. You can also drive it explicitly:

| You say | What happens |
|---|---|
| "remember: prefer Zod over Yup for schema validation" | Auto-saved immediately, before LLM responds |
| "what do I know about React patterns?" | Searches your knowledge base |
| "show my recent thoughts" | Lists last 20 entries |
| "save this: always check for null before accessing .data" | Saved to Engram |

## Multi-Tool Setup

`engram install` auto-detects and configures:

| Tool | MCP Config | Skill | Hooks |
|---|---|---|---|
| Claude Code | `~/.claude/settings.json` via `claude mcp add` | `~/.claude/skills/engram` | `SessionStart`, `UserPromptSubmit`, `Stop` |
| Antigravity CLI | `~/.gemini/config/mcp_config.json` | `~/.gemini/antigravity/skills/engram` | `SessionStart`, `BeforeAgent`, `SessionEnd` |
| Cursor | `~/.cursor/mcp.json` | `~/.cursor/skills/engram` | `sessionStart`, `beforeSubmitPrompt`, `sessionEnd` |
| Windsurf | `~/.codeium/windsurf/mcp.json` | `~/.windsurf/skills/engram` | `pre_user_prompt`, `post_cascade_response_with_transcript` |

## HTTP Server

The HTTP server is what makes auto-retrieval fast — the embedding model stays loaded in memory so each prompt search is just a quick HTTP call rather than a cold model load.

```bash
engram serve                   # start manually on http://127.0.0.1:7823
engram autostart install       # start automatically at login (macOS LaunchAgent)
engram autostart remove        # disable autostart
engram autostart status        # check if running
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

Switch to Ollama if you already have it running — no model download needed and better quality embeddings (768-dim vs 384-dim).

## Upgrading

```bash
brew upgrade engram
engram autostart install && engram rules install
```

The second line reloads the background LaunchAgents — Homebrew unloads them during the old version teardown and can't reload them from the install process context. You only need to run this once after each upgrade.

Your knowledge base at `~/.engram/engram.db` is never touched by upgrades.

## Troubleshooting

**sqlite-vec install fails** — use system Python or Homebrew Python instead of pyenv:
```bash
brew install python
/opt/homebrew/bin/python3 -m venv venv
```

**MCP server not appearing** — run `claude mcp list` (Claude Code) or check your tool's MCP config. Make sure paths are absolute. Restart the IDE.

**Hooks not firing** — confirm with `engram install -v` that hooks were written. For Claude Code, check `~/.claude/settings.json` for a `hooks` block.

**Auto-retrieval not working** — check the HTTP server is running: `curl http://127.0.0.1:7823/health`. If it isn't, run `engram autostart install` and log out and back in, or start it manually with `engram serve`.

**Empty search results** — lower the threshold: `engram search "query" --threshold 0.1`
