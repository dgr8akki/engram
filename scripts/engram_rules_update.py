#!/usr/bin/env python3
"""Write recent Engram memories to static rules files for tools without hook injection.

Targets (written in the project directory):
  .cursorrules                      → Cursor
  .windsurfrules                    → Windsurf
  .github/copilot-instructions.md   → GitHub Copilot

Uses HTML comment markers to splice the Engram block without destroying existing
content in those files. Safe to run repeatedly — idempotent.

Call as a hook (reads cwd from hook input) or manually via:
  engram rules update [--dir PATH]

Replaces the Windsurf-specific engram_windsurf_update.py.
Compatible with: any tool that passes cwd in its hook payload.
"""

import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ENGRAM_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ENGRAM_DIR))

BLOCK_START = "<!-- engram:start -->"
BLOCK_END   = "<!-- engram:end -->"
LIMIT       = 15


def _fetch_recent(config: dict) -> list:
    """Pull recent memories from the running HTTP server."""
    host = config.get("http", {}).get("host", "127.0.0.1")
    port = config.get("http", {}).get("port", 7823)
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/thoughts?limit={LIMIT}", timeout=2) as r:
            return json.loads(r.read()).get("thoughts", [])
    except Exception:
        return []


def _format_block(thoughts: list) -> str:
    lines = [
        "## Engram memories (auto-updated)",
        "",
        "Your recent saved memories:",
        "",
    ]
    for t in thoughts:
        ts = datetime.fromisoformat(t["timestamp"]).strftime("%Y-%m-%d")
        tag_suffix = f"  (tags: {t['tags']})" if t.get("tags") else ""
        lines.append(f"- [{ts}] {t['content']}{tag_suffix}")
    lines += [
        "",
        "Use `search_engram` to find specific memories by meaning.",
        "Use `save_thought` to capture new decisions mid-session.",
    ]
    return "\n".join(lines)


def _splice(existing: str, block: str) -> str:
    """Replace the engram block in existing content, or append it."""
    wrapped = f"{BLOCK_START}\n{block}\n{BLOCK_END}"
    if BLOCK_START in existing:
        before = existing[: existing.index(BLOCK_START)].rstrip()
        tail   = existing[existing.index(BLOCK_END) + len(BLOCK_END) :].lstrip()
        parts  = [p for p in [before, wrapped, tail] if p]
        return "\n\n".join(parts) + "\n"
    sep = "\n\n" if existing.strip() else ""
    return existing.rstrip() + sep + wrapped + "\n"


def update_rules_files(project_dir: Path, thoughts: list) -> list[str]:
    """Write the Engram block into all applicable rules files under project_dir.

    Returns paths of files that were written.
    """
    if not thoughts:
        return []

    block = _format_block(thoughts)
    targets = [
        project_dir / ".cursorrules",
        project_dir / ".windsurfrules",
        project_dir / ".github" / "copilot-instructions.md",
    ]
    updated = []
    for path in targets:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = path.read_text() if path.exists() else ""
            path.write_text(_splice(existing, block))
            updated.append(str(path))
        except Exception:
            pass
    return updated


def main():
    """Hook entrypoint — reads cwd from hook input JSON on stdin."""
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except Exception:
        hook_input = {}

    cwd = hook_input.get("cwd") or str(Path.cwd())

    try:
        import yaml
        with open(ENGRAM_DIR / "config.yaml") as f:
            config = yaml.safe_load(f)
    except Exception:
        print(json.dumps({}))
        sys.exit(0)

    thoughts = _fetch_recent(config)
    update_rules_files(Path(cwd), thoughts)

    print(json.dumps({}))
    sys.exit(0)


if __name__ == "__main__":
    main()
