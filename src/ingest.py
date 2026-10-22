"""Step 2: clean each 10-K and extract Item 1A + Item 7 into structured blocks.

Output: data/processed/<TICKER>.json — a list of blocks, each one of:
  {"type": "heading"|"text"|"table", "item": "1A"|"7", "text": ..., "heading": <nearest heading>}
Tables are converted to pipe-delimited markdown so numbers stay aligned with their row/column labels.

Usage:  python -m src.ingest
"""
import json
import re
import unicodedata

from bs4 import BeautifulSoup

from src.config import DATA_PROC, DATA_RAW, SECTIONS

BLOCK_TAGS = ["p", "div", "table", "h1", "h2", "h3", "h4", "h5", "h6", "li"]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def table_to_md(table) -> str | None:
    rows = []
    for tr in table.find_all("tr"):
        cells = [norm(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
        # EDGAR splits "$", value and ")" into separate cells; merge and drop empties
        merged, buf = [], ""
        for c in cells:
            if c in ("$", "(", "%", ")", "%)"):
                buf = (buf + c) if c in ("$", "(") else ""
                if c in ("%", ")", "%)") and merged:
                    merged[-1] += c
                continue
            if c:
                merged.append(buf + c)
                buf = ""
        if merged:
            rows.append(merged)
    if len(rows) < 2 or not any(re.search(r"\d", " ".join(r)) for r in rows):
        return None  # layout table, not data
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


EMPH_STYLE = re.compile(r"font-weight:\s*(bold|[6-9]00)|font-style:\s*italic", re.I)


def emphasis_ratio(el) -> float:
    """Share of the element's text that is bold or italic (tags or inline CSS)."""
    total = len(norm(el.get_text(" ")))
    if not total:
        return 0.0
    emph = 0
    for node in el.find_all(string=True):
        t = len(norm(str(node)))
        if not t:
            continue
        for anc in [node.parent, *node.parents]:
            if anc is el.parent:
                break
            if anc.name in ("b", "strong", "i", "em") or EMPH_STYLE.search(anc.get("style") or ""):
                emph += t
                break
    return emph / total


def is_heading(el, text: str) -> bool:
    if el.name and el.name.startswith("h"):
        return True
    # Short labels ("Credit Risk") and full-sentence risk-factor titles, which 10-Ks
    # set in bold/italic and often end with a period, are both headings when the
    # whole block is emphasized. Ordinary prose with a bold phrase is not.
    return len(text) <= 400 and emphasis_ratio(el) >= 0.85


def is_category(text: str) -> bool:
    """ALL-CAPS group headings like 'RISKS RELATED TO OUR REGULATORY ENVIRONMENT'."""
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 8 and sum(c.isupper() for c in letters) / len(letters) > 0.9


PAGE_ARTIFACT = re.compile(r"(page\s*)?[-–—]?\s*\d{1,3}\s*[-–—]?|table of contents", re.I)


def drop_running_headers(blocks: list[dict]) -> list[dict]:
    """Remove page numbers and short lines repeated on many pages (running headers)."""
    from collections import Counter
    counts = Counter(b["text"] for b in blocks if b["type"] != "table" and len(b["text"]) < 120)
    return [b for b in blocks if b["type"] == "table" or
            not (PAGE_ARTIFACT.fullmatch(b["text"]) or counts[b["text"]] >= 5)]


def linearize(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "ix:header"]):
        t.decompose()
    blocks, seen = [], set()
    for el in soup.find_all(BLOCK_TAGS):
        if any(id(p) in seen for p in el.parents):
            continue  # already consumed as part of a parent block
        if el.name == "table":
            seen.add(id(el))
            md = table_to_md(el)
            if md:
                blocks.append({"type": "table", "text": md})
            continue
        if el.find(BLOCK_TAGS):
            continue  # container; its children will be visited
        seen.add(id(el))
        text = norm(el.get_text(" "))
        if not text:
            continue
        blocks.append({"type": "heading" if is_heading(el, text) else "text", "text": text})
    return drop_running_headers(blocks)


def extract_sections(blocks: list[dict]) -> list[dict]:
    """Keep blocks inside each in-scope Item. Table of Contents entries also match the
    start pattern; a TOC span always contains other 'Item N' lines, a real section never
    does, so we keep the largest span with no other Item heading inside it."""
    any_item = re.compile(r"^\s*item\s+\d{1,2}[a-c]?(?![0-9a-z])", re.I)
    out = []
    for item, spec in SECTIONS.items():
        starts = [i for i, b in enumerate(blocks)
                  if b["type"] != "table" and re.match(spec["start"], b["text"], re.I)]
        best = None
        for s in starts:
            e = next((j for j in range(s + 1, len(blocks))
                      if blocks[j]["type"] != "table" and re.match(spec["end"], blocks[j]["text"], re.I)),
                     len(blocks))
            inner = blocks[s + 1:e]
            if any(b["type"] != "table" and any_item.match(b["text"]) for b in inner):
                continue  # TOC span: runs across other Items
            size = sum(len(b["text"]) for b in inner)
            if size >= 500 and (best is None or size > best[2]):
                best = (s, e, size)
        if not best:
            print(f"  WARN: Item {item} not found or too short")
            continue
        category, heading = "", spec["title"]
        for b in blocks[best[0] + 1: best[1]]:
            if b["type"] == "heading":
                if is_category(b["text"]):
                    category, heading = b["text"], b["text"]
                else:
                    heading = f"{category} > {b['text']}" if category else b["text"]
            out.append({**b, "item": item, "heading": heading})
    return out


def main():
    manifest = json.loads((DATA_RAW / "manifest.json").read_text())
    for ticker, meta in manifest.items():
        html = (DATA_RAW / meta["file"]).read_text(encoding="utf-8", errors="ignore")
        blocks = extract_sections(linearize(html))
        (DATA_PROC / f"{ticker}.json").write_text(json.dumps(blocks, indent=1))
        n_tab = sum(b["type"] == "table" for b in blocks)
        chars = {i: sum(len(b["text"]) for b in blocks if b["item"] == i) for i in SECTIONS}
        print(f"{ticker}: {len(blocks)} blocks, {n_tab} tables, chars by item {chars}")


if __name__ == "__main__":
    main()
