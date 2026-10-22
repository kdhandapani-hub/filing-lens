"""Step 3: three chunking strategies over the same cleaned blocks.

  fixed        — ignore structure; 512-token windows, 64 overlap (baseline)
  section      — split on 10-K headings; tables flattened into the surrounding text
  table_aware  — section chunks for prose; every data table is its own chunk,
                 prefixed with company / item / heading context so it is retrievable

Every chunk carries metadata used for citations: ticker, company, fiscal_year, item, heading, chunk_id.
"""
import tiktoken
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import (FIXED_CHUNK_TOKENS, FIXED_OVERLAP_TOKENS, SECTION_MAX_TOKENS,
                        SECTION_MIN_TOKENS, SECTIONS, TABLE_MAX_TOKENS)

ENC = tiktoken.get_encoding("cl100k_base")  # token counting proxy


def ntok(s: str) -> int:
    return len(ENC.encode(s))


_splitter = lambda size, overlap: RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base", chunk_size=size, chunk_overlap=overlap,
    separators=["\n\n", "\n", ". ", " ", ""])


def _base_meta(meta: dict, item: str) -> dict:
    return {"ticker": meta["ticker"], "company": meta["name"],
            "fiscal_year": meta["report_date"][:4], "item": item,
            "item_title": SECTIONS[item]["title"]}


def fixed(blocks, meta, strategy="fixed") -> list[Document]:
    docs = []
    split = _splitter(FIXED_CHUNK_TOKENS, FIXED_OVERLAP_TOKENS)
    for item in SECTIONS:
        text = "\n\n".join(b["text"] for b in blocks if b["item"] == item)
        for piece in split.split_text(text):
            docs.append(Document(piece, metadata={**_base_meta(meta, item), "heading": "", "kind": "text"}))
    return _number(docs, strategy)


def section(blocks, meta, strategy="section", tables_separate=False) -> list[Document]:
    docs = []
    split = _splitter(SECTION_MAX_TOKENS, 80)
    for item in SECTIONS:
        buf, heading = [], SECTIONS[item]["title"]

        def flush():
            body = "\n\n".join(buf).strip()
            if body:
                for piece in (split.split_text(body) if ntok(body) > SECTION_MAX_TOKENS else [body]):
                    docs.append(Document(f"[{heading}]\n{piece}", metadata={
                        **_base_meta(meta, item), "heading": heading, "kind": "text"}))
            buf.clear()

        for b in (x for x in blocks if x["item"] == item):
            if b["type"] == "heading":
                if ntok("\n\n".join(buf)) >= SECTION_MIN_TOKENS:
                    flush()
                    heading = b["heading"]  # full "CATEGORY > title" path from ingest
                elif not buf:
                    heading = b["heading"]
                else:  # previous section too small to stand alone: merge, keep heading inline
                    buf.append(b["text"])
            elif b["type"] == "table" and tables_separate:
                docs.extend(_table_docs(b, meta, item))
            else:
                buf.append(b["text"])
        flush()
    return _number(docs, strategy)


def _table_docs(b, meta, item) -> list[Document]:
    header = f"{meta['name']} ({meta['ticker']}) FY{meta['report_date'][:4]} 10-K, Item {item} — {b['heading']}. Table:"
    lines = b["text"].split("\n")
    head, rows = lines[:2], lines[2:]
    parts, cur = [], []
    for r in rows:  # split very large tables by rows, repeating the column header
        if cur and ntok("\n".join(head + cur + [r])) > TABLE_MAX_TOKENS:
            parts.append(cur)
            cur = []
        cur.append(r)
    parts.append(cur)
    return [Document(f"{header}\n" + "\n".join(head + p), metadata={
        **_base_meta(meta, item), "heading": b["heading"], "kind": "table"}) for p in parts if p]


def table_aware(blocks, meta) -> list[Document]:
    return section(blocks, meta, strategy="table_aware", tables_separate=True)


def _number(docs, strategy):
    for i, d in enumerate(docs):
        m = d.metadata
        m["strategy"] = strategy
        m["chunk_id"] = f"{m['ticker']}-{strategy}-{m['item']}-{i:04d}"
        m["tokens"] = ntok(d.page_content)
    return docs


STRATEGY_FNS = {"fixed": fixed, "section": section, "table_aware": table_aware}
