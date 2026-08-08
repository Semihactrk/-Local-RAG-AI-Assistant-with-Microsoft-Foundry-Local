import sys
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from foundry_local_sdk import Configuration, FoundryLocalManager

from app import CHAT_MODEL_ALIAS, CHAT_SETTINGS, EMBEDDING_MODEL_ALIAS, run_query

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)

# Global state: populated once at server startup (see load_models()).
_state = {"embedding_client": None, "chat_client": None}


def load_models():
    print(f"Loading embedding model: {EMBEDDING_MODEL_ALIAS}")
    config = Configuration(app_name="foundry_rag_demo")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance

    embedding_model = manager.catalog.get_model(EMBEDDING_MODEL_ALIAS)
    embedding_model.download(lambda p: None)
    embedding_model.load()
    _state["embedding_client"] = embedding_model.get_embedding_client()

    print(f"Loading chat model: {CHAT_MODEL_ALIAS}")
    chat_model = manager.catalog.get_model(CHAT_MODEL_ALIAS)
    chat_model.download(
        lambda p: print(f"\rDownloading model: {p:.2f}%", end="", flush=True)
    )
    print()
    chat_model.load()
    chat_client = chat_model.get_chat_client()
    chat_client.settings = CHAT_SETTINGS
    _state["chat_client"] = chat_client

    print("Models ready.")


@app.route("/")
def index():
    return render_template(
        "index.html",
        chat_model=CHAT_MODEL_ALIAS,
        embedding_model=EMBEDDING_MODEL_ALIAS,
    )


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400

    if _state["embedding_client"] is None or _state["chat_client"] is None:
        return jsonify({"error": "Models aren't loaded yet, try again shortly."}), 503

    start = time.time()
    result = run_query(question, _state["embedding_client"], _state["chat_client"], log_tokens=False)
    elapsed = time.time() - start

    return jsonify({
        "answer": result["answer"],
        "sources": result["sources"],
        "skipped_llm": result["skipped_llm"],
        "seconds": round(elapsed, 2),
    })


if __name__ == "__main__":
    load_models()
    app.run(host="127.0.0.1", port=5000, debug=False)
