#!/usr/bin/env python3
"""HTTP/REST fallback server for tools that don't support stdio MCP."""

from pathlib import Path
from datetime import datetime
import yaml

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

config_path = Path(__file__).parent / "config.yaml"
with open(config_path) as f:
    config = yaml.safe_load(f)

_db = None
_embedder = None


def get_db():
    global _db
    if _db is None:
        from engram_db import EngramDatabase
        backend = config['embeddings'].get('backend', 'sentence-transformers')
        dim = config['embeddings'].get('ollama_dimensions' if backend == 'ollama' else 'dimensions', 384)
        raw = config['database']['path']
        p = Path(raw).expanduser()
        db_path = p if p.is_absolute() else Path(__file__).parent / raw
        _db = EngramDatabase(str(db_path), embedding_dim=dim)
        _db.init_database()
    return _db


def get_embedder():
    global _embedder
    if _embedder is None:
        from engram_embeddings import EmbeddingGenerator
        _embedder = EmbeddingGenerator(config['embeddings'])
    return _embedder


app = FastAPI(title="Engram", description="Local semantic knowledge base", version="1.0.0")


class ThoughtIn(BaseModel):
    content: str
    tags: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/thoughts")
def list_thoughts(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    thoughts = get_db().list_recent(limit=limit, offset=offset)
    return {"thoughts": thoughts, "count": len(thoughts)}


@app.get("/thoughts/search")
def search_thoughts(
    q: str = Query(..., description="Natural language search query"),
    limit: int = Query(10, ge=1, le=50),
    threshold: float = Query(0.3, ge=0.0, le=1.0)
):
    embedding = get_embedder().generate_embedding(q)
    results = get_db().semantic_search(embedding, limit=limit, threshold=threshold)
    return {"query": q, "results": results, "count": len(results)}


@app.get("/thoughts/{thought_id}")
def get_thought(thought_id: int):
    thought = get_db().get_thought_by_id(thought_id)
    if not thought:
        raise HTTPException(status_code=404, detail=f"Thought {thought_id} not found")
    return thought


@app.post("/thoughts", status_code=201)
def create_thought(body: ThoughtIn):
    embedding = get_embedder().generate_embedding(body.content)
    thought_id = get_db().insert_thought(body.content, embedding, tags=body.tags)
    return {"id": thought_id, "content": body.content, "tags": body.tags}


@app.delete("/thoughts/{thought_id}")
def remove_thought(thought_id: int):
    deleted = get_db().delete_thought(thought_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Thought {thought_id} not found")
    return {"deleted": thought_id}


@app.get("/stats")
def stats():
    return get_db().get_stats()


def run(host: str = None, port: int = None):
    h = host or config['http']['host']
    p = port or config['http']['port']
    uvicorn.run(app, host=h, port=p)


if __name__ == "__main__":
    run()
