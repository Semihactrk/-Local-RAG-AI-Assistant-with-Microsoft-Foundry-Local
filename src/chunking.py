"""Simple paragraph-based text chunking."""

MAX_CHUNK_CHARS = 1200  # roughly 1-3 paragraphs


def split_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """
    Splits text into paragraphs on blank lines, then greedily merges
    consecutive paragraphs into chunks up to max_chars.

    If a single paragraph exceeds max_chars, it's further split on
    sentence boundaries (". ").
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""

    def flush():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for para in paragraphs:
        # Split an overly long single paragraph into sentences
        if len(para) > max_chars:
            flush()
            sentences = para.split(". ")
            sub = ""
            for i, sent in enumerate(sentences):
                piece = sent if sent.endswith(".") else sent + ("." if i < len(sentences) - 1 else "")
                if len(sub) + len(piece) + 1 > max_chars and sub:
                    chunks.append(sub.strip())
                    sub = piece
                else:
                    sub = f"{sub} {piece}".strip()
            if sub.strip():
                chunks.append(sub.strip())
            continue

        if len(current) + len(para) + 2 > max_chars and current:
            flush()
        current = f"{current}\n\n{para}".strip() if current else para

    flush()
    return chunks
