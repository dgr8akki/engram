#!/usr/bin/env python3
"""Session-end hook: saves a meaningful session record to Engram.

Collects all substantive user messages from the transcript, picks the most
representative ones, and builds a summary that captures what the session was
actually about — not just the opening line.

Compatible with: Claude Code (Stop / SessionEnd), Antigravity CLI (SessionEnd /
AfterAgent), Cursor (sessionEnd / stop).
"""

import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ENGRAM_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ENGRAM_DIR))

MIN_MSG_LEN = 20       # ignore very short/trivial messages
MAX_MSGS = 5           # collect up to this many user messages for the summary
MAX_MSG_CHARS = 200    # truncate each message to this length


import re as _re

# Prefixes that indicate injected/synthetic content, not real user input
_SKIP_PREFIXES = (
    "[Engram]", "**Engram", "Base directory for this skill:",
    "<command-message>", "<command-name>",
)


def _text_from_content(content) -> str:
    if isinstance(content, str):
        # Strip XML-style command/hook tags injected by Claude Code
        return _re.sub(r"<[^>]+>", " ", content).strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return _re.sub(r"<[^>]+>", " ", " ".join(parts)).strip()
    return ""


def _collect_user_messages(transcript_path: str) -> list[str]:
    """Return up to MAX_MSGS substantive user messages from the transcript.

    Claude Code transcript format: each line is a JSON object where
    type='user' entries hold the actual user prompt inside entry['message']['content'].
    """
    msgs = []
    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Claude Code wraps prompts as {type:'user', message:{role:'user', content:...}}
                # Older / other tools use {role:'user', content:...} directly
                if entry.get("type") == "user":
                    raw = entry.get("message", {}).get("content", "")
                elif entry.get("role") in ("user", "human"):
                    raw = entry.get("content", "")
                else:
                    continue

                text = _text_from_content(raw)
                if len(text) < MIN_MSG_LEN:
                    continue
                if any(text.startswith(p) for p in _SKIP_PREFIXES):
                    continue

                msgs.append(text[:MAX_MSG_CHARS])
                if len(msgs) >= MAX_MSGS:
                    break
    except Exception:
        pass
    return msgs


def _build_summary(msgs: list[str]) -> str | None:
    if not msgs:
        return None

    if len(msgs) == 1:
        return msgs[0]

    # Use first message as topic, append later ones as additional context
    # to give a richer picture of what was worked on
    parts = [msgs[0]]
    if len(msgs) > 1:
        extras = "; ".join(m[:80] for m in msgs[1:])
        parts.append(f"Also covered: {extras}")
    return " | ".join(parts)


def main():
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except Exception:
        hook_input = {}

    transcript_path = hook_input.get("transcript_path")
    if not transcript_path:
        sys.exit(0)

    msgs = _collect_user_messages(transcript_path)
    summary = _build_summary(msgs)
    if not summary:
        sys.exit(0)

    try:
        import yaml
        with open(ENGRAM_DIR / "config.yaml") as f:
            config = yaml.safe_load(f)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        content = f"[Session {ts}] {summary}"

        # Prefer HTTP server (keeps DB consistent with retrieval)
        host = config.get("http", {}).get("host", "127.0.0.1")
        port = config.get("http", {}).get("port", 7823)
        url = f"http://{host}:{port}/thoughts"
        body = json.dumps({"content": content, "tags": "session"}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=3)
            sys.exit(0)
        except Exception:
            pass  # Fall through to direct DB write

        # Fallback: direct DB write if HTTP server is down
        raw = config["database"]["path"]
        p = Path(raw).expanduser()
        db_path = p if p.is_absolute() else ENGRAM_DIR / raw
        if not db_path.exists():
            sys.exit(0)

        from engram_db import EngramDatabase
        from engram_embeddings import EmbeddingGenerator

        backend = config["embeddings"].get("backend", "sentence-transformers")
        dim_key = "ollama_dimensions" if backend == "ollama" else "dimensions"
        dim = config["embeddings"].get(dim_key, 384)

        db = EngramDatabase(str(db_path), embedding_dim=dim)
        db.init_database()
        embedder = EmbeddingGenerator(config["embeddings"])
        embedding = embedder.generate_embedding(content)
        db.insert_thought(content, embedding, tags="session")
        db.close()

    except Exception:
        pass  # Fire-and-forget — never fail loudly

    sys.exit(0)


if __name__ == "__main__":
    main()
