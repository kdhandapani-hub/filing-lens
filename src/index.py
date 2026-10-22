"""Step 4: build one Chroma collection (dense) + one BM25 corpus (sparse) per chunking strategy.

Usage:  python -m src.index            # all strategies
        python -m src.index fixed      # just one
Re-running is safe: each collection is dropped and rebuilt.
"""
import json
import pickle
import statistics
import sys

from langchain_chroma import Chroma
from langchain_nebius import NebiusEmbeddings

from src.chunking import STRATEGY_FNS
from src.config import CHROMA_DIR, DATA_PROC, DATA_RAW, EMBED_MODEL, STRATEGIES


def load_chunks(strategy: str):
    manifest = json.loads((DATA_RAW / "manifest.json").read_text())
    docs = []
    for ticker, meta in manifest.items():
        blocks = json.loads((DATA_PROC / f"{ticker}.json").read_text())
        docs += STRATEGY_FNS[strategy](blocks, {**meta, "ticker": ticker})
    return docs


def build(strategy: str, embeddings):
    docs = load_chunks(strategy)
    toks = [d.metadata["tokens"] for d in docs]
    print(f"[{strategy}] {len(docs)} chunks | tokens median {statistics.median(toks):.0f}, "
          f"max {max(toks)} | tables {sum(d.metadata['kind'] == 'table' for d in docs)}")

    store = Chroma(collection_name=strategy, embedding_function=embeddings,
                   persist_directory=str(CHROMA_DIR))
    store.reset_collection()
    for i in range(0, len(docs), 64):  # batch to stay within API payload limits
        batch = docs[i:i + 64]
        store.add_documents(batch, ids=[d.metadata["chunk_id"] for d in batch])

    # BM25 is rebuilt in memory at query time from these docs (fast, no extra infra)
    with open(DATA_PROC / f"chunks_{strategy}.pkl", "wb") as f:
        pickle.dump(docs, f)


def main():
    embeddings = NebiusEmbeddings(model=EMBED_MODEL)
    for s in (sys.argv[1:] or STRATEGIES):
        build(s, embeddings)


if __name__ == "__main__":
    main()
