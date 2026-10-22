"""Step 4: embed each chunking strategy into its own Pinecone namespace (dense)
and save the chunks locally for BM25 (sparse).

Usage:  python -m src.index            # all strategies
        python -m src.index fixed      # just one
Re-running is safe: each namespace is cleared and rebuilt.
"""
import json
import pickle
import statistics
import sys
import time

from langchain_nebius import NebiusEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from src.chunking import STRATEGY_FNS
from src.config import (DATA_PROC, DATA_RAW, EMBED_DIM, EMBED_MODEL, PINECONE_CLOUD,
                        PINECONE_INDEX, PINECONE_REGION, STRATEGIES)


def get_index():
    pc = Pinecone()  # reads PINECONE_API_KEY
    if PINECONE_INDEX not in pc.list_indexes().names():
        pc.create_index(name=PINECONE_INDEX, dimension=EMBED_DIM, metric="cosine",
                        spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION))
        while not pc.describe_index(PINECONE_INDEX).status["ready"]:
            time.sleep(2)
    return pc.Index(PINECONE_INDEX)


def load_chunks(strategy: str):
    manifest = json.loads((DATA_RAW / "manifest.json").read_text())
    docs = []
    for ticker, meta in manifest.items():
        blocks = json.loads((DATA_PROC / f"{ticker}.json").read_text())
        docs += STRATEGY_FNS[strategy](blocks, {**meta, "ticker": ticker})
    return docs


def build(strategy: str, index, embeddings):
    docs = load_chunks(strategy)
    toks = [d.metadata["tokens"] for d in docs]
    print(f"[{strategy}] {len(docs)} chunks | tokens median {statistics.median(toks):.0f}, "
          f"max {max(toks)} | tables {sum(d.metadata['kind'] == 'table' for d in docs)}")

    try:
        index.delete(delete_all=True, namespace=strategy)
    except Exception:
        pass  # namespace doesn't exist yet on first run

    store = PineconeVectorStore(index=index, embedding=embeddings, namespace=strategy)
    for i in range(0, len(docs), 64):  # batch to stay within API payload limits
        batch = docs[i:i + 64]
        store.add_documents(batch, ids=[d.metadata["chunk_id"] for d in batch])

    # BM25 is rebuilt in memory at query time from these docs (fast, no extra infra)
    with open(DATA_PROC / f"chunks_{strategy}.pkl", "wb") as f:
        pickle.dump(docs, f)


def main():
    index = get_index()
    embeddings = NebiusEmbeddings(model=EMBED_MODEL)
    for s in (sys.argv[1:] or STRATEGIES):
        build(s, index, embeddings)
    print(index.describe_index_stats())


if __name__ == "__main__":
    main()
