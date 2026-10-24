# Filing Lens Evaluation

22 questions × 8 configurations = 176 graded answers, logged as LangSmith experiments.
Answers from DeepSeek V4.1 Flash; faithfulness and correctness graded by an independent judge (`gpt-4.1-mini`).

## Question set

| Category | Count | Example |
|---|---|---|
| Factual (narrative) | 6 | How does LPL describe the impact of interest rates on its client cash revenue? |
| Numeric / table | 6 | What were Schwab's net interest revenue and asset management fees? |
| Cross-company | 4 | Which firm reported higher net revenues: Raymond James or LPL? |
| Exact term | 2 | What does Raymond James say about the Bank Deposit Program? |
| Unanswerable | 4 | What were Morgan Stanley's wealth management revenues? |

**Ground truth.** Expected answers were drafted by the system from its own retrieved passages, then every claim was checked against the source text; claims not visible in the source were removed. Three answers (F01, C04, N04) were written or corrected from the filing text because retrieval had missed the needed passage.

## Metrics

| Metric | What it measures |
|---|---|
| Retrieval hit | Share of expected companies whose expected 10-K Item appears in the retrieved chunks |
| Refusal correct | Refused exactly when the question is unanswerable |
| Faithfulness | Judge: share of the answer's claims supported by the retrieved context |
| Correctness | Judge vs the verified expected answer: 1 all key facts, 0.5 some, 0 missing or contradicted |
| Latency | End-to-end seconds per question (p50, p95, share ≤ 5s) |

## Results

| Config | Retrieval hit | Refusal correct | Faithfulness | Correctness | p50 (s) | p95 (s) | ≤5s |
|---|---|---|---|---|---|---|---|
| fixed / hybrid + rerank | 0.92 | 0.86 | 0.89 | 0.56 | 6.78* | 18.39* | 32%* |
| section / hybrid + rerank | **0.99** | 0.91 | 0.89 | **0.72** | 2.58 | **4.74** | 95% |
| **table_aware / hybrid + rerank** | 0.93 | **0.95** | **0.92** | **0.72** | 2.65 | 6.54 | 86% |
| table_aware / dense + rerank | 0.90 | 0.95 | 0.88 | 0.67 | 2.86 | 4.48 | 95% |
| table_aware / dense | 0.92 | 0.86 | 0.91 | 0.56 | 2.12 | 3.68 | 100% |
| table_aware / BM25 + rerank | 0.93 | 0.86 | 0.89 | 0.56 | 2.64 | 4.38 | 100% |
| table_aware / BM25 | 1.00 | 0.86 | 0.93 | 0.42 | 2.11 | 3.79 | 100% |
| table_aware / hybrid | 0.92 | 0.82 | 0.93 | 0.56 | 1.76 | 3.69 | 100% |

\* `fixed` ran first and absorbed embedding-endpoint warm-up. Re-run on its own (`run_eval --only "fixed/hybrid+rr"`) it averaged **2.74s** with 86% under 5s, in line with the other configs.

**Run-to-run variance.** The same re-run scored correctness 0.53 (vs 0.56) and faithfulness 0.95 (vs 0.89). Differences under about 0.05 between configs are within noise; the findings below rely on larger gaps.

### Correctness by question type

| Config | Numeric / table | Cross-company | Factual | Exact term |
|---|---|---|---|---|
| fixed / hybrid + rerank | 0.33 | 0.62 | **0.67** | 0.75 |
| section / hybrid + rerank | 0.75 | **0.88** | 0.58 | 0.75 |
| table_aware / hybrid + rerank | **0.92** | 0.75 | 0.50 | 0.75 |

## Findings

1. **Structure-aware chunking beats fixed windows.** `section` and `table_aware` both reach 0.72 correctness against 0.56 for `fixed`.
2. **Each structured strategy wins where it was designed to.** `table_aware` is best on numeric questions (0.92 vs 0.33 for fixed): keeping a table intact keeps each figure next to its row and column labels. `section` is best on cross-company comparisons (0.88).
3. **Tables crowd out prose on narrative questions.** On factual risk questions `table_aware` scores lowest (0.50) and `fixed` highest (0.67). Rate tables outrank the risk-factor prose that actually describes the risk (see F01).
4. **Reranking is the largest single lever.** Turning it on raises correctness by 0.11–0.17 for every retriever and raises refusal accuracy from 0.82 to 0.95 for hybrid, for about 1s of latency. Without it, N03 and N05 are falsely refused because the right KPI table isn't in the top 5 by fusion alone.
5. **Hybrid beats either retriever alone** (0.72 vs 0.67 dense and 0.56 BM25). BM25 alone has the weakest correctness (0.42): numbers-heavy tables share few words with the question.
6. **Every unanswerable question was refused, in all 8 configs** (32 of 32). The two refusal gates hold: the Morgan Stanley question scores 0.86 on rerank and is still refused at generation.
7. **The main error mode is false refusal, not hallucination.** For the default config the only wrong refusal is F01; for other configs it is 3–5 questions (F05, N03, N05, X01). Faithfulness stays at 0.88–0.93 everywhere.

