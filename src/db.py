"""
SQLite helper functions.

Schema:
    chunks(id INTEGER PK, source TEXT, chunk_index INTEGER, content TEXT,
           embedding TEXT)  -- embedding is a JSON-serialized list of floats

Storing the embedding as JSON TEXT instead of a BLOB keeps things readable
and is fast enough for a small dataset (a few hundred chunks). For larger
datasets, BLOB + struct.pack would be preferable.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "knowledge.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def insert_chunk(conn: sqlite3.Connection, source: str, chunk_index: int, content: str, embedding: list[float]) -> None:
    conn.execute(
        "INSERT INTO chunks (source, chunk_index, content, embedding) VALUES (?, ?, ?, ?)",
        (source, chunk_index, content, json.dumps(embedding)),
    )


def clear_source(conn: sqlite3.Connection, source: str) -> None:
    """Clear old chunks if the same document is ingested again (avoids duplicates)."""
    conn.execute("DELETE FROM chunks WHERE source = ?", (source,))


def fetch_all_chunks(conn: sqlite3.Connection):
    """Returns (id, source, content, embedding-as-list) tuples."""
    rows = conn.execute("SELECT id, source, content, embedding FROM chunks").fetchall()
    return [(r[0], r[1], r[2], json.loads(r[3])) for r in rows]


def count_chunks(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
