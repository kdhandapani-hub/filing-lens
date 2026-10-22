"""Step 1: download the latest 10-K (primary HTML doc) for each company from SEC EDGAR.

Usage:  python -m src.download
Needs SEC_USER_AGENT in .env, e.g. "Karthik Dhandapani you@email.com" (SEC rule).
"""
import json
import time

import requests

from src.config import COMPANIES, DATA_RAW, SEC_USER_AGENT


def latest_10k(cik: str, headers: dict) -> dict:
    url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    recent = r.json()["filings"]["recent"]
    for i, form in enumerate(recent["form"]):
        if form == "10-K":
            return {
                "accession": recent["accessionNumber"][i],
                "primary_doc": recent["primaryDocument"][i],
                "filing_date": recent["filingDate"][i],
                "report_date": recent["reportDate"][i],
            }
    raise ValueError(f"No 10-K found for CIK {cik}")


def main():
    if not SEC_USER_AGENT:
        raise SystemExit("Set SEC_USER_AGENT in .env first (e.g. 'Your Name you@email.com').")
    headers = {"User-Agent": SEC_USER_AGENT}
    manifest = {}
    for ticker, meta in COMPANIES.items():
        f = latest_10k(meta["cik"], headers)
        acc = f["accession"].replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(meta['cik'])}/{acc}/{f['primary_doc']}"
        out = DATA_RAW / f"{ticker}_10K_{f['report_date']}.html"
        if not out.exists():
            r = requests.get(url, headers=headers, timeout=60)
            r.raise_for_status()
            out.write_bytes(r.content)
            time.sleep(0.5)  # stay well under SEC's 10 req/sec limit
        manifest[ticker] = {**meta, **f, "url": url, "file": out.name}
        print(f"{ticker}: {f['report_date']} 10-K -> {out.name} ({out.stat().st_size // 1024} KB)")
    (DATA_RAW / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
