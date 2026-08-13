"""
SQLite helper functions.

Schema:
    chunks(id INTEGER PK, source TEXT, chunk_index INTEGER, content TEXT,
           embedding TEXT)  -- embedding is a JSON-serialized list of floats
    conversations(id INTEGER PK, title TEXT, created_at TEXT)
    messages(id INTEGER PK, conversation_id INTEGER FK, role TEXT,
             content TEXT, sources TEXT, seconds REAL, created_at TEXT)

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

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources TEXT,
    seconds REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
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


# ---------- Conversation history ----------

def create_conversation(conn: sqlite3.Connection, title: str) -> int:
    cur = conn.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
    conn.commit()
    return cur.lastrowid


def add_message(conn: sqlite3.Connection, conversation_id: int, role: str, content: str,
                 sources: list[str] | None = None, seconds: float | None = None) -> None:
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, sources, seconds) VALUES (?, ?, ?, ?, ?)",
        (conversation_id, role, content, json.dumps(sources) if sources else None, seconds),
    )
    conn.commit()


def list_conversations(conn: sqlite3.Connection) -> list[dict]:
    """Most recent first."""
    rows = conn.execute("SELECT id, title FROM conversations ORDER BY id DESC").fetchall()
    return [{"id": r[0], "title": r[1]} for r in rows]


def get_conversation_messages(conn: sqlite3.Connection, conversation_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content, sources, seconds FROM messages WHERE conversation_id = ? ORDER BY id ASC",
        (conversation_id,),
    ).fetchall()
    return [
        {"role": r[0], "content": r[1], "sources": json.loads(r[2]) if r[2] else [], "seconds": r[3]}
        for r in rows
    ]
