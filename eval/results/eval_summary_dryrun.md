# Evaluation summary

3 questions × 8 configurations. Scores are means over the questions where the metric applies.

## Overall

| Config | Retrieval hit | Refusal correct | Faithfulness | Correctness | Latency p50 (s) | p95 (s) | ≤5s |
|---|---|---|---|---|---|---|---|
| fixed/hybrid+rr | 0.83 | 1.00 | 0.84 | – | 4.16 | 6.61 | 0.67 |
| section/hybrid+rr | 1.00 | 1.00 | 0.89 | – | 3.90 | 4.22 | 1.00 |
| table_aware/hybrid+rr | 1.00 | 0.67 | 1.00 | – | 2.73 | 2.94 | 1.00 |
| table_aware/dense+rr | 0.83 | 1.00 | 1.00 | – | 2.16 | 2.45 | 1.00 |
| table_aware/dense | 0.83 | 1.00 | 0.92 | – | 1.21 | 1.34 | 1.00 |
| table_aware/bm25+rr | 0.83 | 0.67 | 1.00 | – | 1.90 | 2.11 | 1.00 |
| table_aware/bm25 | 1.00 | 0.67 | 1.00 | – | 1.30 | 1.33 | 1.00 |
| table_aware/hybrid | 1.00 | 1.00 | 1.00 | – | 1.37 | 1.46 | 1.00 |

## retrieval_hit by question category

| Config | cross_company |
|---|---|
| fixed/hybrid+rr | 0.83 |
| section/hybrid+rr | 1.00 |
| table_aware/hybrid+rr | 1.00 |
| table_aware/dense+rr | 0.83 |
| table_aware/dense | 0.83 |
| table_aware/bm25+rr | 0.83 |
| table_aware/bm25 | 1.00 |
| table_aware/hybrid | 1.00 |

## faithfulness by question category

| Config | cross_company |
|---|---|
| fixed/hybrid+rr | 0.84 |
| section/hybrid+rr | 0.89 |
| table_aware/hybrid+rr | 1.00 |
| table_aware/dense+rr | 1.00 |
| table_aware/dense | 0.92 |
| table_aware/bm25+rr | 1.00 |
| table_aware/bm25 | 1.00 |
| table_aware/hybrid | 1.00 |

## correctness by question category

| Config | cross_company |
|---|---|
| fixed/hybrid+rr | – |
| section/hybrid+rr | – |
| table_aware/hybrid+rr | – |
| table_aware/dense+rr | – |
| table_aware/dense | – |
| table_aware/bm25+rr | – |
| table_aware/bm25 | – |
| table_aware/hybrid | – |
