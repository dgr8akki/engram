#!/usr/bin/env python3
"""Session-start hook: reads recent Engram memories and injects them as context.

Compatible with: Claude Code (SessionStart), Antigravity CLI (SessionStart),
Cursor (sessionStart). Outputs both camelCase and snake_case keys so every tool
picks up what it understands.

Also ensures the HTTP server is running — spawns it in the background if not.
"""

import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ENGRAM_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ENGRAM_DIR))


def _find_python() -> Path:
    for candidate in [
        Path("/opt/homebrew/opt/engram/libexec/venv/bin/python3"),
        Path("/usr/local/opt/engram/libexec/venv/bin/python3"),
        ENGRAM_DIR / "venv" / "bin" / "python3",
    ]:
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def _find_cli() -> Path:
    for candidate in [
        Path("/opt/homebrew/opt/engram/libexec/engram_cli.py"),
        Path("/usr/local/opt/engram/libexec/engram_cli.py"),
        ENGRAM_DIR / "engram_cli.py",
    ]:
        if candidate.exists():
            return candidate
    return ENGRAM_DIR / "engram_cli.py"


def _ensure_http_server(config: dict) -> None:
    """Start the HTTP server in the background if it isn't already responding."""
    host = config.get("http", {}).get("host", "127.0.0.1")
    port = config.get("http", {}).get("port", 7823)
    health_url = f"http://{host}:{port}/health"

    try:
        urllib.request.urlopen(health_url, timeout=1)
        return  # already up
    except Exception:
        pass

    # Not running — spawn detached
    subprocess.Popen(
        [str(_find_python()), str(_find_cli()), "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Poll up to 3 s for it to come up before continuing
    for _ in range(6):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(health_url, timeout=1)
            return
        except Exception:
            pass


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

        try:
            _ensure_http_server(config)
        except Exception:
            pass  # never block the session over this

        raw = config["database"]["path"]
        p = Path(raw).expanduser()
        db_path = p if p.is_absolute() else ENGRAM_DIR / raw
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
        stats = db.get_stats()
        db.close()

        if stats["total_thoughts"] == 0:
            print(json.dumps({}))
            return

        newest = datetime.fromisoformat(stats["newest_thought"]).strftime("%Y-%m-%d %H:%M")
        context = (
            f"Engram: {stats['total_thoughts']} thoughts saved "
            f"({stats['unique_tags']} tags, last saved {newest}). "
            "Use `search_engram` to look up relevant memories, `save_thought` to save new ones."
        )
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
