"""Ask the RAG app a question from the terminal.

Usage:
  python -m src.ask "What does Raymond James say about interest rate risk?"
  python -m src.ask "Compare RJF and Stifel advisor competition" --strategy section --retriever dense --no-rerank
  python -m src.ask --demo        # runs a fixed set covering answer, comparison and refusal paths
"""
import argparse

from src.config import STRATEGIES
from src.graph import ask

DEMO = [
    "What does Raymond James say about interest rate risk?",
    "What were Schwab's net revenues by segment?",
    "Compare how Raymond James and Stifel describe competition for financial advisors.",
    "What were Morgan Stanley's wealth management revenues?",   # out of corpus -> refuse
    "What is Raymond James' stock price target for next year?",  # not disclosed -> refuse
]


def show(q, r, show_docs=False):
    t = r["timings"]
    print(f"\nQ: {q}")
    print(f"   tickers={r.get('tickers')} | max_rerank={r.get('max_score')} | refused={r.get('refused')}"
          f"{' (' + r['refusal_reason'] + ')' if r.get('refusal_reason') else ''} | total {t['total']}s "
          f"(retrieve {t.get('retrieve')}s, generate {t.get('generate', '-')}s)")
    print(f"   retrieve breakdown: {t.get('retrieve_breakdown')}")
    gm = r.get("gen_meta") or {}
    if gm:
        print(f"   generation: finish={gm.get('finish_reason')} attempts={gm.get('attempts')} usage={gm.get('usage')}")
    print("\n" + r["answer"])
    for c in r.get("citations", []):
        print(f"   [{c['n']}] {c['chunk_id']} | {c['ticker']} Item {c['item']} | {c['heading'][:70]}")
    if show_docs or r.get("refused"):
        print("   retrieved:")
        for d in r.get("docs") or []:
            m = d.metadata
            print(f"     {m.get('rerank_score', m.get('rrf_score', 0)):.3f} | {m['chunk_id']} | {m['heading'][:55]} | "
                  f"{d.page_content[:70]!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--strategy", default="table_aware", choices=STRATEGIES)
    ap.add_argument("--retriever", default="hybrid", choices=["dense", "bm25", "hybrid"])
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--threshold", type=float)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--show-docs", action="store_true", help="print retrieved chunks")
    a = ap.parse_args()
    kw = dict(strategy=a.strategy, retriever=a.retriever, use_rerank=not a.no_rerank)
    if a.threshold is not None:
        kw["threshold"] = a.threshold
    from src.retrieval import _bm25, _pc, _store, embed_query
    _store(a.strategy); _bm25(a.strategy); _pc()  # warm up clients so timings exclude one-off setup
    embed_query("warm-up")                         # first embedding call is a cold start (~8s)
    for q in (DEMO if a.demo else [a.question]):
        show(q, ask(q, **kw), a.show_docs)


if __name__ == "__main__":
    main()
