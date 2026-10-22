"""Speed up writing expected answers: draft a candidate for each answerable question,
with the exact source chunks, so you only VERIFY instead of reading 10-Ks cold.

Usage:
  python -m src.draft_expected                 # writes eval/expected_review.md + candidate_answer fields
  python -m src.draft_expected --promote N01,N02   # copy verified candidates into expected_answer

Workflow: read eval/expected_review.md, check each candidate against its quoted source chunk
(and the filing if needed), fix it in eval/questions_draft.json -> "candidate_answer", then promote.
Labels are drafted by the system but must be human-verified, or the eval would grade itself.
"""
import argparse
import json

from src.config import ROOT
from src.graph import ask

QFILE = ROOT / "eval" / "questions_draft.json"
REVIEW = ROOT / "eval" / "expected_review.md"


def draft():
    qs = json.loads(QFILE.read_text())
    md = ["# Expected-answer review", "",
          "For each question: check the candidate against the source chunks. If correct, promote it; "
          "if not, edit `candidate_answer` in questions_draft.json first.", ""]
    for q in qs:
        if q.get("expected_answer") or q["category"] == "unanswerable":
            continue
        r = ask(q["question"])
        q["candidate_answer"] = "" if r.get("refused") else r["answer"]
        md += [f"## {q['id']} ({q['category']}): {q['question']}", "",
               f"**Candidate:** {q['candidate_answer'] or '_(system refused; write the answer yourself)_'}", "",
               "<details><summary>Source chunks</summary>", ""]
        for i, d in enumerate(r.get("docs") or [], 1):
            m = d.metadata
            md += [f"**[{i}] {m['chunk_id']}** ({m['ticker']} Item {m['item']}, {m.get('heading', '')})", "",
                   "```", d.page_content[:1500], "```", ""]
        md += ["</details>", ""]
        print(f"{q['id']}: drafted ({'refused' if r.get('refused') else 'ok'})")
    QFILE.write_text(json.dumps(qs, indent=2, ensure_ascii=False))
    REVIEW.write_text("\n".join(md))
    print(f"\nReview: {REVIEW}\nThen: python -m src.draft_expected --promote ID1,ID2,...")


def promote(ids):
    qs = json.loads(QFILE.read_text())
    for q in qs:
        if q["id"] in ids and q.get("candidate_answer"):
            q["expected_answer"] = q["candidate_answer"]
            print(f"{q['id']}: promoted")
    QFILE.write_text(json.dumps(qs, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--promote", help="comma-separated question IDs whose candidate you verified")
    a = ap.parse_args()
    promote(set(a.promote.split(","))) if a.promote else draft()
