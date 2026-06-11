#!/usr/bin/env python3
"""Session-end hook: saves a brief session record to Engram.

Parses the transcript to extract the first meaningful user message as a session
topic. Fire-and-forget — failures are silent so they never interrupt the user.

Compatible with: Claude Code (Stop / SessionEnd), Antigravity CLI (SessionEnd /
AfterAgent), Cursor (sessionEnd / stop).
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ENGRAM_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ENGRAM_DIR))

# Only save session summaries longer than this (avoids saving trivial 1-word sessions)
MIN_SUMMARY_LEN = 20


def _text_from_content(content) -> str:
    """Extract plain text from Claude/Antigravity content field (str or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(parts)
    return ""


def parse_first_user_message(transcript_path: str) -> str | None:
    """Return the first substantive user message from a JSONL transcript."""
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

                role = entry.get("role") or entry.get("type", "")
                if role not in ("user", "human"):
                    continue

                text = _text_from_content(entry.get("content", ""))
                text = text.strip()
                if len(text) >= MIN_SUMMARY_LEN:
                    return text[:300]
    except Exception:
        pass
    return None


def main():
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except Exception:
        hook_input = {}

    transcript_path = hook_input.get("transcript_path")
    summary = None
    if transcript_path:
        summary = parse_first_user_message(transcript_path)

    if not summary:
        sys.exit(0)

    try:
        import yaml
        with open(ENGRAM_DIR / "config.yaml") as f:
            config = yaml.safe_load(f)

        db_path = ENGRAM_DIR / config["database"]["path"]
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

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        content = f"[Session {ts}] {summary}"
        embedding = embedder.generate_embedding(content)
        db.insert_thought(content, embedding, tags="session")
        db.close()

    except Exception:
        pass  # Fire-and-forget — never fail loudly

    sys.exit(0)


if __name__ == "__main__":
    main()
