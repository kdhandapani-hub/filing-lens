"""Step 5: sanity check — dense top hits per strategy, then a Pinecone-hosted rerank.

Usage:  python -m src.smoke_test
"""
from langchain_nebius import NebiusEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

from src.config import EMBED_MODEL, PINECONE_INDEX, RERANK_MODEL, STRATEGIES

QUERIES = [
    "What does Raymond James say about interest rate risk?",
    "Schwab net revenues by segment",
    "LPL advisor recruiting and retention risks",
]


def main():
    pc = Pinecone()
    index = pc.Index(PINECONE_INDEX)
    emb = NebiusEmbeddings(model=EMBED_MODEL)
    for s in STRATEGIES:
        store = PineconeVectorStore(index=index, embedding=emb, namespace=s)
        print(f"\n=========== {s} ===========")
        for q in QUERIES:
            hits = store.similarity_search_with_score(q, k=8)
            print(f"\nQ: {q}\n  dense top-3:")
            for d, score in hits[:3]:
                m = d.metadata
                print(f"    {score:.3f} | {m['ticker']} Item {m['item']} | {m['kind']} | "
                      f"{m['heading'][:45]} | {d.page_content[:80]!r}")
            rr = pc.inference.rerank(model=RERANK_MODEL, query=q, top_n=3, return_documents=False,
                                     documents=[d.page_content for d, _ in hits])
            print("  reranked top-3:")
            for r in rr.data:
                m = hits[r.index][0].metadata
                print(f"    {r.score:.3f} | {m['ticker']} Item {m['item']} | {m['kind']} | {m['heading'][:45]} | "
                      f"{hits[r.index][0].page_content[:80]!r}")


if __name__ == "__main__":
    main()
