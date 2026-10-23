# Evaluation summary

22 questions × 1 configurations. Judge: openai:gpt-4.1-mini. Scores are means over the questions where the metric applies.

## Overall

| Config | Retrieval hit | Refusal correct | Faithfulness | Correctness | Latency p50 (s) | p95 (s) | ≤5s |
|---|---|---|---|---|---|---|---|
| fixed/hybrid+rr | 0.92 | 0.86 | 0.95 | 0.53 | 2.04 | 6.63 | 0.86 |

## retrieval_hit by question category

| Config | cross_company | exact_term | factual | numeric_table | unanswerable |
|---|---|---|---|---|---|
| fixed/hybrid+rr | 0.88 | 1.00 | 0.83 | 1.00 | – |

## faithfulness by question category

| Config | cross_company | exact_term | factual | numeric_table | unanswerable |
|---|---|---|---|---|---|
| fixed/hybrid+rr | 0.86 | 1.00 | 1.00 | 0.95 | – |

## correctness by question category

| Config | cross_company | exact_term | factual | numeric_table | unanswerable |
|---|---|---|---|---|---|
| fixed/hybrid+rr | 0.50 | 0.75 | 0.67 | 0.33 | – |
