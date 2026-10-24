"""Filing Lens HTTP API: the front-end interface to the RAG graph.

Run locally:   uvicorn api:app --reload --port 8000      (docs at http://localhost:8000/docs)
On Replit:     see start.sh / .replit

Endpoints
  GET  /api/health     liveness + which models are configured
  GET  /api/options    strategies, retrievers and example questions for the UI
  POST /api/ask        {question, strategy?, retriever?, rerank?} -> answer, citations, refusal, timings

Access: when APP_ACCESS_CODE is set, /api/ask requires header  X-Access-Code: <code>.
The code is typed by the user in the UI, never baked into front-end JS, because anything shipped
to the browser is public. A per-IP rate limit caps spend if the code leaks.
If frontend/dist exists (the vibe-coded UI build), it is served at "/" from the same origin.
"""
import os
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import CHAT_MODEL, EMBED_MODEL, RERANK_MODEL, STRATEGIES

ACCESS_CODE = os.getenv("APP_ACCESS_CODE", "")
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_10_MIN", "30"))
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
FRONTEND = Path(__file__).parent / "frontend" / "dist"

EXAMPLES = [
    "What does Raymond James say about interest rate risk?",
    "What were Schwab's net revenues by segment?",
    "Which firm reported higher net revenues in its most recent fiscal year: Raymond James or LPL?",
    "Compare how Raymond James and Stifel describe competition for financial advisors.",
    "What were Morgan Stanley's wealth management revenues?",
]

_ready = threading.Event()


def _warm_up():
    """Load clients, BM25 corpora and the graph once, so the first user doesn't pay ~8s of cold start."""
    from src import graph
    from src.retrieval import _bm25, _pc, _store, embed_query, retrieve
    for s in STRATEGIES:
        _store(s)
        _bm25(s)
    _pc()
    embed_query("warm-up")
    # One real retrieval per namespace: opens the Pinecone index connection and the rerank endpoint,
    # which are otherwise cold on the first user question (~15-35s observed).
    for s in STRATEGIES:
        try:
            retrieve("What are the main risk factors?", s, retriever="hybrid", use_rerank=True)
        except Exception as e:  # warm-up must never block startup
            print(f"warm-up retrieve failed for {s}: {type(e).__name__}: {e}")
    graph.GRAPH = graph.build_graph()
    _ready.set()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    threading.Thread(target=_warm_up, daemon=True).start()  # health responds while warming
    yield


app = FastAPI(title="Filing Lens API", version="1.0", lifespan=lifespan)
if ALLOWED_ORIGINS:  # only needed if the UI is hosted on a different origin
    app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-Access-Code"])


# ---------------- models ----------------
class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    strategy: Literal["fixed", "section", "table_aware"] = "table_aware"
    retriever: Literal["hybrid", "dense", "bm25"] = "hybrid"
    rerank: bool = True


class Citation(BaseModel):
    n: int
    chunk_id: str
    ticker: str
    company: str
    item: str
    heading: str
    excerpt: str


class AskResponse(BaseModel):
    answer: str
    refused: bool
    refusal_reason: str | None = None
    citations: list[Citation]
    companies: list[str]
    top_score: float | None
    timings: dict
    config: str


# ---------------- access + rate limit ----------------
_hits: dict[str, deque] = defaultdict(deque)
_hits_lock = threading.Lock()


def _check_access(code: str | None, request: Request):
    if ACCESS_CODE and code != ACCESS_CODE:
        raise HTTPException(401, "Enter the access code to use Filing Lens.")
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    now = time.time()
    with _hits_lock:
        q = _hits[ip]
        while q and now - q[0] > 600:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            raise HTTPException(429, f"Limit is {RATE_LIMIT} questions per 10 minutes. Try again shortly.")
        q.append(now)


# ---------------- routes ----------------
@app.get("/api/health")
def health():
    return {"status": "ready" if _ready.is_set() else "warming_up", "chat_model": CHAT_MODEL,
            "embed_model": EMBED_MODEL, "rerank_model": RERANK_MODEL, "access_code_required": bool(ACCESS_CODE)}


@app.get("/api/options")
def options():
    return {"strategies": STRATEGIES, "retrievers": ["hybrid", "dense", "bm25"], "examples": EXAMPLES,
            "default": {"strategy": "table_aware", "retriever": "hybrid", "rerank": True}}


@app.post("/api/ask", response_model=AskResponse)
def ask_endpoint(body: AskRequest, request: Request, x_access_code: str | None = Header(default=None)):
    _check_access(x_access_code, request)
    if not _ready.wait(timeout=60):
        raise HTTPException(503, "Still starting up. Try again in a few seconds.")
    from src.graph import ask

    try:
        r = ask(body.question.strip(), strategy=body.strategy, retriever=body.retriever, use_rerank=body.rerank)
    except Exception as e:  # upstream API failure (Nebius, Pinecone): report it, don't leak a stack trace
        raise HTTPException(502, f"The answer service failed: {type(e).__name__}. Please retry.") from e

    docs = r.get("docs") or []
    cites = []
    for c in r.get("citations", []):
        d = docs[c["n"] - 1] if 0 < c["n"] <= len(docs) else None
        cites.append(Citation(n=c["n"], chunk_id=c["chunk_id"], ticker=c["ticker"],
                              company=d.metadata.get("company", c["ticker"]) if d else c["ticker"],
                              item=c["item"], heading=c.get("heading", ""),
                              excerpt=(d.page_content[:900] if d else "")))
    t = r.get("timings", {})
    return AskResponse(
        answer=r["answer"], refused=bool(r.get("refused")), refusal_reason=r.get("refusal_reason"),
        citations=cites, companies=r.get("tickers") or [], top_score=r.get("max_score"),
        timings={k: t.get(k) for k in ("total", "retrieve", "generate", "retrieve_breakdown")},
        config=f"{body.strategy}/{body.retriever}{'+rerank' if body.rerank else ''}")


# ---------------- front end (same origin) ----------------
if FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = (FRONTEND / path).resolve()
        if path and f.is_file() and f.is_relative_to(FRONTEND.resolve()):  # block ../ traversal
            return FileResponse(f)
        return FileResponse(FRONTEND / "index.html")
