#!/usr/bin/env python3
"""Windsurf pre_user_prompt hook: writes recent memories to .windsurfrules.

Windsurf cannot inject additionalContext directly, so we write memories to
a project-level .windsurfrules file that Cascade reads as system context on
every turn. The file is overwritten each time so it stays current.

Called by Windsurf's pre_user_prompt hook before each user message.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ENGRAM_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ENGRAM_DIR))

RULES_HEADER = "# Engram Memories (auto-updated)\n\n"


def main():
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except Exception:
        hook_input = {}

    # Write to the project's .windsurfrules (cwd from hook input, fall back to home)
    cwd = hook_input.get("cwd") or Path.home()
    rules_file = Path(cwd) / ".windsurfrules"

    try:
        import yaml
        with open(ENGRAM_DIR / "config.yaml") as f:
            config = yaml.safe_load(f)

        raw = config["database"]["path"]
        p = Path(raw).expanduser()
        db_path = p if p.is_absolute() else ENGRAM_DIR / raw
        if not db_path.exists():
            sys.exit(0)

        from engram_db import EngramDatabase

        backend = config["embeddings"].get("backend", "sentence-transformers")
        dim_key = "ollama_dimensions" if backend == "ollama" else "dimensions"
        dim = config["embeddings"].get(dim_key, 384)

        db = EngramDatabase(str(db_path), embedding_dim=dim)
        db.init_database()
        thoughts = db.list_recent(limit=10)
        db.close()

        if not thoughts:
            sys.exit(0)

        lines = [RULES_HEADER, "Your recent Engram memories:\n"]
        for t in thoughts:
            ts = datetime.fromisoformat(t["timestamp"]).strftime("%Y-%m-%d")
            tag_suffix = f" (tags: {t['tags']})" if t["tags"] else ""
            lines.append(f"- [{ts}] {t['content']}{tag_suffix}")
        lines.append(
            "\nUse Engram MCP tools to search or save memories during this session."
        )

        # Preserve any existing non-engram content in the rules file
        existing = ""
        if rules_file.exists():
            existing_text = rules_file.read_text()
            # Strip out any previous engram block
            if "# Engram Memories" in existing_text:
                parts = existing_text.split("# Engram Memories")
                existing = parts[0].rstrip()
            else:
                existing = existing_text.rstrip()

        new_content = (existing + "\n\n" if existing else "") + "\n".join(lines) + "\n"
        rules_file.write_text(new_content)

    except Exception:
        pass  # Never break the session

    sys.exit(0)


if __name__ == "__main__":
    main()
