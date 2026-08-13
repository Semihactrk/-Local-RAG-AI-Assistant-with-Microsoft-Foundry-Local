# Local RAG Assistant — Foundry Local

Built for the **Microsoft AI Innovators Summer Internship** program.

A fully offline, document-based Q&A assistant built with Microsoft Foundry
Local. The concrete code counterpart of the Phase 2 (project implementation)
section of the 6-week curriculum in the "Summer School Foundry Local Plan"
document.

## Architecture

```
User question
      │
      ▼
[embedding_client] ── turns the query into a vector with qwen3-embedding-0.6b
      │
      ▼
[retrieval.py] ── cosine similarity against every chunk embedding in SQLite,
                   returns the top-K chunks (db/knowledge.db)
      │
      ▼
[app.py: answer_query()] ── system prompt + context + question → chat_client
      │
      ▼
[chat_client] ── qwen2.5-1.5b-instruct (Foundry Local, local inference)
      │
      ▼
Answer (+ source filename)
```

## Setup

```powershell
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

> The Foundry Local SDK requires Python 3.11+.

## Usage order

1. Put your `.txt`/`.md` documents under `data/documents/` (a sample
   document already exists: `sample_foundry_local.md`).
2. `.venv\Scripts\python.exe src\setup_check.py` — verify the environment
   and GPU EP registration (see the "GPU note" below).
3. `.venv\Scripts\python.exe src\ingest.py` — chunk the documents, embed
   them, and write them to SQLite.
4. `.venv\Scripts\python.exe src\app.py` — a CLI Q&A loop.
   For the web interface: `.venv\Scripts\python.exe src\flask_app.py`, then
   open `http://localhost:5000` in your browser.
5. `.venv\Scripts\python.exe src\evaluate.py` — runs the question set in
   `data/test_questions.json` and produces the `docs/test_report.md` report.

## File structure

| File | Purpose |
|---|---|
| `src/setup_check.py` | Step 1: EP registration + Hello Model test |
| `src/db.py` | SQLite schema and CRUD helpers |
| `src/chunking.py` | Paragraph-based text chunking |
| `src/ingest.py` | Step 2: chunking → embedding → SQLite |
| `src/retrieval.py` | Step 3: top-K retrieval via cosine similarity |
| `src/app.py` | Step 4: `answer_query()`/`run_query()` + CLI interface |
| `src/flask_app.py` | Step 5: Flask server, `/api/ask`, `/api/conversations/<id>` JSON endpoints |
| `templates/index.html`, `static/style.css`, `static/app.js` | Step 5: web UI — sidebar (source archive + conversation history), chat bubbles, source chips, typing animation |
| `src/evaluate.py` | Step 6: automated test/report |
| `src/calibrate_threshold.py` | Re-measures `RETRIEVAL_SCORE_THRESHOLD` (re-run whenever the document set changes) |
| `src/list_models.py` | Lists every model alias in the catalog |

## Technology choices and rationale

- **Runtime:** Foundry Local Python SDK (`foundry-local-sdk`). The setup
  always calls `manager.download_and_register_eps()` — otherwise hardware
  acceleration is silently skipped and it falls back to CPU.
- **Embedding model:** `qwen3-embedding-0.6b` — available out of the box in
  the Foundry Local catalog, multilingual.
- **Chat model:** `qwen2.5-1.5b-instruct` — a safe starting point for the
  RTX 3060 Laptop GPU on this machine (~6GB VRAM estimated). Can be
  upgraded to 3B/7B based on the Step 6 performance measurements.
- **Database:** SQLite, with embeddings stored as JSON-serialized `TEXT`
  (fine for a small dataset; a BLOB/dedicated vector DB would be needed at
  larger scale).
- **Interface:** Flask + vanilla HTML/CSS/JS (not Streamlit — a more
  customizable look was wanted for presentation purposes). `flask_app.py`
  loads the models once at server startup; `/api/ask` returns JSON. The UI
  has chat bubbles, source chips, a response-time badge, and a "typing..."
  animation — tested end-to-end in the browser (see findings below).
