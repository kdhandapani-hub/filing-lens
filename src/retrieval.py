"""Day 2: retrieval layer.

  dense   — Pinecone vector search in the strategy's namespace
  bm25    — keyword search over the same chunks (exact terms: tickers, program names, numbers)
  hybrid  — both, merged with Reciprocal Rank Fusion (RRF)
  rerank  — optional Pinecone-hosted cross-encoder over the fused candidates

Every function takes `ticker` so comparison questions can retrieve per company.
"""
import pickle
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache

from langchain_core.documents import Document
from langsmith import traceable
from rank_bm25 import BM25Okapi

from src.config import (CANDIDATES_K, COMPANIES, DATA_PROC, EMBED_MODEL, PINECONE_INDEX,
                        RERANK_MODEL, RRF_K)

# Per-request stage timings (seconds), summed across sub-queries. Reset by the graph per question.
STAGE_TIMES: ContextVar[dict] = ContextVar("STAGE_TIMES", default=None)


@contextmanager
def timed(stage: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        d = STAGE_TIMES.get()
        if d is not None:
            d[stage] = round(d.get(stage, 0.0) + time.perf_counter() - t0, 3)


TOKEN = re.compile(r"[a-z0-9][a-z0-9.\-&%$]*")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


# ---------- clients (created once) ----------
@lru_cache
def _pc():
    from pinecone import Pinecone
    return Pinecone()


@lru_cache
def _embeddings():
    from langchain_nebius import NebiusEmbeddings
    return NebiusEmbeddings(model=EMBED_MODEL)


@lru_cache
def _store(strategy: str):
    from langchain_pinecone import PineconeVectorStore
    return PineconeVectorStore(index=_pc().Index(PINECONE_INDEX), embedding=_embeddings(),
                               namespace=strategy)


@lru_cache
def _bm25(strategy: str):
    with open(DATA_PROC / f"chunks_{strategy}.pkl", "rb") as f:
        docs: list[Document] = pickle.load(f)
    return docs, BM25Okapi([tokenize(d.page_content) for d in docs])


@lru_cache(maxsize=256)
def _embed_cached(q: str) -> tuple[float, ...]:
    return tuple(_embeddings().embed_query(q))


@traceable(name="embed_query")
def embed_query(q: str) -> tuple[float, ...]:
    with timed("embed"):
        return _embed_cached(q)


# ---------- retrievers ----------
@traceable(name="dense_pinecone")
def dense(query: str, strategy: str, ticker: str | None = None, k: int = CANDIDATES_K) -> list[Document]:
    flt = {"ticker": {"$eq": ticker}} if ticker else None
    vec = list(embed_query(query))
    with timed("pinecone"):
        hits = _store(strategy).similarity_search_by_vector_with_score(vec, k=k, filter=flt)
    return [_tag(d, dense_score=s) for d, s in hits]


@traceable(name="bm25")
def bm25(query: str, strategy: str, ticker: str | None = None, k: int = CANDIDATES_K) -> list[Document]:
    with timed("bm25"):
        docs, index = _bm25(strategy)
        scores = index.get_scores(tokenize(query))
    order = sorted(range(len(docs)), key=lambda i: -scores[i])
    out = []
    for i in order:
        if ticker and docs[i].metadata["ticker"] != ticker:
            continue
        if scores[i] <= 0:
            break
        out.append(_tag(docs[i], bm25_score=float(scores[i])))
        if len(out) == k:
            break
    return out


def rrf(*ranked_lists: list[Document], k: int = RRF_K) -> list[Document]:
    """Reciprocal Rank Fusion: score = sum(1 / (k + rank)). Rank-based, so dense
    cosine scores and BM25 scores never need to be put on the same scale."""
    fused: dict[str, Document] = {}
    score: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, d in enumerate(lst):
            cid = d.metadata["chunk_id"]
            score[cid] = score.get(cid, 0.0) + 1.0 / (k + rank + 1)
            if cid in fused:
                fused[cid].metadata.update({m: v for m, v in d.metadata.items() if m.endswith("_score")})
            else:
                fused[cid] = d
    out = sorted(fused.values(), key=lambda d: -score[d.metadata["chunk_id"]])
    for d in out:
        d.metadata["rrf_score"] = round(score[d.metadata["chunk_id"]], 5)
    return out


@traceable(name="rerank")
def rerank(query: str, docs: list[Document], top_n: int) -> list[Document]:
    if not docs:
        return []
    with timed("rerank"):
        res = _pc().inference.rerank(model=RERANK_MODEL, query=query, documents=[d.page_content for d in docs],
                                     top_n=min(top_n, len(docs)), return_documents=False,
                                     parameters={"truncate": "END"})
    return [_tag(docs[r.index], rerank_score=float(r.score)) for r in res.data]


@traceable(name="retrieve")
def retrieve(query: str, strategy: str, retriever: str = "hybrid", use_rerank: bool = True,
             ticker: str | None = None, top_n: int = 5) -> list[Document]:
    if retriever == "dense":
        cands = dense(query, strategy, ticker)
    elif retriever == "bm25":
        cands = bm25(query, strategy, ticker)
    elif retriever == "hybrid":
        cands = rrf(dense(query, strategy, ticker), bm25(query, strategy, ticker))
    else:
        raise ValueError(f"unknown retriever {retriever!r}")
    return rerank(query, cands, top_n) if use_rerank else cands[:top_n]


# ---------- company detection (drives per-company filtering) ----------
ALIASES = {
    "RJF": [r"raymond\s+james", r"\brjf\b"],
    "SCHW": [r"schwab", r"\bschw\b"],
    "LPLA": [r"\blpl\b", r"\blpla\b"],
    "SF": [r"stifel", r"\bsf\b(?=\s|$|[?.,])"],
}
ALL_FIRMS = re.compile(r"\b(all (four|4|the) (firms|companies)|each (firm|company)|every (firm|company)|"
                       r"all of them|across (the )?(firms|companies))\b", re.I)


def detect_tickers(question: str) -> list[str]:
    if ALL_FIRMS.search(question):
        return list(COMPANIES)
    q = question.lower()
    return [t for t, pats in ALIASES.items() if any(re.search(p, q) for p in pats)]


def _tag(d: Document, **scores) -> Document:
    d = Document(d.page_content, metadata=dict(d.metadata))  # copy: never mutate cached docs
    d.metadata.update(scores)
    return d
