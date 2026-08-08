"""Utility: measures real cosine similarity scores for answerable/unanswerable questions."""
import sys

from foundry_local_sdk import Configuration, FoundryLocalManager

from retrieval import get_top_chunks

sys.stdout.reconfigure(encoding="utf-8")

config = Configuration(app_name="foundry_rag_demo")
FoundryLocalManager.initialize(config)
manager = FoundryLocalManager.instance

model = manager.catalog.get_model("qwen3-embedding-0.6b")
model.download(lambda p: None)
model.load()
client = model.get_embedding_client()

queries = [
    ("What is an embedding and why does it matter?", "answerable"),
    ("What is Foundry Local?", "answerable"),
    ("What are the advantages of SQLite?", "answerable"),
    ("What is Azure Machine Learning?", "answerable"),
    ("What deep learning frameworks does IBM Watson Studio support?", "answerable"),
    ("What is machine learning?", "answerable"),
    ("What are common NLP tasks?", "answerable"),
    ("How does computer vision work?", "answerable"),
    ("What's the difference between a list and a tuple in Python?", "unanswerable"),
    ("How much does Azure Machine Learning cost per month?", "unanswerable"),
    ("What is the capital of France?", "unanswerable"),
    ("What's the weather like today?", "unanswerable"),
]

for q, label in queries:
    resp = client.generate_embedding(q)
    top = get_top_chunks(resp.data[0].embedding, top_k=1)
    score = top[0]["score"] if top else None
    print(f"[{label}] {q!r} -> top_score={score:.4f}" if score is not None else f"[{label}] {q!r} -> (empty db)")

model.unload()
