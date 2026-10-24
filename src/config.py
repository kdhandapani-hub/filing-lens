"""Central config for the Week 2 Financial RAG project."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROC = ROOT / "data" / "processed"
for p in (DATA_RAW, DATA_PROC):
    p.mkdir(parents=True, exist_ok=True)

# --- Models (Nebius Token Factory) ---
EMBED_MODEL = os.getenv("NEBIUS_EMBED_MODEL", "Qwen/Qwen3-Embedding-8B")  # 4096-dim
CHAT_MODEL = os.getenv("NEBIUS_CHAT_MODEL", "")  # exact ID from the Nebius playground
# Optional switches to turn off hidden reasoning (find the right one with: python -m src.check_reasoning)
CHAT_EXTRA_BODY = os.getenv("NEBIUS_CHAT_EXTRA_BODY", "")      # JSON, e.g. {"chat_template_kwargs": {"thinking": false}}
REASONING_EFFORT = os.getenv("NEBIUS_REASONING_EFFORT", "")    # e.g. low

# --- Eval judge: a different model family from the answer model, so answers aren't graded by their own author.
JUDGE_PROVIDER = os.getenv("JUDGE_PROVIDER", "openai" if os.getenv("OPENAI_API_KEY") else "nebius")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-4.1-mini")   # any OpenAI chat model ID your key can use

# --- Retrieval defaults (Day 2). Tune RELEVANCE_THRESHOLD on the eval set. ---
CANDIDATES_K = 10           # per retriever (dense and BM25) before fusion
RRF_K = 60                  # reciprocal-rank-fusion constant
TOP_N = 5                   # chunks passed to the LLM for single-company / open questions
COMPARISON_BUDGET = int(os.getenv("COMPARISON_BUDGET", "10"))  # total chunks shared across compared companies
MIN_PER_COMPANY, MAX_PER_COMPANY = 3, 5                         # -> 2 firms: 5 each, 4 firms: 3 each
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.05"))  # min rerank score to answer; 0.15 -> 0.05 raised eval correctness 0.72 -> 0.81 with refusals unchanged

# --- Vector store (Pinecone serverless): one index, one namespace per chunking strategy ---
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "week2-financial-rag")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")
EMBED_DIM = int(os.getenv("EMBED_DIM", "4096"))  # must match EMBED_MODEL
RERANK_MODEL = os.getenv("PINECONE_RERANK_MODEL", "bge-reranker-v2-m3")

# SEC requires a descriptive User-Agent: "Your Name your@email.com"
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "")

# --- Corpus: 4 broker-dealer / wealth firms (verify CIKs on EDGAR if a download fails) ---
COMPANIES = {
    "RJF": {"name": "Raymond James Financial", "cik": "720005"},
    "SCHW": {"name": "Charles Schwab", "cik": "316709"},
    "LPLA": {"name": "LPL Financial Holdings", "cik": "1397911"},
    "SF": {"name": "Stifel Financial", "cik": "720672"},
}

# --- 10-K sections in scope. Patterns match headings at the START of a line,
#     so cross-references like "see Item 1A" mid-sentence are ignored. ---
SECTIONS = {
    "1A": {
        "title": "Risk Factors",
        "start": r"^\s*item\s+1a(?![0-9])",
        "end": r"^\s*item\s+(1b|1c|2)(?![0-9a-z])",
    },
    "7": {
        "title": "Management's Discussion and Analysis",
        "start": r"^\s*item\s+7(?![0-9a])",
        "end": r"^\s*item\s+(7a|8)(?![0-9])",
    },
}

# --- Chunking strategies compared in the report ---
STRATEGIES = ["fixed", "section", "table_aware"]
FIXED_CHUNK_TOKENS = 512
FIXED_OVERLAP_TOKENS = 64
SECTION_MAX_TOKENS = 800
SECTION_MIN_TOKENS = 150  # don't start a new chunk at a heading until this much text accumulated
TABLE_MAX_TOKENS = 600
