#!/usr/bin/env python3
"""UserPromptSubmit / BeforeAgent hook: auto-retrieves relevant memories and auto-saves
when the user says 'remember this' etc.

On every prompt:
  1. Hits the running HTTP server to search for memories relevant to the prompt text.
     The server keeps the embedding model warm, so this is just a fast HTTP call.
  2. Injects matching memories as additionalContext so Claude sees them before responding.

On save-trigger phrases (remember: / note: / save: / …):
  3. Embeds and stores the content directly (DB write, no server round-trip needed).

Compatible with: Claude Code (UserPromptSubmit), Antigravity CLI (BeforeAgent),
Cursor (beforeSubmitPrompt).
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ENGRAM_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ENGRAM_DIR))

# Patterns that trigger an auto-save. Capture group 1 = content to save.
# All anchored to the start of the message so mentioning these words mid-sentence
# (e.g. "do you know about engram command") never misfires as a save.
PATTERNS = [
    r"^remember[:\s]+(.+)",
    r"^note[:\s]+(.+)",
    r"^save[:\s]+(.+)",
    r"^remember this[:\s]+(.+)",
    r"^remember this$",              # "remember this" alone → save the previous context
    r"^note (?:that|this)[:\s]+(.+)",
    r"^save this[:\s]+(.+)",
    r"^add to (?:my )?(?:brain|engram|notes|knowledge)[:\s]+(.+)",
    r"^engram[:\s]+(.+)",            # "engram: ..." direct capture
]

CONTINUE = json.dumps({"continue": True})

# Search config
SEARCH_LIMIT = 5
SEARCH_THRESHOLD = 0.40   # only inject memories that are clearly relevant
QUERY_MAX_CHARS = 300     # truncate very long prompts for the search query


def extract_save_content(prompt: str):
    """Return (content, tags) to save, or (None, None) if no trigger found."""
    text = prompt.strip()
    for pattern in PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                content = m.group(1).strip()
            except IndexError:
                content = text  # pattern had no capture group
            if content:
                return content, None
    return None, None


def _http_base(config: dict) -> str:
    host = config.get("http", {}).get("host", "127.0.0.1")
    port = config.get("http", {}).get("port", 7823)
    return f"http://{host}:{port}"


def _search_via_http(prompt: str, config: dict) -> list:
    """Search engram via the running HTTP server. Returns [] if server is down."""
    query = urllib.parse.quote(prompt[:QUERY_MAX_CHARS])
    url = (
        f"{_http_base(config)}/thoughts/search"
        f"?q={query}&limit={SEARCH_LIMIT}&threshold={SEARCH_THRESHOLD}"
    )
    try:
        with urllib.request.urlopen(url, timeout=1) as r:
            results = json.loads(r.read()).get("results", [])
    except Exception:
        return []
    # Session summaries are broad/self-similar and drown out deliberate notes —
    # keep them searchable on demand, just not auto-injected on every prompt.
    return [r for r in results if "session" not in (r.get("tags") or "").split(",")]


def _save_via_http(content: str, tags: str | None, config: dict) -> int | None:
    """Save a thought via the HTTP server. Returns thought ID, or None if server is down."""
    url = f"{_http_base(config)}/thoughts"
    body = json.dumps({"content": content, "tags": tags}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return json.loads(r.read()).get("id")
    except Exception:
        return None


def _format_memory_block(results: list) -> str:
    lines = ["**Engram — relevant memories:**", ""]
    for r in results:
        content = r.get("content", "")
        score = r.get("similarity", 0)
        lines.append(f"- {content}  _(match: {score:.2f})_")
    lines += ["", "Use these to inform your response where relevant."]
    return "\n".join(lines)


def main():
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except Exception:
        hook_input = {}

    # Different tools expose the prompt under different keys
    prompt = (
        hook_input.get("prompt")
        or hook_input.get("user_prompt")
        or hook_input.get("message")
        or ""
    )

    try:
        import yaml
        with open(ENGRAM_DIR / "config.yaml") as f:
            config = yaml.safe_load(f)
    except Exception:
        print(CONTINUE)
        return

    context_parts = []

    # --- Auto-retrieve: search for relevant memories on every prompt ---
    if prompt.strip():
        results = _search_via_http(prompt, config)
        if results:
            context_parts.append(_format_memory_block(results))

    # --- Auto-save: check for explicit save triggers ---
    save_content, tags = extract_save_content(prompt)
    if save_content:
        thought_id = _save_via_http(save_content, tags, config)

        if thought_id is None:
            # HTTP server not available — fall back to direct DB write
            try:
                raw = config["database"]["path"]
                p = Path(raw).expanduser()
                db_path = p if p.is_absolute() else ENGRAM_DIR / raw

                from engram_db import EngramDatabase
                from engram_embeddings import EmbeddingGenerator

                backend = config["embeddings"].get("backend", "sentence-transformers")
                dim_key = "ollama_dimensions" if backend == "ollama" else "dimensions"
                dim = config["embeddings"].get(dim_key, 384)

                db = EngramDatabase(str(db_path), embedding_dim=dim)
                db.init_database()
                embedder = EmbeddingGenerator(config["embeddings"])
                embedding = embedder.generate_embedding(save_content)
                thought_id = db.insert_thought(save_content, embedding, tags=tags)
                db.close()
            except Exception as e:
                print(json.dumps({"_engram_error": str(e)}), file=sys.stderr)

        if thought_id is not None:
            snippet = save_content[:80] + ("…" if len(save_content) > 80 else "")
            context_parts.append(f"[Engram] Saved (ID: {thought_id}): \"{snippet}\"")

    if not context_parts:
        print(CONTINUE)
        return

    ctx = "\n\n".join(context_parts)
    print(json.dumps({
        "continue": True,
        "additionalContext": ctx,
        "hookSpecificOutput": {
            "hookEventName": hook_input.get("hook_event_name", "UserPromptSubmit"),
            "additionalContext": ctx,
        },
        "additional_context": ctx,
    }))


if __name__ == "__main__":
    main()
