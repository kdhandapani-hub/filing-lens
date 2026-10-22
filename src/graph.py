"""Day 2: the RAG flow as a LangGraph.

    plan ─► retrieve ─► grade ──relevant──► generate ──answered──► END
                              └─weak──► refuse ◄──NOT_FOUND──┘

plan      detect companies; comparison questions become one sub-query per company
retrieve  hybrid/dense/bm25 (+ rerank) per sub-query, in the chosen strategy namespace
grade     retrieval-level guard: refuse if the best rerank score is below threshold
generate  answer ONLY from the numbered context, cite [n]; emit NOT_FOUND if unsupported
refuse    fixed "not in the filings" response (the designed failure mode)

Two refusal gates on purpose: grade catches "nothing relevant was retrieved",
generate catches "something was retrieved but it doesn't answer this question"
(e.g. a firm that isn't in the corpus, or a forecast the filings don't make).
"""
import re
import time
from functools import lru_cache
from typing import TypedDict

from langchain_core.documents import Document
from langgraph.graph import END, StateGraph

import json

from src.config import CHAT_EXTRA_BODY, CHAT_MODEL, COMPANIES, REASONING_EFFORT, RELEVANCE_THRESHOLD, TOP_N, TOP_N_PER_COMPANY
from src.retrieval import STAGE_TIMES, detect_tickers, retrieve as run_retrieval

REFUSAL = ("I can't answer that from the filings in this knowledge base "
           "(latest 10-Ks for Raymond James, Schwab, LPL Financial and Stifel; Items 1A and 7).")
NOT_FOUND = "NOT_FOUND"

SYSTEM = f"""You are a financial analyst assistant answering questions about SEC 10-K filings.
Rules:
- Use ONLY the numbered context passages. Never use outside knowledge.
- Cite every factual sentence with its passage number(s), e.g. [2] or [1][3].
- Quote figures exactly as written with the period they refer to. Tables in 10-Ks are usually
  "in millions" unless stated otherwise; say "(in millions)" when the context indicates it.
- For comparisons, cover each company separately, then summarize the difference.
- If the context does not contain the information needed, reply with exactly: {NOT_FOUND}
- If it only partly answers, answer the supported part and say what is not disclosed.
Be concise: at most 150 words. Start directly with the answer, no preamble."""
THINK = re.compile(r"<think>.*?</think>", re.S)


class RAGState(TypedDict, total=False):
    # inputs
    question: str
    strategy: str            # fixed | section | table_aware
    retriever: str           # dense | bm25 | hybrid
    use_rerank: bool
    threshold: float
    # intermediate
    tickers: list[str]
    docs: list[Document]
    max_score: float
    # outputs
    answer: str
    refused: bool
    refusal_reason: str      # low_relevance | not_in_context
    citations: list[dict]
    timings: dict
    gen_meta: dict           # finish_reason, token usage, attempts


@lru_cache
def _llm():
    from langchain_nebius import ChatNebius
    kw = {}
    if CHAT_EXTRA_BODY:
        kw["extra_body"] = json.loads(CHAT_EXTRA_BODY)
    if REASONING_EFFORT:
        kw["reasoning_effort"] = REASONING_EFFORT
    return ChatNebius(model=CHAT_MODEL, temperature=0, max_tokens=1500, **kw)


def _timed(name):
    def wrap(fn):
        def inner(state):
            t0 = time.perf_counter()
            out = fn(state)
            out["timings"] = {**state.get("timings", {}), name: round(time.perf_counter() - t0, 3)}
            return out
        inner.__name__ = name
        return inner
    return wrap


# ---------------- nodes ----------------
@_timed("plan")
def plan(state: RAGState) -> RAGState:
    return {"tickers": detect_tickers(state["question"])}


@_timed("retrieve")
def retrieve(state: RAGState) -> RAGState:
    q, tickers = state["question"], state.get("tickers") or []
    kw = dict(strategy=state.get("strategy", "table_aware"), retriever=state.get("retriever", "hybrid"),
              use_rerank=state.get("use_rerank", True))
    if len(tickers) >= 2:  # comparison: guarantee every named company is represented
        docs = [d for t in tickers for d in run_retrieval(q, ticker=t, top_n=TOP_N_PER_COMPANY, **kw)]
    else:
        docs = run_retrieval(q, ticker=tickers[0] if tickers else None, top_n=TOP_N, **kw)
    scores = [d.metadata.get("rerank_score") for d in docs if d.metadata.get("rerank_score") is not None]
    return {"docs": docs, "max_score": max(scores) if scores else None}


