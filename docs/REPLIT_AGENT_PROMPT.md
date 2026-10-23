# Replit Agent prompt: Filing Lens chat UI

Paste everything below the line into Replit Agent after importing the repo.

---

Build a chat front end for **Filing Lens**, an existing RAG backend in this repo that answers questions about the latest 10-K filings of Raymond James, Charles Schwab, LPL Financial and Stifel, with citations, and refuses when the filings don't contain the answer.

## Hard constraints

1. **Do not modify** `api.py`, anything in `src/`, `data/`, `eval/`, `build.sh`, `start.sh`, or `requirements.txt`. The backend is finished and evaluated. If you think a backend change is needed, stop and tell me instead.
2. Create the front end only inside a new `frontend/` folder: **Vite + React + TypeScript**. `npm run build` must output to `frontend/dist`. `api.py` already serves `frontend/dist` at `/` from the same origin.
3. Call the API with **relative URLs** (`/api/...`). No CORS setup, no hard-coded hosts.
4. **No secrets in front-end code.** The user types the access code; keep it in `sessionStorage` and send it as the `X-Access-Code` header.
5. Keep dependencies light: React, a small markdown renderer (`react-markdown`), and CSS. No UI kit, no Tailwind.

## API contract (already implemented)

`GET /api/health` → `{ status: "ready" | "warming_up", chat_model, embed_model, rerank_model, access_code_required }`

`GET /api/options` → `{ strategies: string[], retrievers: string[], examples: string[], default: { strategy, retriever, rerank } }`

`POST /api/ask` with header `X-Access-Code` and body:
```json
{ "question": "string (3-500 chars)", "strategy": "table_aware", "retriever": "hybrid", "rerank": true }
```
Response:
```json
{
  "answer": "markdown text with citation markers like [1] or [2][3]",
  "refused": false,
  "refusal_reason": null,
  "citations": [{ "n": 1, "chunk_id": "SCHW-table_aware-7-0056", "ticker": "SCHW",
                  "company": "Charles Schwab", "item": "7", "heading": "RESULTS OF OPERATIONS > Segment Information",
                  "excerpt": "source text..." }],
  "companies": ["SCHW"],
  "top_score": 0.94,
  "timings": { "total": 3.9, "retrieve": 3.1, "generate": 0.8 },
  "config": "table_aware/hybrid+rerank"
}
```
Errors: `401` wrong or missing access code, `429` rate limit, `502` upstream model failure, `503` still warming up, `422` invalid input. Each has `{ "detail": "message" }`; show that message.

## Screens and behavior

**Access gate.** If `/api/health` says `access_code_required`, show a small centered card: product name, one line explaining the app, a password field, "Continue". On 401 later, clear the stored code and return here.

**Chat (main screen).**
- Header: "Filing Lens", a subtitle "Latest 10-Ks · Raymond James · Schwab · LPL · Stifel · Items 1A and 7", and a settings button.
- Empty state: one sentence on what it answers, plus the example questions from `/api/options` as clickable chips.
- Messages: user bubble on the right; assistant answer on the left rendered as markdown.
- **Citation markers** `[n]` in the answer become small clickable chips. Clicking one opens a **source panel** (right side on desktop, bottom sheet on mobile) showing company, ticker, "10-K Item {item}", the heading, and the excerpt in a monospace block that preserves table pipes. Below the answer, list all sources as chips: `[1] SCHW · Item 7 · Segment Information`.
- **Refusals** (`refused: true`): render as a distinct amber notice, not a normal answer, with the message and a one-line reason: `low_relevance` → "Nothing relevant was found in the filings." `not_in_context` → "Related passages were found, but they don't answer this question."
- Footer line under each answer, small and muted: `3.9s total · retrieve 3.1s · generate 0.8s · top match 0.94 · table_aware/hybrid+rerank`.
- While waiting: a typing indicator plus a status line that changes over time ("Searching the filings…" → "Reranking passages…" → "Writing a cited answer…"). The request takes 2–8 seconds.
- Input: multiline textarea, Enter to send, Shift+Enter for a new line, disabled while a request is in flight, 500-character limit with a counter near the limit.

**Settings popover.** Chunking strategy (fixed / section / table_aware), retriever (hybrid / dense / bm25), rerank on/off. Defaults come from `/api/options`. Add one line: "Switch settings to compare retrieval strategies."

**Status.** If `/api/health` returns `warming_up`, show a slim banner "Starting up…" and poll every 3 seconds until ready.

## Visual direction

A research tool for financial analysts, so it should feel like reading a filing: calm, dense, precise.
- Neutral off-white background with a cool tint, deep navy text, one restrained accent (deep teal) for citation chips and focus states; amber only for refusals.
- Serif for the product name and section titles, a clean sans-serif for body text, monospace for excerpts and numbers.
- Generous line height in answers, tabular numbers, no gradients, no emoji, no oversized hero.
- Supports light and dark mode via `prefers-color-scheme`.
- Responsive down to 375px wide; the source panel becomes a bottom sheet on mobile.
- Accessible: visible focus rings, buttons with labels, sufficient contrast.

## Acceptance checks

Run `bash build.sh`, then `bash start.sh`, open the app, and confirm:
1. "What were Schwab's net revenues by segment?" returns figures with at least one clickable `[n]` chip that opens the excerpt.
2. "Compare how Raymond James and Stifel describe competition for financial advisors." shows sources from both companies.
3. "What were Morgan Stanley's wealth management revenues?" shows the amber refusal notice.
4. A wrong access code shows the gate again with the server's message.
5. Switching strategy to `fixed` changes the config shown in the footer.

Tell me what you built and anything you could not complete. Do not change backend files.
