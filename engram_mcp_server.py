#!/usr/bin/env python3
"""MCP server for Engram — exposes thought capture and semantic search to AI coding tools."""

import sys
import asyncio
from pathlib import Path
from datetime import datetime
import yaml

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


def load_config():
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        print("Error: config.yaml not found", file=sys.stderr)
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


config = load_config()

def _resolve_db_path(cfg: dict) -> Path:
    raw = cfg['database']['path']
    p = Path(raw).expanduser()
    return p if p.is_absolute() else Path(__file__).parent / raw

db_path = _resolve_db_path(config)
_db = None
_embedder = None


def get_db():
    global _db
    if _db is None:
        from engram_db import EngramDatabase
        dim = config['embeddings'].get(
            'ollama_dimensions' if config['embeddings'].get('backend') == 'ollama' else 'dimensions', 384
        )
        _db = EngramDatabase(str(db_path), embedding_dim=dim)
        _db.init_database()
    return _db


def get_embedder():
    global _embedder
    if _embedder is None:
        from engram_embeddings import EmbeddingGenerator
        _embedder = EmbeddingGenerator(config['embeddings'])
        if config['embeddings'].get('backend', 'sentence-transformers') == 'sentence-transformers':
            _ = _embedder.model
    return _embedder


server = Server(config['mcp']['server_name'])


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_engram",
            description=(
                "Semantically search your personal knowledge base by meaning, not just keywords. "
                "Use this when the user asks 'what have I thought about X', 'do I have notes on Y', "
                "or 'find thoughts related to Z'. Returns ranked results with similarity scores."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query — describe what you're looking for, not just keywords. Example: 'ideas about improving developer productivity'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return. Default 10, max 50.",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Minimum similarity score (0.0–1.0). Lower values return more results but less relevant. Default 0.3.",
                        "default": 0.3,
                        "minimum": 0.0,
                        "maximum": 1.0
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="list_recent_thoughts",
            description=(
                "Browse your most recently captured thoughts in reverse chronological order. "
                "Use this when the user wants to review recent entries, catch up on what was saved, "
                "or browse without a specific query in mind."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of thoughts to retrieve. Default 20.",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of thoughts to skip for pagination. Default 0.",
                        "default": 0,
                        "minimum": 0
                    }
                }
            }
        ),
        Tool(
            name="save_thought",
            description=(
                "Save a thought, idea, note, or piece of information to your local knowledge base. "
                "Use this when the user says 'remember this', 'save this', 'note that', or "
                "'add this to my brain'. Content is embedded and indexed for semantic search."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The thought or note to save. Be specific — more detail means better search recall later."
                    },
                    "tags": {
                        "type": "string",
                        "description": "Optional comma-separated tags for categorization. Example: 'ai,productivity,ideas'"
                    }
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="delete_thought",
            description="Delete a thought by its ID. Use when the user wants to remove a specific entry.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "The numeric ID of the thought to delete (shown in search/list results)"
                    }
                },
                "required": ["id"]
            }
        ),
        Tool(
            name="engram_stats",
            description="Get statistics about the knowledge base: total count, date range, and tag diversity.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "search_engram":
            return await _search(arguments)
        elif name == "list_recent_thoughts":
            return await _list_recent(arguments)
        elif name == "save_thought":
            return await _save(arguments)
        elif name == "delete_thought":
            return await _delete(arguments)
        elif name == "engram_stats":
            return await _stats(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        msg = f"Error in {name}: {e}"
        print(msg, file=sys.stderr)
        return [TextContent(type="text", text=msg)]


async def _search(args: dict) -> list[TextContent]:
    query = args.get("query")
    if not query:
        return [TextContent(type="text", text="Error: query is required")]

    limit = args.get("limit", config['search']['default_limit'])
    threshold = args.get("threshold", config['search']['similarity_threshold'])

    embedding = get_embedder().generate_embedding(query)
    results = get_db().semantic_search(embedding, limit=limit, threshold=threshold)

    if not results:
        return [TextContent(type="text", text=f"No thoughts found matching '{query}' (threshold: {threshold})")]

    lines = [f"Found {len(results)} matching thoughts:\n"]
    for i, r in enumerate(results, 1):
        ts = datetime.fromisoformat(r['timestamp']).strftime('%Y-%m-%d %H:%M')
        lines.append(f"{i}. [ID:{r['id']}] {r['similarity']*100:.1f}% — {ts}")
        lines.append(f"   {r['content']}")
        if r['tags']:
            lines.append(f"   Tags: {r['tags']}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def _list_recent(args: dict) -> list[TextContent]:
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    thoughts = get_db().list_recent(limit=limit, offset=offset)

    if not thoughts:
        return [TextContent(type="text", text="No thoughts yet. Save one with the save_thought tool.")]

    lines = [f"Recent thoughts ({len(thoughts)}):\n"]
    for i, t in enumerate(thoughts, 1 + offset):
        ts = datetime.fromisoformat(t['timestamp']).strftime('%Y-%m-%d %H:%M')
        lines.append(f"{i}. [ID:{t['id']}] {ts}")
        lines.append(f"   {t['content']}")
        if t['tags']:
            lines.append(f"   Tags: {t['tags']}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def _save(args: dict) -> list[TextContent]:
    content = args.get("content")
    if not content:
        return [TextContent(type="text", text="Error: content is required")]

    tags = args.get("tags")
    embedding = get_embedder().generate_embedding(content)
    thought_id = get_db().insert_thought(content, embedding, tags=tags)

    lines = [f"Saved. (ID: {thought_id})", f"Content: {content}"]
    if tags:
        lines.append(f"Tags: {tags}")

    return [TextContent(type="text", text="\n".join(lines))]


async def _delete(args: dict) -> list[TextContent]:
    thought_id = args.get("id")
    if thought_id is None:
        return [TextContent(type="text", text="Error: id is required")]

    deleted = get_db().delete_thought(int(thought_id))
    if deleted:
        return [TextContent(type="text", text=f"Deleted thought ID {thought_id}.")]
    return [TextContent(type="text", text=f"No thought found with ID {thought_id}.")]


async def _stats(args: dict) -> list[TextContent]:
    stats = get_db().get_stats()
    lines = ["Engram statistics:\n", f"Total thoughts: {stats['total_thoughts']}"]

    if stats['total_thoughts'] > 0:
        oldest = datetime.fromisoformat(stats['oldest_thought'])
        newest = datetime.fromisoformat(stats['newest_thought'])
        lines.append(f"Oldest: {oldest.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Newest: {newest.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Unique tags: {stats['unique_tags']}")
        days = (newest - oldest).days
        if days > 0:
            lines.append(f"Span: {days} days ({stats['total_thoughts']/days:.1f} thoughts/day)")

    return [TextContent(type="text", text="\n".join(lines))]


async def main():
    print("Starting Engram MCP server...", file=sys.stderr)
    print(f"Database: {db_path}", file=sys.stderr)
    backend = config['embeddings'].get('backend', 'sentence-transformers')
    print(f"Embedding backend: {backend} (loads on first tool call)", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        print("Engram MCP server ready.", file=sys.stderr)
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
