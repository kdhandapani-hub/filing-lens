# Week 2 — Financial Document Intelligence RAG

> My RAG app helps wealth-management analysts answer risk, segment and performance questions from the latest 10-K filings of four broker-dealers (Raymond James, Schwab, LPL, Stifel — SEC EDGAR, Items 1A and 7) via a chat API with ≥90% faithfulness and a ≤5s latency ceiling.

## Architecture

![Filing Lens architecture](docs/filing-lens-architecture.png)

Build pipeline, LangGraph query path, managed services, and evaluation. Components, interfaces, request sequence and design decisions: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Stack
EDGAR HTML → BeautifulSoup cleaning → 3 chunking strategies → Nebius `Qwen3-Embedding-8B` → Pinecone serverless (dense, 1 namespace per strategy) + BM25 (sparse) → hybrid + Pinecone-hosted rerank (`bge-reranker-v2-m3`) → LangGraph (retrieve → grade → answer | refuse) → LangSmith tracing + evals.

## Day 1: build the indexes

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # fill NEBIUS_API_KEY, PINECONE_API_KEY, LANGSMITH_API_KEY, SEC_USER_AGENT

python -m src.download     # 4 latest 10-Ks -> data/raw/ + manifest.json
python -m src.ingest       # clean + extract Item 1A / Item 7 -> data/processed/<TICKER>.json
python -m src.index        # Pinecone index (auto-created) w/ 3 namespaces + BM25 corpora
python -m src.smoke_test   # dense top-3 vs reranked top-3 per strategy
```

### What to check after each step
| Step | Healthy output |
|---|---|
| download | 4 files, each roughly 1–10 MB |
| ingest | Each ticker shows both items with tens of thousands of chars, plus some tables. A `WARN` means that filing's headings didn't match; send me the output. |
| index | `fixed` chunks ~500 tokens; `table_aware` reports >0 tables; final stats show 3 namespaces |
| smoke_test | Interest-rate query hits RJF Item 1A; segment query hits SCHW Item 7 tables in `table_aware` |

## Day 2: hybrid retrieval + LangGraph

```bash
# .env: set NEBIUS_CHAT_MODEL (from the Nebius models page)
python -m src.ask --demo                                   # answer, comparison and refusal paths
python -m src.ask "Your question" --strategy section --retriever dense --no-rerank
```

Flow (`src/graph.py`): `plan → retrieve → grade → generate | refuse`
- **plan**: detects companies; comparison questions retrieve per company (Pinecone metadata filter) so every named firm is represented.
- **retrieve** (`src/retrieval.py`): dense (Pinecone) + BM25, fused with Reciprocal Rank Fusion, then Pinecone rerank.
- **grade**: refuses if the best rerank score < `RELEVANCE_THRESHOLD` (nothing relevant retrieved).
- **generate**: answers only from numbered context with `[n]` citations; returns `NOT_FOUND` → refuse when the context doesn't answer the question.
- Every run is traced in LangSmith with strategy/retriever/rerank tags; per-node timings returned for latency reporting.

## Day 3: evaluation

```bash
python -m src.draft_expected                  # drafts candidate answers + source chunks -> eval/expected_review.md
python -m src.draft_expected --promote N01,N02   # after verifying each candidate against its source
python -m src.run_eval --limit 3              # dry run (3 questions x 8 configs)
python -m src.run_eval                        # core matrix: 8 configs; add --full for all 18
```

Each configuration is a LangSmith experiment on the same dataset, so they can be compared side by side.
Metrics: retrieval_hit (expected company + Item retrieved), refusal_correct, faithfulness (LLM judge, claims supported by context), correctness (LLM judge vs verified expected answer), latency p50/p95, share under 5s.
Results: `eval/results/eval_summary.md`, `eval/results/eval_rows.csv`. Analysis and findings: **[docs/EVALUATION.md](docs/EVALUATION.md)**.

Core matrix: `fixed`, `section`, `table_aware` with hybrid+rerank (chunking comparison), plus `table_aware` with dense/bm25/hybrid, rerank on/off (retrieval ablation).
Judge: an OpenAI model (`JUDGE_MODEL`, default `gpt-4.1-mini`) grades faithfulness and correctness, so answers from DeepSeek are not graded by the same model family. Expected answers are human-verified.

## API + hosted UI

```bash
uvicorn api:app --reload --port 8000     # docs at http://localhost:8000/docs
```
`POST /api/ask` returns the answer, citations with source excerpts, refusal reason, timings and config. Set `APP_ACCESS_CODE` to require an access code (sent as `X-Access-Code`); a per-IP rate limit caps spend.
Hosting: one Replit app serves the API and the vibe-coded front end. Setup: [docs/REPLIT_SETUP.md](docs/REPLIT_SETUP.md). Agent prompt: [docs/REPLIT_AGENT_PROMPT.md](docs/REPLIT_AGENT_PROMPT.md).

## Local chat UI (Streamlit)

```bash
streamlit run app.py
```
Sidebar switches chunking strategy, retriever and rerank live; each answer shows cited source excerpts, refusal reason, and latency. Set `APP_PASSWORD` to require an access code.

Local demo and fallback for the hosted UI.

## Chunking strategies
| Strategy | How | Hypothesis |
|---|---|---|
| fixed | 512 tok / 64 overlap, structure ignored | Baseline; splits mid-thought and mid-table |
| section | Split on 10-K headings, ≤800 tok, heading prefixed | Better coherence on narrative risk questions |
| table_aware | section + each data table as its own chunk with company/item/heading context | Best on numeric questions |

## Iteration log
Record every change and its effect here; it becomes the "iterations + learnings" section of the Google Doc.

- Day 1: Synthetic test showed Table of Contents entries matched as section starts → now picks the last qualifying match.
- Day 1: Swapped Chroma for Pinecone serverless (namespaces = strategies) and a local cross-encoder for Pinecone-hosted reranking — removes the PyTorch dependency.
- Day 1 v1 baseline (`eval/results/smoke_v1_baseline.txt`): reranking fixed cross-company noise (LPL query: dense top-3 had SF/RJF chunks, reranked top-3 all LPLA). `table_aware` won the numeric query (Schwab segment table, rerank 0.97). Weak: RJF interest-rate-risk query scored 0.05–0.2 after rerank in section/table_aware.
- Day 1 v1 root causes: (1) sentence-style bold/italic risk-factor titles were not detected as headings, so `section` only split at ALL-CAPS categories -> oversized mixed-topic chunks cut mid-sentence; (2) page footers (`- 39 -`) and running headers leaked into chunks; (3) table chunks crowd prose for narrative queries in `table_aware`.
- Day 1 v2 fixes: heading = block >=85% bold/italic (any length <=400, periods allowed); ALL-CAPS headings tracked as categories, chunk prefix is `[CATEGORY > risk title]`; drop page numbers + lines repeated >=5 times; section boundaries chosen structurally (a real Item span never contains another `Item N` heading, a TOC span always does). (3) left for hybrid retrieval to address on Day 2.
- Day 2 model choice: Llama-3.3-70B-Instruct has no public (pay-per-token) endpoint on Nebius; chose DeepSeek V4.1 Flash (~139 tok/s, $0.30/$1.20 per 1M tokens). Day 1 embedding cost for all index builds: 0.65M tokens, < $0.01.
- Day 2 demo v1 (`eval/results/demo_v1.txt`): Schwab segment question answered from the exact Segment Information table (rerank 0.94); RJF vs Stifel comparison grounded in both firms via per-company retrieval. Morgan Stanley question passed the retrieval gate (rerank 0.86: wealth-management passages from other firms look relevant) but the generation gate returned NOT_FOUND, which shows why two refusal gates are needed. Stock price target refused correctly.
- Day 2 demo v1 issues: (1) Q1 returned empty text and Q3 was truncated at max_tokens=600; (2) ~12s end-to-end vs <=5s target, with retrieval at 5-10s; (3) table figures lacked "(in millions)" because the caption sits outside the table.
- Day 2 v2 fixes: max_tokens 1500 + retry once on empty output + strip <think> blocks + record finish_reason/token usage; answers capped at 150 words; per-stage retrieval timings (embed / pinecone / bm25 / rerank) printed and traced in LangSmith; client warm-up so timings exclude one-off setup.
- Day 2 demo v2 (`eval/results/demo_v2.txt`): stage timings showed (a) embedding cold start 7.7-8.4s on the first two calls, then 0.3-0.9s warm; (b) generation 8-12s because the model emits hidden reasoning tokens (601 of 808 output tokens on Q1) even though the catalog lists Reasoning as "Not available"; this also explains v1's empty answer (600-token limit consumed by reasoning). Pinecone 0.07-0.33s, BM25 ~2ms, rerank 0.4-1.4s. Refusals already 1.8-2.3s end to end. "(in millions)" now stated.
- Day 2 v3 fixes: warm-up embedding call; configurable `NEBIUS_CHAT_EXTRA_BODY` / `NEBIUS_REASONING_EFFORT` plus `src/check_reasoning.py` to find the setting that disables hidden reasoning.
- Day 2 v4 (`eval/results/demo_v4.txt`): `src/check_reasoning.py` tested 4 disable switches; only `chat_template_kwargs: {thinking: false}` worked on Nebius DeepSeek V4.1 Flash (reasoning 74 -> 0 tokens); `enable_thinking`, `thinking.type=disabled` and `reasoning_effort=low` had no effect. Result: all 5 demo questions answered or refused correctly with 0 reasoning tokens; end-to-end 1.9-6.4s (4 of 5 under 5s) vs 6.5-14.5s in v1. Remaining latency is the cross-region embedding call (0.7-2.2s; Nebius embeddings run in eu-north1, Pinecone in us-east-1).
- Day 3 dry run (3 comparison questions x 8 configs): `section` beat `fixed` on retrieval hit (1.0 vs 0.83) and faithfulness (0.89 vs 0.84). C02 (RJF vs LPL net revenues) was falsely refused only in configs using BM25 (table_aware hybrid+rr, bm25+rr, bm25); dense+rr answered it.
- C02 diagnosis: hypothesis 1 (plural mismatch "revenues" vs "revenue") tested with plural folding: still refused (`eval/results/c02_before.txt`, `c02_after.txt`), so rejected. Retrieved chunks showed the real cause: BM25 matched question framing ("which firm reported ... most recent") to an RJF regulatory risk factor ("financial services firm...") and a generic LPL MD&A intro, and each company's search carried the other company's name.
- Day 3 fixes: BM25 stopwords incl. question-framing words; comparison questions now send each company a focused sub-query with the other firm's name removed (`focus_query`), e.g. "Raymond James ... net revenues ... fiscal year". Plural folding kept (harmless, helps advisor/advisors).
- C02 after fixes: BM25-only still misses the consolidated revenue tables (numbers-heavy, few matching words) but rerank scores rose 0.21 -> 0.66 and it now lands in Results of Operations; hybrid answers it (`eval/results/c02_hybrid_v2.txt`) -> ablation finding: keyword search alone fails table lookups, dense recovers them. New issue: the answer named LPL as higher while admitting RJF's company-wide total was not in context (only segment tables retrieved). Fix: prompt rule to compare only when both figures are present for comparable periods, and to flag differing fiscal year-ends (RJF Sep 30, LPL Dec 31).
- C02 root cause confirmed: RJF's consolidated table exists (`RJF-table_aware-7-0036`, EXECUTIVE OVERVIEW > Summary results of operations) but RJF has 6 tables with a "Net revenues" row (consolidated + 5 segments); with 3 slots per company the segment tables outranked it -> ranking miss, not a chunking bug. Fix: comparison context budget of ~10 chunks shared across firms (2 firms: 5 each; 4 firms: 3 each) instead of a fixed 3 per firm.
- Eval judge: switched from the answer model (DeepSeek) to an independent OpenAI judge to avoid self-grading bias; judge identity recorded in each LangSmith experiment's metadata and in the summary.
- Comparison latency: per-firm focused queries doubled embedding calls (C02 took 7.2s). Per-firm retrieval now runs in parallel threads, with context propagated so LangSmith spans and stage timings still attach to the request.
- Day 3 F01 diagnosis: "principal interest rate risks" refused in section and table_aware. The content is indexed (`1A-0012` "We are exposed to market risk, including interest rate risk"; Item 7 Risk Management > Market risk) but ranks 6th dense, outside BM25 top 10, 11th after rerank, even for a plain query. Cause: one long multi-topic risk factor (rates, equity, credit, FX) vs rate tables that score higher but don't describe risk. Generation correctly refused. Left as a documented failure.
- Day 3 ground truth: system-drafted expected answers checked claim by claim against their source passages; unverifiable claims removed; F01, C04 (Schwab's chunks fell below the relevance threshold) and N04 (Institutional Group table not retrieved) written from filing text.
- Day 3 full eval (22 Qs x 8 configs, `docs/EVALUATION.md`): structured chunking beats fixed on correctness (0.72 vs 0.56); table_aware wins numeric (0.92 vs 0.33 fixed), section wins cross-company (0.88), fixed wins narrative factual (0.67 vs 0.50 table_aware: tables crowd prose). Rerank adds 0.11-0.17 correctness for every retriever. All 32 unanswerable cases refused. Default chosen: table_aware/hybrid+rerank (refusal 0.95, faithfulness 0.92, correctness 0.72, p50 2.65s).
