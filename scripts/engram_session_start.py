#!/usr/bin/env python3
"""Session-start hook: reads recent Engram memories and injects them as context.

Compatible with: Claude Code (SessionStart), Antigravity CLI (SessionStart),
Cursor (sessionStart). Outputs both camelCase and snake_case keys so every tool
picks up what it understands.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ENGRAM_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ENGRAM_DIR))


def main():
    # Read hook input (may be empty on some tools)
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except Exception:
        hook_input = {}

    try:
        import yaml
        with open(ENGRAM_DIR / "config.yaml") as f:
            config = yaml.safe_load(f)

        db_path = ENGRAM_DIR / config["database"]["path"]
        if not db_path.exists():
            # DB not yet initialised — nothing to inject
            print(json.dumps({}))
            return

        from engram_db import EngramDatabase

        backend = config["embeddings"].get("backend", "sentence-transformers")
        dim_key = "ollama_dimensions" if backend == "ollama" else "dimensions"
        dim = config["embeddings"].get(dim_key, 384)

        db = EngramDatabase(str(db_path), embedding_dim=dim)
        db.init_database()
        thoughts = db.list_recent(limit=15)
        db.close()

        if not thoughts:
            print(json.dumps({}))
            return

        lines = [
            "## Engram — Personal Knowledge Base",
            "",
            "Your most recent saved memories (newest first):",
            "",
        ]
        for t in thoughts:
            ts = datetime.fromisoformat(t["timestamp"]).strftime("%Y-%m-%d")
            tag_suffix = f"  _(tags: {t['tags']})_" if t["tags"] else ""
            lines.append(f"- [{ts}] {t['content']}{tag_suffix}")

        lines += [
            "",
            "Use `search_engram` to find specific memories by meaning.",
            "Use `save_thought` to save new insights during this session.",
        ]

        context = "\n".join(lines)
        event_name = hook_input.get("hook_event_name", "SessionStart")

        output = {
            # Claude Code / Antigravity
            "additionalContext": context,
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "additionalContext": context,
            },
            # Cursor
            "additional_context": context,
        }
        print(json.dumps(output))

    except Exception as e:
        # Never crash loudly — hooks must not break the session
        print(json.dumps({"_engram_error": str(e)}), file=sys.stderr)
        print(json.dumps({}))


if __name__ == "__main__":
    main()
