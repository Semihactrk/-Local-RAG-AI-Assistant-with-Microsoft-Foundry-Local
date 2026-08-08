"""
Step 6: Functional test / evaluation harness.

Runs the question list in test_questions.json, records the answer and
response time for each, and writes the result to a markdown report.

test_questions.json format:
[
  {"question": "...", "expected": "answerable" | "unanswerable"},
  ...
]

Run:
    .venv\\Scripts\\python.exe src\\evaluate.py
"""

import json
import sys
import time
from pathlib import Path

from foundry_local_sdk import Configuration, FoundryLocalManager

from app import CHAT_MODEL_ALIAS, CHAT_SETTINGS, EMBEDDING_MODEL_ALIAS, answer_query

sys.stdout.reconfigure(encoding="utf-8")

QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "test_questions.json"
REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "test_report.md"


def load_questions():
    if not QUESTIONS_PATH.exists():
        default = [
            {"question": "What is Foundry Local?", "expected": "answerable"},
            {"question": "What does RAG stand for?", "expected": "answerable"},
            {"question": "What are the advantages of SQLite?", "expected": "answerable"},
            {"question": "What is the capital of France?", "expected": "unanswerable"},
        ]
        QUESTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        QUESTIONS_PATH.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[info] {QUESTIONS_PATH} not found, created a sample question set. "
              f"Edit it with your own questions and re-run.")
    return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))


def main():
    questions = load_questions()

    config = Configuration(app_name="foundry_rag_demo")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance

    embedding_model = manager.catalog.get_model(EMBEDDING_MODEL_ALIAS)
    embedding_model.download(lambda p: None)
    embedding_model.load()
    embedding_client = embedding_model.get_embedding_client()

    chat_model = manager.catalog.get_model(CHAT_MODEL_ALIAS)
    chat_model.download(lambda p: None)
    chat_model.load()
    chat_client = chat_model.get_chat_client()
    chat_client.settings = CHAT_SETTINGS

    results = []
    for q in questions:
        start = time.time()
        answer = answer_query(q["question"], embedding_client, chat_client, log_tokens=False)
        elapsed = time.time() - start
        results.append({**q, "answer": answer, "seconds": round(elapsed, 2)})
        print(f"[{elapsed:.1f}s] {q['question']} -> {answer[:80]}...")

    embedding_model.unload()
    chat_model.unload()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Test Report\n", f"Model: {CHAT_MODEL_ALIAS} / {EMBEDDING_MODEL_ALIAS}\n"]
    for r in results:
        lines.append(f"## {r['question']}")
        lines.append(f"- Expected: {r['expected']}")
        lines.append(f"- Time: {r['seconds']}s")
        lines.append(f"- Answer: {r['answer']}\n")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
