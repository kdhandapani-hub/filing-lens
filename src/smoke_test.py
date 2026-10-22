"""Step 5: sanity check — run a few queries against each strategy's dense index and print top hits.

Usage:  python -m src.smoke_test
"""
from langchain_chroma import Chroma
from langchain_nebius import NebiusEmbeddings

from src.config import CHROMA_DIR, EMBED_MODEL, STRATEGIES

QUERIES = [
    "What does Raymond James say about interest rate risk?",
    "Schwab net revenues by segment",
    "LPL advisor recruiting and retention risks",
]


def main():
    emb = NebiusEmbeddings(model=EMBED_MODEL)
    for s in STRATEGIES:
        store = Chroma(collection_name=s, embedding_function=emb, persist_directory=str(CHROMA_DIR))
        print(f"\n=========== {s} ({store._collection.count()} chunks) ===========")
        for q in QUERIES:
            print(f"\nQ: {q}")
            for d, score in store.similarity_search_with_relevance_scores(q, k=3):
                m = d.metadata
                print(f"  {score:.3f} | {m['ticker']} Item {m['item']} | {m['kind']} | "
                      f"{m['heading'][:50]} | {d.page_content[:90]!r}")


if __name__ == "__main__":
    main()
