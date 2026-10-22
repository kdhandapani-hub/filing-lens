# Week 2 — Financial Document Intelligence RAG

> My RAG app helps wealth-management analysts answer risk, segment and performance questions from the latest 10-K filings of four broker-dealers (Raymond James, Schwab, LPL, Stifel — SEC EDGAR, Items 1A and 7) via a chat API with ≥90% faithfulness and a ≤5s latency ceiling.

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