@_timed("grade")
def grade(state: RAGState) -> RAGState:
    docs, thr = state.get("docs", []), state.get("threshold", RELEVANCE_THRESHOLD)
    if not docs:
        return {"refused": True, "refusal_reason": "low_relevance"}
    if state.get("max_score") is None:  # no reranker -> no calibrated score; let generate decide
        return {"refused": False}
    kept = [d for d in docs if d.metadata["rerank_score"] >= thr]
    if not kept:
        return {"refused": True, "refusal_reason": "low_relevance"}
    return {"docs": kept, "refused": False}


def format_context(docs: list[Document]) -> str:
    parts = []
    for i, d in enumerate(docs, 1):
        m = d.metadata
        parts.append(f"[{i}] {m['company']} ({m['ticker']}) FY{m['fiscal_year']} 10-K, "
                     f"Item {m['item']} ({m['item_title']}) — {m.get('heading') or 'n/a'}\n{d.page_content}")
    return "\n\n---\n\n".join(parts)


@_timed("generate")
def generate(state: RAGState) -> RAGState:
    docs = state["docs"]
    prompt = [("system", SYSTEM),
              ("human", f"Context:\n\n{format_context(docs)}\n\nQuestion: {state['question']}")]
    text, meta = "", {}
    for attempt in (1, 2):  # retry once if the model returns no visible text
        msg = _llm().invoke(prompt)
        text = THINK.sub("", msg.content or "").strip()
        meta = {"finish_reason": (msg.response_metadata or {}).get("finish_reason"),
                "usage": getattr(msg, "usage_metadata", None), "attempts": attempt}
        if text:
            break
    if not text:
        return {"answer": "[empty model output]", "citations": [], "refused": False,
                "refusal_reason": "empty_output", "gen_meta": meta}
    if text.startswith(NOT_FOUND) or text == NOT_FOUND:
        return {"refused": True, "refusal_reason": "not_in_context", "gen_meta": meta}
    used = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text) if 0 < int(n) <= len(docs)})
    cites = [{"n": n, "chunk_id": docs[n - 1].metadata["chunk_id"], "ticker": docs[n - 1].metadata["ticker"],
              "item": docs[n - 1].metadata["item"], "heading": docs[n - 1].metadata.get("heading", "")}
             for n in used]
    return {"answer": text, "citations": cites, "refused": False, "gen_meta": meta}


@_timed("refuse")
def refuse(state: RAGState) -> RAGState:
    return {"answer": REFUSAL, "citations": [], "refused": True}


# ---------------- graph ----------------
def build_graph():
    g = StateGraph(RAGState)
    for name, fn in [("plan", plan), ("retrieve", retrieve), ("grade", grade),
                     ("generate", generate), ("refuse", refuse)]:
        g.add_node(name, fn)
    g.set_entry_point("plan")
    g.add_edge("plan", "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", lambda s: "refuse" if s.get("refused") else "generate",
                            {"refuse": "refuse", "generate": "generate"})
    g.add_conditional_edges("generate", lambda s: "refuse" if s.get("refused") else END,
                            {"refuse": "refuse", END: END})
    g.add_edge("refuse", END)
    return g.compile()


GRAPH = None


def ask(question: str, strategy: str = "table_aware", retriever: str = "hybrid",
        use_rerank: bool = True, threshold: float = RELEVANCE_THRESHOLD) -> RAGState:
    global GRAPH
    GRAPH = GRAPH or build_graph()
    t0 = time.perf_counter()
    stages = {}
    token = STAGE_TIMES.set(stages)
    out = GRAPH.invoke({"question": question, "strategy": strategy, "retriever": retriever,
                        "use_rerank": use_rerank, "threshold": threshold, "timings": {}},
                       config={"run_name": f"rag[{strategy}/{retriever}{'+rr' if use_rerank else ''}]",
                               "metadata": {"strategy": strategy, "retriever": retriever, "rerank": use_rerank},
                               "tags": [strategy, retriever, "rerank" if use_rerank else "no-rerank"]})
    STAGE_TIMES.reset(token)
    out["timings"]["total"] = round(time.perf_counter() - t0, 3)
    out["timings"]["retrieve_breakdown"] = stages
    return out


assert set(COMPANIES) == {"RJF", "SCHW", "LPLA", "SF"}