- **Sidebar:** a two-panel layout (inspired by a Microsoft Foundry Local RAG
  example screenshot) with a **Source Archive** — the actual files under
  `data/documents/` with their size, read fresh on every page load — and
  **Conversations**, persisted in two new SQLite tables (`conversations`,
  `messages`) via `db.py`. "+ New conversation" resets the chat to the intro
  card; clicking a past conversation reloads its full message history from
  `GET /api/conversations/<id>`. A new conversation is auto-created (and
  auto-titled from the first question) on the first `POST /api/ask` call
  that doesn't include a `conversation_id`.

## GPU note (a two-stage finding, verified then corrected)

**Stage 1 — EP registration (`setup_check.py`):** On this machine, running
`download_and_register_eps()` had `CUDAExecutionProvider` registration stall
at 6% and silently fail; `WebGpuExecutionProvider` (DirectX12-based)
completed at 100% and showed as registered. From this I concluded "GPU
acceleration is working via WebGPU."

**Stage 2 — the actual model selection (discovered later):** I queried the
catalog's `.variants` list one by one for aliases like `qwen2.5-1.5b`,
`qwen3-embedding-0.6b`, `qwen2.5-7b`, `phi-3.5-mini`, and `qwen3-4b` — **none
of them offer a GPU variant, all only have `generic-cpu`**. Only the tiny
`qwen2.5-0.5b` offers both `generic-gpu` and `generic-cpu`, and the manager
automatically picks the GPU one. In other words, the models actually used in
this project — `qwen2.5-1.5b` (chat) and `qwen3-embedding-0.6b` (embedding)
— **had been running on CPU the whole time**; the "Hello Model" test in
`setup_check.py` used a different model (one that does have a GPU variant),
which misleadingly gave the impression that "GPU is working."

