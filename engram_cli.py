#!/usr/bin/env python3
"""CLI for Engram — local semantic knowledge base."""

import sys
from pathlib import Path
from datetime import datetime
import yaml
import click

from engram_db import EngramDatabase
from engram_embeddings import EmbeddingGenerator


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
        config = load_config()
        backend = config['embeddings'].get('backend', 'sentence-transformers')
        dim = config['embeddings'].get('ollama_dimensions' if backend == 'ollama' else 'dimensions', 384)
        db_path = Path(__file__).parent / config['database']['path']
        _db = EngramDatabase(str(db_path), embedding_dim=dim)
    return _db


def get_embedder():
    global _embedder
    if _embedder is None:
        config = load_config()
        _embedder = EmbeddingGenerator(config['embeddings'])
    return _embedder


@click.group()
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
    """Auto-configure Engram MCP server for detected AI coding tools.

    Detects and configures: Claude Code, Cursor, Windsurf, Antigravity, Cline.
    """
    from engram_install import run_install
    run_install(verbose=verbose)


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
    cli()