## Failure analysis (default: table_aware / hybrid + rerank)

| ID | Score | What happened | Root cause |
|---|---|---|---|
| F01 | refused | "Principal interest rate risks" refused in every structured config | The risk factor is one long multi-topic chunk (rates, equity, credit, FX) that ranks 11th after rerank, behind rate tables that don't describe risk |
| N04 | 0.5 | Gave Global Wealth Management, said Institutional Group wasn't in context | The Institutional Group table exists (`SF-table_aware-7-0066`) but didn't reach the top 5; its heading was also mis-filed under "INCOME BEFORE INCOME TAXES" |
| F03, F04, F06 | 0.5 | Correct but incomplete or extra detail | Partial overlap with expected key facts |
| C03, C04 | 0.5 | Missed one firm's detail | Per-firm budget of 3 chunks for 4-firm questions; low-scoring firms drop below the relevance threshold |
| X02 | 0.5 in all configs | Accurate, cut short before the final fact | 150-word answer cap |

**Retrieval misses the model handled honestly.** In `section`, N01 retrieved only the Asset Management segment and the answer said the consolidated figure wasn't in context. The same happened for Stifel's Institutional Group in N04. The answers are incomplete, but they don't invent anything.

## Judge limitation

Faithfulness counts statements about absence ("the segment margin is not disclosed in the context") as unsupported claims. N05 is fully correct (correctness 1.0) but scores 0.5 faithfulness for this reason. Reported faithfulness is therefore a slight underestimate for answers that flag missing data.

## Threshold re-run (after live testing)

On the live app, "What does LPL say about cybersecurity risk?" was refused at the retrieval gate. The content was indexed and retrieved: `LPLA-table_aware-1A-0029` ("Our information technology systems may be vulnerable to security risks") ranked 2nd and `1A-0031` ("A cyber-attack or other security breach…") 5th. But the best rerank score was 0.11, under the 0.15 threshold, because the filing's wording ("security risks", "cyber-attack") differs from the question's ("cybersecurity risk").

The default configuration was re-run on the same 22 questions with `RELEVANCE_THRESHOLD=0.05` (`run_eval --only "table_aware/hybrid+rr"`; results in `eval/results/eval_summary_table_aware_hybrid_rr.md`):

| Threshold | Retrieval hit | Refusal correct | Faithfulness | Correctness |
|---|---|---|---|---|
| 0.15 | 0.93 | 0.95 | 0.92 | 0.72 |
| **0.05** | 0.94 | 0.955 | 0.917 | **0.81** |

Correctness rose by 0.09, above the ±0.05 run-to-run noise; refusals and faithfulness didn't move. The generation gate still refuses all four unanswerable questions, so the retrieval gate can be looser. Latency in this run (4.9s average) isn't comparable: the eval sends 4 questions at once, which is exactly the concurrent-embedding pattern the shared Nebius endpoint slows down on.

**0.05 is now the default** (`src/config.py`).

## Decisions

- **Default: `table_aware / hybrid + rerank`.** It has the best refusal accuracy (0.95) and faithfulness (0.92, meeting the ≥ 0.90 target) and ties for best correctness. With the relevance threshold lowered to 0.05, its correctness is 0.81.
- **Latency:** p50 2.65s meets the ≤ 5s target; p95 6.54s does not, driven by comparison questions. Per-firm retrieval now runs in parallel (shipped after this run).

## Next iterations

| Change | Expected effect |
|---|---|
| Route by question type: numeric → `table_aware`, narrative and comparison → `section` | Combines the strengths in findings 2–3 |
| Guarantee a prose / table mix in the top 5 | Fixes F01-style misses without losing numeric accuracy |
| Split long multi-topic risk factors; embed risk-factor titles separately | Makes "market risk, including interest rate risk" findable |
| Per-firm minimum after the relevance threshold | Stops a firm silently disappearing from 4-firm answers |
| Judge prompt: ignore statements about what the context lacks | Removes the faithfulness underestimate |
| Calibrate the relevance threshold per question type, or replace it with a rank-based gate | Reranker scores vary with wording; a fixed cutoff refused a valid question |
| Passage-level retrieval metric (expected chunk IDs) | `retrieval_hit` at company + Item level is too coarse: BM25 scores 1.0 on it with the worst correctness |