**Takeaway (an important addendum to Faruk's advice):** calling
`download_and_register_eps()` and seeing an EP show as "registered" isn't
enough — you also need to verify that **the specific model alias you're
using actually has a variant for that EP** (via
`manager.catalog.get_model(alias).variants`). Otherwise you might assume
"I'm using the GPU" just because an EP is registered, while actually running
on CPU — exactly what happened here. In this project, ~7-11s response time
on CPU is acceptable, so I didn't change it, but keep this in mind if you
move to a larger model (including qwen2.5-7b, which also only has a CPU
variant).

## Context window / truncation check

`MAX_CONTEXT_TOKENS_ASSUMED` in `app.py` has been **verified**: I found
`"context_length": 32768` in the `genai_config.json` inside the downloaded
`qwen2.5-1.5b-instruct-generic-cpu:4` model folder (the first draft assumed
4096 — the real value turned out to be 8x higher). `answer_query()` still
logs the estimated prompt token count on every call; if you switch to a
different model/variant, re-check that model's own `genai_config.json`.
With the small documents in this project (a handful of chunks), getting
anywhere near the 32768 limit is nearly impossible, meaning a "lost in the
middle" risk here would come from the model's own comprehension quality,
not context truncation.

## Test results

`docs/test_report.md` is generated automatically after running
`src/evaluate.py` (an answerable/unanswerable question set + response
times). Current status: **10/10 correct** across 6 documents (8 answerable
+ 2 unanswerable correctly declined, including a regression test for the
"declined-with-a-bogus-citation" bug below), response times between
0.6-10.8s.

## Real finding: repetition loop and its fix

In the first test pass, the question "What are the advantages of SQLite?"
took **103.9 seconds** — the model repeated the same sentence ("...did not
require a server setup") more than 80 times and got cut off mid-sentence
when it hit the `max_tokens` limit. This is a classic degeneration seen in
small/quantized models when `frequency_penalty` isn't set — a different
failure mode from context-window truncation (which could otherwise be
mistaken for "lost in the middle").

**Fix:** I defined `ChatClientSettings(temperature=0.3, max_tokens=400,
frequency_penalty=0.4)` in `app.py` and assigned it to `chat_client.settings`
(`foundry_local_sdk.openai.chat_client.ChatClientSettings` — verified from
the installed SDK's source). After the fix, the same question dropped to
**10.0 seconds** and the answer became coherent. `max_tokens` also acts as a
safety net guaranteeing the answer gets cut off within a reasonable time in
the worst case.

## Real finding: even the "I don't know" answer was getting mangled

Discovered during live testing in the web UI: the model consistently
mangled the system prompt's "I couldn't find this information in my
documents." sentence in free-form generation (a word-boundary glitch — a
1.5B model, even at low temperature). This shows how fragile it is to rely
on an LLM to reproduce a fixed sentence verbatim.

**Fix:** using `calibrate_threshold.py`, I measured real cosine similarity
scores for answerable vs. unanswerable questions: answerable questions
scored **0.46-0.61** on the top chunk, unanswerable ones scored **0.20-0.34**
(see the script's output). Based on that gap, I added a
`RETRIEVAL_SCORE_THRESHOLD = 0.40` threshold to `app.py`: below the
threshold, the fixed `NOT_FOUND_MESSAGE` is returned without ever calling
the LLM. Result: guaranteed correct grammar + response time dropped from
6-7s to **0.6s**. Re-measured twice more as documents were added — most
recently at 13 chunks / 6 files: answerable questions score **0.51-0.80**,
truly unrelated questions score **0.19-0.26**. The gap held throughout, so
the threshold is still valid. Re-run `calibrate_threshold.py` again any
time the document set changes meaningfully.

Important caveat found during the second re-measurement: a *topically
related but factually unanswered* question ("How much does Azure Machine
Learning cost per month?") scored **0.68** — comfortably above the
threshold. The score-threshold gate alone cannot catch this case; it's
exactly what the next finding's fix (`_looks_like_not_found()`) handles
instead. The two mechanisms are complementary, not redundant: the
threshold catches "nothing relevant retrieved," the LLM-decline detector
catches "something relevant retrieved, but it doesn't actually answer
this."

## Real finding: source citation couldn't be left to the LLM either

In the original design, `SYSTEM_PROMPT` told the model to write "Source:
filename.md" at the end of its answer — but just like the "I don't know"
sentence above, the small model applied this inconsistently in free-form
generation (sometimes skipping it, sometimes mangling it).

**Fix:** I removed the source-citation instruction from `SYSTEM_PROMPT`
entirely. Instead, `run_query()` (`app.py`) appends the `sources` list —
already known from the retrieval step — to the end of the answer
**deterministically, in code** (`"\n\nSource: ..."`). This way, the
requirement that "the model's answer includes source citation" is backed by
exact data in the code rather than the model's unreliable generation — it
shows up both in the CLI output and in the web UI's message bubble (the
UI's source chip is still there as well).

## Real finding: a "found" source citation on a declined answer

Asking "What is machine learning?" once returned "I couldn't find this
information in my documents." **together with** a bogus
"Source: IBM_deep_learning.md, Azure_microsoft_machine_learning.md" line.
Cause: the `RETRIEVAL_SCORE_THRESHOLD` gate only catches queries where
*nothing* scores above 0.40. It's still possible for a chunk to score above
the threshold (some topical overlap) while not actually answering a broad
question — in that case `run_query()` still calls the LLM, which correctly
declines per `SYSTEM_PROMPT`, but the code was appending the deterministic
source citation regardless of whether the LLM actually used that context.

**Fix:** `run_query()` now checks the LLM's own answer for the "couldn't
find this information" phrase (`_looks_like_not_found()`) before attaching
a citation. If the model declined on its own, the response is normalized to
`NOT_FOUND_MESSAGE` with an empty `sources` list, exactly like the
threshold-gated path. Verified via direct API calls: "How much does Azure
Machine Learning cost per month?" (a question none of the documents answer)
now correctly returns no sources, while "What is Azure Machine Learning?"
still cites `Azure_microsoft_machine_learning.md` as expected. Both cases
are now part of `data/test_questions.json` as a permanent regression test.

## Known limitations

- Retrieval uses brute-force cosine similarity (fine for a small N).
- Conversations are **stored and browsable** in the sidebar, but each
  question is still answered independently — prior turns in the same
  conversation are *not* fed back into the LLM's prompt. A follow-up like
  "what about that?" won't have context; every question is treated as a
  fresh RAG query against the documents. Adding real multi-turn context
  would mean including recent message history in `build_prompt()`.
- Source citation is now added deterministically from code (see the finding
  above) — it doesn't rely on the LLM.
