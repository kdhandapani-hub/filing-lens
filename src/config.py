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
CHAT_MODEL = os.getenv("NEBIUS_CHAT_MODEL", "")  # set in .env on Day 2 (from Nebius models page)

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
