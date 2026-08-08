"""
Retrieval function.

Embeds the query, computes cosine similarity against every chunk embedding
in SQLite, and returns the top-K most relevant chunks.

Note: this brute-force approach (loading all vectors into memory and
comparing) is fine for small datasets (a few hundred chunks) -- as noted in
the plan PDF, a large N would need a dedicated vector DB.
"""

import numpy as np

from db import fetch_all_chunks, get_connection

TOP_K = 3


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def get_top_chunks(query_embedding: list[float], top_k: int = TOP_K):
    """
    query_embedding: the query's embedding vector (list[float]).
    Returns: [{"source": str, "content": str, "score": float}, ...] sorted
    from highest to lowest score.
    """
    conn = get_connection()
    rows = fetch_all_chunks(conn)  # [(id, source, content, embedding), ...]

    if not rows:
        return []

    q = np.array(query_embedding, dtype=np.float32)
    scored = []
    for _id, source, content, embedding in rows:
        score = cosine_similarity(q, np.array(embedding, dtype=np.float32))
        scored.append({"source": source, "content": content, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


if __name__ == "__main__":
    # Quick manual test: embed a query and print the most relevant chunks.
    import sys

    from foundry_local_sdk import Configuration, FoundryLocalManager

    sys.stdout.reconfigure(encoding="utf-8")

    config = Configuration(app_name="foundry_rag_demo")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance

    model = manager.catalog.get_model("qwen3-embedding-0.6b")
    model.download(lambda p: None)
    model.load()
    client = model.get_embedding_client()

    query = input("Enter a test query: ")
    response = client.generate_embedding(query)
    results = get_top_chunks(response.data[0].embedding)

    print(f"\nTop {len(results)} chunks:")
    for r in results:
        print(f"\n[{r['source']}] (score: {r['score']:.4f})")
        print(r["content"][:300])

    model.unload()
