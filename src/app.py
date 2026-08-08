import sys

from foundry_local_sdk import Configuration, FoundryLocalManager
from foundry_local_sdk.openai.chat_client import ChatClientSettings

from retrieval import get_top_chunks

sys.stdout.reconfigure(encoding="utf-8")

CHAT_SETTINGS = ChatClientSettings(
    temperature=0.3,
    max_tokens=400,
    frequency_penalty=0.4,
)

CHAT_MODEL_ALIAS = "qwen2.5-1.5b"
EMBEDDING_MODEL_ALIAS = "qwen3-embedding-0.6b"

MAX_CONTEXT_TOKENS_ASSUMED = 32768

RETRIEVAL_SCORE_THRESHOLD = 0.40
NOT_FOUND_MESSAGE = "I couldn't find this information in my documents."

SYSTEM_PROMPT = (
    "Do not go beyond the CONTEXT provided to you. Answer using only the "
    "information in the text passages given below. If the answer isn't in "
    "the context, say 'I couldn't find this information in my documents.' "
    "and do not make anything up."
)


def _looks_like_not_found(text: str) -> bool:
    """Heuristic: did the model decline to answer on its own (per SYSTEM_PROMPT),
    even though retrieval score passed the threshold? Matches on the core phrase
    it's instructed to use, tolerating minor rewording/punctuation differences."""
    lowered = text.lower()
    return "couldn't find this information" in lowered or "could not find this information" in lowered


def estimate_tokens(text: str) -> int:
    """Rough estimate: ~4 characters = 1 token (a stand-in for a real tokenizer)."""
    return max(1, len(text) // 4)


def build_prompt(query: str, chunks: list[dict]) -> str:
    context_block = "\n\n---\n\n".join(
        f"[Source: {c['source']}]\n{c['content']}" for c in chunks
    )
    return f"CONTEXT:\n{context_block}\n\nQUESTION: {query}"


def run_query(query: str, embedding_client, chat_client, log_tokens: bool = True) -> dict:
    """
    A more detailed version of answer_query() -- also returns which sources
    were used and whether the LLM call was skipped. Use this in UIs (Flask,
    CLI) that need to display sources/scores.

    Returns: {"answer": str, "sources": list[str], "chunks": list[dict], "skipped_llm": bool}
    """
    # 1. Embed the query and fetch the most relevant chunks.
    emb_response = embedding_client.generate_embedding(query)
    chunks = get_top_chunks(emb_response.data[0].embedding)

    if not chunks:
        return {
            "answer": "There are no documents in the database yet. Run src/ingest.py first.",
            "sources": [], "chunks": [], "skipped_llm": True,
        }

    if chunks[0]["score"] < RETRIEVAL_SCORE_THRESHOLD:
        if log_tokens:
            print(f"[debug] top_score={chunks[0]['score']:.4f} < threshold ({RETRIEVAL_SCORE_THRESHOLD}) "
                  f"-> returning the fixed message without calling the LLM.")
        return {"answer": NOT_FOUND_MESSAGE, "sources": [], "chunks": chunks, "skipped_llm": True}

    # 2. Build the prompt and log it for token/truncation checks.
    user_content = build_prompt(query, chunks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    if log_tokens:
        full_text = SYSTEM_PROMPT + user_content
        est = estimate_tokens(full_text)
        print(f"[debug] estimated prompt token count: ~{est} "
              f"(assumed limit: {MAX_CONTEXT_TOKENS_ASSUMED})")
        if est > MAX_CONTEXT_TOKENS_ASSUMED:
            print("[WARNING] Estimated token count exceeds the assumed limit -- "
                  "the answer may get truncated. Consider retrieving fewer chunks.")
        for c in chunks:
            print(f"[debug] retrieved: {c['source']} (score={c['score']:.4f})")

    # 3. Get the answer from the LLM.
    response = chat_client.complete_chat(messages)

    # Show real token usage if available (may not exist depending on SDK
    # version -- check safely).
    usage = getattr(response, "usage", None)
    if log_tokens and usage is not None:
        print(f"[debug] actual token usage: {usage}")

    raw_answer = response.choices[0].message.content.rstrip()

    if _looks_like_not_found(raw_answer):
        if log_tokens:
            print("[debug] LLM declined on its own (retrieved chunks weren't actually "
                  "relevant) -> dropping the source citation.")
        return {"answer": NOT_FOUND_MESSAGE, "sources": [], "chunks": chunks, "skipped_llm": False}

    sources = list(dict.fromkeys(c["source"] for c in chunks))  # preserve order, dedupe

    answer_text = raw_answer
    if sources:
        answer_text += f"\n\nSource: {', '.join(sources)}"

    return {
        "answer": answer_text,
        "sources": sources,
        "chunks": chunks,
        "skipped_llm": False,
    }


def answer_query(query: str, embedding_client, chat_client, log_tokens: bool = True) -> str:
    """For backward compatibility: returns just the answer text."""
    return run_query(query, embedding_client, chat_client, log_tokens)["answer"]


def main():
    config = Configuration(app_name="foundry_rag_demo")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance

    print(f"Loading embedding model: {EMBEDDING_MODEL_ALIAS}")
    embedding_model = manager.catalog.get_model(EMBEDDING_MODEL_ALIAS)
    embedding_model.download(lambda p: None)
    embedding_model.load()
    embedding_client = embedding_model.get_embedding_client()

    print(f"Loading chat model: {CHAT_MODEL_ALIAS}")
    chat_model = manager.catalog.get_model(CHAT_MODEL_ALIAS)
    chat_model.download(
        lambda p: print(f"\rDownloading model: {p:.2f}%", end="", flush=True)
    )
    print()
    chat_model.load()
    chat_client = chat_model.get_chat_client()
    chat_client.settings = CHAT_SETTINGS

    print("\nReady. Type 'exit' to quit.\n")
    try:
        while True:
            query = input("Question: ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit", "q"):
                break
            answer = answer_query(query, embedding_client, chat_client)
            print(f"\nAssistant: {answer}\n")
    finally:
        embedding_model.unload()
        chat_model.unload()
        print("Models unloaded.")


if __name__ == "__main__":
    main()
