"""Database layer using SQLite + sqlite-vec for vector search."""

import sqlite3
import json
import struct
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

try:
    import sqlite_vec
except ImportError:
    raise ImportError("sqlite-vec is required. Install with: pip install sqlite-vec")


class EngramDatabase:
    def __init__(self, db_path: str, embedding_dim: int = 384):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_dim = embedding_dim
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.enable_load_extension(True)
            sqlite_vec.load(self.conn)
            self.conn.enable_load_extension(False)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def init_database(self):
        self.connect()
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS thoughts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                tags TEXT,
                metadata TEXT
            )
        """)
        self.conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_thoughts USING vec0(
                thought_id INTEGER PRIMARY KEY,
                embedding FLOAT[{self.embedding_dim}]
            )
        """)
        self.conn.commit()

    def _pack(self, embedding: np.ndarray) -> bytes:
        return struct.pack(f'{len(embedding)}f', *embedding.tolist())

    def insert_thought(
        self,
        content: str,
        embedding: np.ndarray,
        tags: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        self.connect()
        timestamp = datetime.now().isoformat()
        metadata_json = json.dumps(metadata) if metadata else None

        cursor = self.conn.execute(
            "INSERT INTO thoughts (content, timestamp, tags, metadata) VALUES (?, ?, ?, ?)",
            (content, timestamp, tags, metadata_json)
        )
        thought_id = cursor.lastrowid

        self.conn.execute(
            "INSERT INTO vec_thoughts (thought_id, embedding) VALUES (?, ?)",
            (thought_id, self._pack(embedding))
        )
        self.conn.commit()
        return thought_id

    def semantic_search(
        self,
        query_embedding: np.ndarray,
        limit: int = 10,
        threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        self.connect()
        cursor = self.conn.execute("""
            SELECT
                t.id,
                t.content,
                t.timestamp,
                t.tags,
                t.metadata,
                1 - vec_distance_cosine(v.embedding, ?) as similarity
            FROM vec_thoughts v
            JOIN thoughts t ON t.id = v.thought_id
            WHERE similarity >= ?
            ORDER BY similarity DESC
            LIMIT ?
        """, (self._pack(query_embedding), threshold, limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'content': row[1],
                'timestamp': row[2],
                'tags': row[3],
                'metadata': json.loads(row[4]) if row[4] else None,
                'similarity': row[5]
            })
        return results

    def list_recent(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        self.connect()
        cursor = self.conn.execute("""
            SELECT id, content, timestamp, tags, metadata
            FROM thoughts
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'content': row[1],
                'timestamp': row[2],
                'tags': row[3],
                'metadata': json.loads(row[4]) if row[4] else None
            })
        return results

    def get_stats(self) -> Dict[str, Any]:
        self.connect()
        cursor = self.conn.execute("SELECT COUNT(*) FROM thoughts")
        total = cursor.fetchone()[0]

        if total == 0:
            return {'total_thoughts': 0, 'oldest_thought': None, 'newest_thought': None, 'unique_tags': 0}

        cursor = self.conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM thoughts")
        oldest, newest = cursor.fetchone()

        cursor = self.conn.execute("SELECT tags FROM thoughts WHERE tags IS NOT NULL")
        all_tags: set = set()
        for (tags,) in cursor.fetchall():
            if tags:
                all_tags.update(t.strip() for t in tags.split(','))

        return {
            'total_thoughts': total,
            'oldest_thought': oldest,
            'newest_thought': newest,
            'unique_tags': len(all_tags)
        }

    def get_thought_by_id(self, thought_id: int) -> Optional[Dict[str, Any]]:
        self.connect()
        cursor = self.conn.execute(
            "SELECT id, content, timestamp, tags, metadata FROM thoughts WHERE id = ?",
            (thought_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'content': row[1],
                'timestamp': row[2],
                'tags': row[3],
                'metadata': json.loads(row[4]) if row[4] else None
            }
        return None

    def delete_thought(self, thought_id: int) -> bool:
        self.connect()
        cursor = self.conn.execute("DELETE FROM thoughts WHERE id = ?", (thought_id,))
        self.conn.execute("DELETE FROM vec_thoughts WHERE thought_id = ?", (thought_id,))
        self.conn.commit()
        return cursor.rowcount > 0
