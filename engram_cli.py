#!/usr/bin/env python3
"""CLI for Engram — local semantic knowledge base."""

import sys
from pathlib import Path
from datetime import datetime
import yaml
import click

__version__ = "1.0.0"


def load_config():
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        click.echo("Error: config.yaml not found", err=True)
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


_db = None
_embedder = None


def get_db():
    global _db
    if _db is None:
        from engram_db import EngramDatabase
        config = load_config()
        backend = config['embeddings'].get('backend', 'sentence-transformers')
        dim = config['embeddings'].get('ollama_dimensions' if backend == 'ollama' else 'dimensions', 384)
        db_path = Path(__file__).parent / config['database']['path']
        _db = EngramDatabase(str(db_path), embedding_dim=dim)
    return _db


def get_embedder():
    global _embedder
    if _embedder is None:
        from engram_embeddings import EmbeddingGenerator
        config = load_config()
        _embedder = EmbeddingGenerator(config['embeddings'])
    return _embedder


@click.group(name="engram", context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="engram")
def cli():
    """Engram — your local semantic knowledge base."""
    pass


@cli.command()
def init():
    """Initialize the Engram database."""
    try:
        db = get_db()
        db.init_database()
        click.echo("Database initialized.")
        click.echo(f"Location: {db.db_path}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('content')
@click.option('--tags', '-t', help='Comma-separated tags')
def add(content, tags):
    """Save a thought to your knowledge base."""
    try:
        embedding = get_embedder().generate_embedding(content)
        thought_id = get_db().insert_thought(content, embedding, tags=tags)
        click.echo(f"Saved (ID: {thought_id})")
        if tags:
            click.echo(f"Tags: {tags}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command(name='list')
@click.option('--limit', '-l', default=20, help='Number of thoughts to show')
@click.option('--offset', '-o', default=0, help='Skip this many thoughts')
def list_cmd(limit, offset):
    """List recent thoughts."""
    try:
        thoughts = get_db().list_recent(limit=limit, offset=offset)
        if not thoughts:
            click.echo('No thoughts yet. Add one with: engram add "your thought"')
            return
        click.echo(f"\n{len(thoughts)} thoughts:\n")
        for t in thoughts:
            ts = datetime.fromisoformat(t['timestamp']).strftime('%Y-%m-%d %H:%M')
            click.echo(f"[{t['id']}] {ts}")
            click.echo(f"  {t['content']}")
            if t['tags']:
                click.echo(f"  Tags: {t['tags']}")
            click.echo()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('query')
@click.option('--limit', '-l', default=10, help='Number of results')
@click.option('--threshold', '-t', default=None, type=float, help='Similarity threshold (0-1)')
def search(query, limit, threshold):
    """Semantic search across your thoughts."""
    try:
        config = load_config()
        if threshold is None:
            threshold = config['search']['similarity_threshold']

        embedding = get_embedder().generate_embedding(query)
        results = get_db().semantic_search(embedding, limit=limit, threshold=threshold)

        if not results:
            click.echo(f"No thoughts found matching '{query}' (threshold: {threshold})")
            return

        click.echo(f"\nFound {len(results)} matching thoughts:\n")
        for r in results:
            ts = datetime.fromisoformat(r['timestamp']).strftime('%Y-%m-%d %H:%M')
            click.echo(f"[{r['id']}] {r['similarity']*100:.1f}%  {ts}")
            click.echo(f"  {r['content']}")
            if r['tags']:
                click.echo(f"  Tags: {r['tags']}")
            click.echo()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('thought_id', type=int)
def delete(thought_id):
    """Delete a thought by ID."""
    try:
        deleted = get_db().delete_thought(thought_id)
        if deleted:
            click.echo(f"Deleted thought {thought_id}.")
        else:
            click.echo(f"No thought found with ID {thought_id}.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def stats():
    """Show knowledge base statistics."""
    try:
        s = get_db().get_stats()
        click.echo(f"\nTotal thoughts: {s['total_thoughts']}")
        if s['total_thoughts'] > 0:
            oldest = datetime.fromisoformat(s['oldest_thought'])
            newest = datetime.fromisoformat(s['newest_thought'])
            click.echo(f"Oldest: {oldest.strftime('%Y-%m-%d %H:%M')}")
            click.echo(f"Newest: {newest.strftime('%Y-%m-%d %H:%M')}")
            click.echo(f"Unique tags: {s['unique_tags']}")
            days = (newest - oldest).days
            if days > 0:
                click.echo(f"Span: {days} days ({s['total_thoughts']/days:.1f}/day)")
        click.echo()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Show all clients including undetected ones')
def install(verbose):
    """Configure Engram for all detected AI coding tools.

    Registers the MCP server and installs the skill for each detected tool.
    Detects: Claude Code, Cursor, Windsurf, Antigravity, Cline.
    """
    from engram_install import run_install
    run_install(verbose=verbose)


@cli.group()
def skill():
    """Manage the Engram skill for AI coding tools."""
    pass


@skill.command(name='install')
@click.option('--verbose', '-v', is_flag=True, help='Show undetected tools too')
def skill_install(verbose):
    """Install the Engram skill into ~/.agents/skills/ and link to all detected tools.

    Creates ~/.agents/skills/engram -> <repo>/skill/ then symlinks into:
      ~/.claude/skills/engram
      ~/.gemini/antigravity/skills/engram
      ~/.gemini/antigravity-ide/skills/engram
      ~/.cursor/skills/engram
      ~/.windsurf/skills/engram
    """
    from engram_install import run_skill_install
    run_skill_install(verbose=verbose)


@skill.command(name='path')
def skill_path():
    """Print the path to the Engram skill file."""
    from pathlib import Path
    skill_file = Path(__file__).parent / "skill" / "SKILL.md"
    click.echo(str(skill_file))


@cli.group()
def hooks():
    """Manage Engram memory hooks for AI coding tools."""
    pass


@hooks.command(name='install')
@click.option('--verbose', '-v', is_flag=True, help='Show undetected tools too')
def hooks_install(verbose):
    """Install session-lifecycle hooks into all detected AI coding tools.

    Hooks installed per tool:

    \b
    Claude Code / Antigravity CLI / Cursor:
      SessionStart     → injects recent memories as context at session start
      UserPromptSubmit → auto-saves when you say 'remember: ...' or 'note: ...'
      SessionEnd       → records session topic to Engram

    \b
    Windsurf:
      pre_user_prompt  → writes memories to .windsurfrules before each turn
      post_cascade_response_with_transcript → saves session topic at turn end
    """
    from engram_install import run_hooks_install
    run_hooks_install(verbose=verbose)


@cli.group()
def autostart():
    """Manage automatic startup of the Engram HTTP server at login (macOS only)."""
    pass


@autostart.command(name='install')
def autostart_install():
    """Install Engram HTTP server as a LaunchAgent so it starts at every login."""
    from engram_install import install_launch_agent
    ok, msg = install_launch_agent()
    if ok:
        click.echo(f"LaunchAgent installed and loaded.")
        click.echo(f"Plist: {msg}")
        click.echo("Engram HTTP server will start automatically at login.")
        click.echo("Logs: ~/Library/Logs/engram.log")
    else:
        click.echo(f"Error: {msg}", err=True)
        sys.exit(1)


@autostart.command(name='remove')
def autostart_remove():
    """Remove the Engram LaunchAgent (disables autostart)."""
    from engram_install import remove_launch_agent
    ok, msg = remove_launch_agent()
    if ok:
        click.echo(f"LaunchAgent removed: {msg}")
    else:
        click.echo(f"Error: {msg}", err=True)
        sys.exit(1)


@autostart.command(name='status')
def autostart_status():
    """Show whether the Engram LaunchAgent is installed and running."""
    from engram_install import launch_agent_status, LAUNCH_AGENT_PLIST
    status = launch_agent_status()
    click.echo(f"Status: {status}")
    if LAUNCH_AGENT_PLIST.exists():
        click.echo(f"Plist:  {LAUNCH_AGENT_PLIST}")


@cli.group()
def rules():
    """Keep rules files in sync for tools without hook injection (Copilot, Zed, etc.)."""
    pass


@rules.command(name='update')
@click.option('--dir', 'target_dir', default=None,
              help='Project directory to update (default: current dir)')
def rules_update(target_dir):
    """Write recent memories to .cursorrules, .windsurfrules, and copilot-instructions.md.

    Run this in a project directory to seed it with your Engram memories.
    The HTTP server must be running (engram serve / engram autostart install).
    """
    import importlib.util
    scripts_dir = Path(__file__).parent / "scripts"
    spec = importlib.util.spec_from_file_location(
        "engram_rules_update", scripts_dir / "engram_rules_update.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    config = load_config()
    thoughts = mod._fetch_recent(config)

    if not thoughts:
        click.echo("No memories found. Is the HTTP server running?")
        click.echo("Start it with: engram serve   or   engram autostart install")
        return

    project_dir = Path(target_dir) if target_dir else Path.cwd()
    updated = mod.update_rules_files(project_dir, thoughts)

    if updated:
        click.echo(f"Updated {len(thoughts)} memories into {len(updated)} file(s):")
        for p in updated:
            click.echo(f"  {p}")
    else:
        click.echo("No files written (no thoughts or permission error).")


@rules.command(name='install')
def rules_install():
    """Install a LaunchAgent that refreshes rules files at login and every 30 minutes.

    Writes to ~/ so tools that read global rules (Cursor ~/.cursorrules) stay
    current even without a per-project hook. Per-project updates happen via the
    SessionStart hook installed by engram install.
    """
    from engram_install import install_rules_agent
    ok, msg = install_rules_agent()
    if ok:
        click.echo("Rules updater installed and loaded.")
        click.echo(msg)
        click.echo("Memories will refresh at login and every 30 minutes.")
        click.echo("Logs: ~/Library/Logs/engram.log")
    else:
        click.echo(f"Error: {msg}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--host', default=None, help='Host to bind (default: 127.0.0.1)')
@click.option('--port', default=None, type=int, help='Port to bind (default: 7823)')
def serve(host, port):
    """Start the HTTP REST server (for tools without MCP support).

    Endpoints:
      GET  /thoughts          - list recent thoughts
      GET  /thoughts/search?q=... - semantic search
      POST /thoughts          - save a thought
      GET  /thoughts/{id}     - get by ID
      DELETE /thoughts/{id}   - delete by ID
      GET  /stats             - statistics
    """
    from engram_http_server import run
    config = load_config()
    h = host or config['http']['host']
    p = port or config['http']['port']
    click.echo(f"Starting Engram HTTP server on http://{h}:{p}")
    run(host=h, port=p)


if __name__ == '__main__':
    cli(prog_name="engram")
