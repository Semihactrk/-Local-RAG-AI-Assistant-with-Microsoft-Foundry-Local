import sys
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from foundry_local_sdk import Configuration, FoundryLocalManager

from app import CHAT_MODEL_ALIAS, CHAT_SETTINGS, EMBEDDING_MODEL_ALIAS, run_query
from db import add_message, create_conversation, get_connection, get_conversation_messages, list_conversations

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "data" / "documents"
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


def list_documents():
    """Documents shown in the sidebar's Source Archive (name + human-readable size)."""
    docs = []
    for path in sorted(DOCS_DIR.glob("*")):
        if path.suffix.lower() in (".txt", ".md") and path.is_file():
            size_kb = path.stat().st_size / 1024
            docs.append({"name": path.name, "size": f"{size_kb:.1f} KB"})
    return docs


@app.route("/")
def index():
    conn = get_connection()
    return render_template(
        "index.html",
        chat_model=CHAT_MODEL_ALIAS,
        embedding_model=EMBEDDING_MODEL_ALIAS,
        documents=list_documents(),
        conversations=list_conversations(conn),
    )


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    conversation_id = data.get("conversation_id")
    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400

    if _state["embedding_client"] is None or _state["chat_client"] is None:
        return jsonify({"error": "Models aren't loaded yet, try again shortly."}), 503

    conn = get_connection()
    is_new_conversation = not conversation_id
    title = None
    if is_new_conversation:
        title = question if len(question) <= 60 else question[:57] + "..."
        conversation_id = create_conversation(conn, title)

    add_message(conn, conversation_id, "user", question)

    start = time.time()
    result = run_query(question, _state["embedding_client"], _state["chat_client"], log_tokens=False)
    elapsed = time.time() - start

    add_message(
        conn, conversation_id, "assistant", result["answer"],
        sources=result["sources"], seconds=round(elapsed, 2),
    )

    return jsonify({
        "answer": result["answer"],
        "sources": result["sources"],
        "skipped_llm": result["skipped_llm"],
        "seconds": round(elapsed, 2),
        "conversation_id": conversation_id,
        "is_new_conversation": is_new_conversation,
        "title": title,
    })


@app.route("/api/conversations/<int:conversation_id>")
def get_conversation(conversation_id):
    conn = get_connection()
    return jsonify({"id": conversation_id, "messages": get_conversation_messages(conn, conversation_id)})


if __name__ == "__main__":
    load_models()
    app.run(host="127.0.0.1", port=5000, debug=False)
