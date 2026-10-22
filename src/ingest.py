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


def is_heading(el, text: str) -> bool:
    if el.name and el.name.startswith("h"):
        return True
    if len(text) > 120 or text.endswith("."):
        return False
    bold = el.find(["b", "strong"]) or re.search(
        r"font-weight:\s*(bold|700)", (el.get("style") or "") + str(el.find("span") or "")
    )
    return bool(bold) and len(text.split()) <= 14


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
        if not text or re.fullmatch(r"(page )?\d{1,3}|table of contents", text, re.I):
            continue  # page numbers / running headers
        blocks.append({"type": "heading" if is_heading(el, text) else "text", "text": text})
    return blocks


def extract_sections(blocks: list[dict]) -> list[dict]:
    """Keep blocks inside each in-scope Item. Table of Contents entries also match the
    start pattern, so we take the LAST start whose span holds real content."""
    out = []
    for item, spec in SECTIONS.items():
        starts = [i for i, b in enumerate(blocks)
                  if b["type"] != "table" and re.match(spec["start"], b["text"], re.I)]
        best = None
        for s in starts:
            e = next((j for j in range(s + 1, len(blocks))
                      if blocks[j]["type"] != "table" and re.match(spec["end"], blocks[j]["text"], re.I)),
                     len(blocks))
            size = sum(len(b["text"]) for b in blocks[s + 1:e])
            if size >= 2000:
                best = (s, e, size)  # keep overwriting -> last qualifying start wins
        if not best:
            print(f"  WARN: Item {item} not found or too short")
            continue
        heading = spec["title"]
        for b in blocks[best[0] + 1: best[1]]:
            if b["type"] == "heading":
                heading = b["text"]
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
