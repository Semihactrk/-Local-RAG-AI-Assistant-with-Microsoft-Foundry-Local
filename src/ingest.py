"""
Step 2: Document ingestion pipeline.

Reads .txt and .md files from data/documents, splits them into
paragraph-based chunks, generates an embedding for each chunk using
Foundry Local's qwen3-embedding-0.6b model, and stores them in SQLite
(db/knowledge.db).

Run:
    .venv\\Scripts\\python.exe src\\ingest.py
"""

import sys
from pathlib import Path

from foundry_local_sdk import Configuration, FoundryLocalManager

from chunking import split_into_chunks
from db import clear_source, count_chunks, get_connection, insert_chunk

sys.stdout.reconfigure(encoding="utf-8")

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "documents"
EMBEDDING_MODEL_ALIAS = "qwen3-embedding-0.6b"
BATCH_SIZE = 16


def load_documents() -> list[tuple[str, str]]:
    """Returns (filename, content) pairs."""
    docs = []
    for path in sorted(DOCS_DIR.glob("*")):
        if path.suffix.lower() in (".txt", ".md") and path.is_file():
            docs.append((path.name, path.read_text(encoding="utf-8")))
    return docs


def main():
    docs = load_documents()
    if not docs:
        print(f"[WARNING] No .txt/.md files found in {DOCS_DIR}. "
              f"Add some documents first.")
        return

    config = Configuration(app_name="foundry_rag_demo")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance

    print(f"Loading embedding model: {EMBEDDING_MODEL_ALIAS}")
    model = manager.catalog.get_model(EMBEDDING_MODEL_ALIAS)
    model.download(
        lambda p: print(f"\rDownloading model: {p:.2f}%", end="", flush=True)
    )
    print()
    model.load()
    client = model.get_embedding_client()

    conn = get_connection()
    total_chunks = 0

    for filename, content in docs:
        chunks = split_into_chunks(content)
        print(f"\n{filename}: {len(chunks)} chunks")

        clear_source(conn, filename)  # avoid duplicates if this file is re-ingested

        for batch_start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[batch_start: batch_start + BATCH_SIZE]
            response = client.generate_embeddings(batch)
            for i, item in enumerate(response.data):
                chunk_index = batch_start + i
                insert_chunk(conn, filename, chunk_index, batch[i], item.embedding)
                total_chunks += 1

        conn.commit()

    model.unload()

    final_count = count_chunks(conn)
    print(f"\n[OK] Ingestion complete. {total_chunks} chunks processed this run, "
          f"{final_count} total chunks in the database.")
    print(f"Sanity check: compare the expected count ({total_chunks}) against "
          f"the database count ({final_count}).")


if __name__ == "__main__":
    main()
