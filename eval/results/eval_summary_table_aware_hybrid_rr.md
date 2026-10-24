# Evaluation summary

22 questions × 1 configurations. Judge: openai:gpt-4.1-mini. Scores are means over the questions where the metric applies.

## Overall

| Config | Retrieval hit | Refusal correct | Faithfulness | Correctness | Latency p50 (s) | p95 (s) | ≤5s |
|---|---|---|---|---|---|---|---|
| table_aware/hybrid+rr | 0.94 | 0.95 | 0.92 | 0.81 | 5.07 | 6.72 | 0.50 |

## retrieval_hit by question category

| Config | cross_company | exact_term | factual | numeric_table | unanswerable |
|---|---|---|---|---|---|
| table_aware/hybrid+rr | 1.00 | 1.00 | 0.83 | 1.00 | – |

## faithfulness by question category

| Config | cross_company | exact_term | factual | numeric_table | unanswerable |
|---|---|---|---|---|---|
| table_aware/hybrid+rr | 0.90 | 1.00 | 1.00 | 0.83 | – |

## correctness by question category

| Config | cross_company | exact_term | factual | numeric_table | unanswerable |
|---|---|---|---|---|---|
| table_aware/hybrid+rr | 1.00 | 0.75 | 0.58 | 0.92 | – |
