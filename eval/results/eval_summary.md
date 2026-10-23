# Evaluation summary

22 questions × 8 configurations. Judge: openai:gpt-4.1-mini. Scores are means over the questions where the metric applies.

## Overall

| Config | Retrieval hit | Refusal correct | Faithfulness | Correctness | Latency p50 (s) | p95 (s) | ≤5s |
|---|---|---|---|---|---|---|---|
| fixed/hybrid+rr | 0.92 | 0.86 | 0.89 | 0.56 | 6.78 | 18.39 | 0.32 |
| section/hybrid+rr | 0.99 | 0.91 | 0.89 | 0.72 | 2.58 | 4.74 | 0.95 |
| table_aware/hybrid+rr | 0.93 | 0.95 | 0.92 | 0.72 | 2.65 | 6.54 | 0.86 |
| table_aware/dense+rr | 0.90 | 0.95 | 0.88 | 0.67 | 2.86 | 4.48 | 0.95 |
| table_aware/dense | 0.92 | 0.86 | 0.91 | 0.56 | 2.12 | 3.68 | 1.00 |
| table_aware/bm25+rr | 0.93 | 0.86 | 0.89 | 0.56 | 2.64 | 4.38 | 1.00 |
| table_aware/bm25 | 1.00 | 0.86 | 0.93 | 0.42 | 2.11 | 3.79 | 1.00 |
| table_aware/hybrid | 0.92 | 0.82 | 0.93 | 0.56 | 1.76 | 3.69 | 1.00 |

## retrieval_hit by question category

| Config | cross_company | exact_term | factual | numeric_table | unanswerable |
|---|---|---|---|---|---|
| fixed/hybrid+rr | 0.88 | 1.00 | 0.83 | 1.00 | – |
| section/hybrid+rr | 0.94 | 1.00 | 1.00 | 1.00 | – |
| table_aware/hybrid+rr | 0.94 | 1.00 | 0.83 | 1.00 | – |
| table_aware/dense+rr | 0.81 | 1.00 | 0.83 | 1.00 | – |
| table_aware/dense | 0.88 | 1.00 | 0.83 | 1.00 | – |
| table_aware/bm25+rr | 0.94 | 1.00 | 0.83 | 1.00 | – |
| table_aware/bm25 | 1.00 | 1.00 | 1.00 | 1.00 | – |
| table_aware/hybrid | 0.88 | 1.00 | 0.83 | 1.00 | – |

## faithfulness by question category

| Config | cross_company | exact_term | factual | numeric_table | unanswerable |
|---|---|---|---|---|---|
| fixed/hybrid+rr | 0.80 | 1.00 | 0.97 | 0.83 | – |
| section/hybrid+rr | 0.90 | 1.00 | 0.91 | 0.84 | – |
| table_aware/hybrid+rr | 0.91 | 1.00 | 0.97 | 0.86 | – |
| table_aware/dense+rr | 0.79 | 1.00 | 0.89 | 0.92 | – |
| table_aware/dense | 0.86 | 1.00 | 0.90 | 0.92 | – |
| table_aware/bm25+rr | 0.91 | 1.00 | 0.91 | 0.81 | – |
| table_aware/bm25 | 0.87 | 1.00 | 0.93 | 0.94 | – |
| table_aware/hybrid | 0.88 | 1.00 | 0.89 | 1.00 | – |

## correctness by question category

| Config | cross_company | exact_term | factual | numeric_table | unanswerable |
|---|---|---|---|---|---|
| fixed/hybrid+rr | 0.62 | 0.75 | 0.67 | 0.33 | – |
| section/hybrid+rr | 0.88 | 0.75 | 0.58 | 0.75 | – |
| table_aware/hybrid+rr | 0.75 | 0.75 | 0.50 | 0.92 | – |
| table_aware/dense+rr | 0.50 | 0.25 | 0.58 | 1.00 | – |
| table_aware/dense | 0.62 | 0.25 | 0.58 | 0.58 | – |
| table_aware/bm25+rr | 0.62 | 0.75 | 0.58 | 0.42 | – |
| table_aware/bm25 | 0.25 | 0.75 | 0.42 | 0.42 | – |
| table_aware/hybrid | 0.75 | 0.25 | 0.50 | 0.58 | – |
