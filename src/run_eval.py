"""Day 3: evaluation matrix, logged to LangSmith as one experiment per configuration.

Usage:
  python -m src.run_eval                 # core matrix (8 configs) over all questions
  python -m src.run_eval --full          # all 18 configs (3 strategies x 3 retrievers x rerank on/off)
  python -m src.run_eval --limit 3       # quick dry run on the first 3 questions

Metrics per question (LangSmith feedback keys):
  retrieval_hit     share of expected companies whose expected Item appears in the retrieved chunks
  refusal_correct   1 if it refused exactly when it should (expected_answer == "REFUSE")
  faithfulness      LLM judge: share of answer claims supported by the retrieved context
  correctness       LLM judge vs your expected_answer (skipped when expected_answer is empty)
  latency_s / under_5s

Outputs: eval/results/eval_rows.csv (one row per question x config) and eval/results/eval_summary.md.
"""
import argparse
import csv
import hashlib
import json
import re
import statistics
from collections import defaultdict

from src.config import ROOT, STRATEGIES
from src import graph
from src.graph import ask, format_context

QFILE = ROOT / "eval" / "questions_draft.json"
OUT = ROOT / "eval" / "results"

CORE = ([(s, "hybrid", True) for s in STRATEGIES] +                       # chunking comparison
        [("table_aware", r, rr) for r in ("dense", "bm25", "hybrid")      # retrieval / rerank ablation
         for rr in (True, False) if not (r == "hybrid" and rr)])
FULL = [(s, r, rr) for s in STRATEGIES for r in ("dense", "bm25", "hybrid") for rr in (True, False)]


def label(cfg):
    s, r, rr = cfg
    return f"{s}/{r}{'+rr' if rr else ''}"


# ---------------- dataset ----------------
def ensure_dataset(client):
    qs = json.loads(QFILE.read_text())
    name = f"filing-lens-eval-{hashlib.sha1(QFILE.read_bytes()).hexdigest()[:8]}"  # new name when questions change
    if not client.has_dataset(dataset_name=name):
        ds = client.create_dataset(name, description="Broker-dealer 10-K questions (Items 1A/7): factual, "
                                                       "numeric/table, cross-company, exact-term, unanswerable")
        client.create_examples(
            inputs=[{"question": q["question"]} for q in qs],
            outputs=[{k: q.get(k) for k in ("id", "category", "tickers", "item", "expected_answer")} for q in qs],
            dataset_id=ds.id)
    return name


# ---------------- target ----------------
def make_target(strategy, retriever, use_rerank):
    def target(inputs: dict) -> dict:
        r = ask(inputs["question"], strategy=strategy, retriever=retriever, use_rerank=use_rerank)
        docs = r.get("docs") or []
        return {"answer": r["answer"], "refused": bool(r.get("refused")),
                "refusal_reason": r.get("refusal_reason"),
                "retrieved": [{k: d.metadata.get(k) for k in ("chunk_id", "ticker", "item", "kind", "rerank_score")}
                              for d in docs],
                "context": format_context(docs) if docs else "",
                "latency_s": r["timings"]["total"]}
    return target


# ---------------- evaluators ----------------
def _out(run):
    return run.outputs or {}


def _ref(example):
    return example.outputs or {}


def _should_refuse(example):
    return (_ref(example).get("expected_answer") or "").strip().upper() == "REFUSE"


def refusal_correct(run, example):
    return {"key": "refusal_correct", "score": int(_out(run).get("refused", False) == _should_refuse(example))}


def retrieval_hit(run, example):
    ref = _ref(example)
    want, item = ref.get("tickers") or [], ref.get("item") or ""
    if not want:
        return {"key": "retrieval_hit", "score": None}
    got = {(d["ticker"], d["item"]) for d in _out(run).get("retrieved", [])}
    hits = [any(gt == t and (not item or gi == item) for gt, gi in got) for t in want]
    return {"key": "retrieval_hit", "score": sum(hits) / len(want)}


def latency(run, example):
    return {"key": "latency_s", "score": _out(run).get("latency_s")}


def under_5s(run, example):
    lat = _out(run).get("latency_s")
    return {"key": "under_5s", "score": None if lat is None else int(lat <= 5.0)}


FAITH_PROMPT = """You are grading a retrieval-augmented answer for FAITHFULNESS.
Split the ANSWER into its factual claims. A claim is supported only if the CONTEXT states it
(numbers must match exactly; paraphrase is fine). Ignore citation markers like [2].

CONTEXT:
{context}

ANSWER:
{answer}

Return only JSON: {{"supported": <int>, "total": <int>, "unsupported_claims": [<short strings>]}}"""

CORRECT_PROMPT = """You are grading an answer against a reference answer written by an analyst.
Score 1.0 if the answer contains all key facts in the reference (same figures, same company, same period),
0.5 if it contains some key facts and nothing contradicts the reference, 0.0 if it misses them or contradicts it.
Extra correct detail is fine.

QUESTION: {question}
REFERENCE: {expected}
ANSWER: {answer}

Return only JSON: {{"score": <0, 0.5 or 1>, "reason": "<one sentence>"}}"""


def _judge(prompt: str) -> dict:
    text = graph._llm().invoke([("human", prompt)]).content or ""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def faithfulness(run, example):
    o = _out(run)
    if o.get("refused") or not o.get("context"):
        return {"key": "faithfulness", "score": None}
    j = _judge(FAITH_PROMPT.format(context=o["context"], answer=o["answer"]))
    total, sup = j.get("total"), j.get("supported")
    if not total:
        return {"key": "faithfulness", "score": None, "comment": "judge returned no claims"}
    return {"key": "faithfulness", "score": round(min(sup, total) / total, 3),
            "comment": "; ".join(j.get("unsupported_claims") or []) or "all claims supported"}


def correctness(run, example):
    exp = (_ref(example).get("expected_answer") or "").strip()
    if not exp or exp.upper() == "REFUSE":
        return {"key": "correctness", "score": None}
    o = _out(run)
    if o.get("refused"):
        return {"key": "correctness", "score": 0.0, "comment": "refused an answerable question"}
    j = _judge(CORRECT_PROMPT.format(question=(run.inputs or {}).get("question", ""), expected=exp,
                                     answer=o.get("answer", "")))
    s = j.get("score")
    return {"key": "correctness", "score": float(s) if s is not None else None, "comment": j.get("reason")}


EVALUATORS = [retrieval_hit, refusal_correct, faithfulness, correctness, latency, under_5s]
METRICS = ["retrieval_hit", "refusal_correct", "faithfulness", "correctness", "latency_s", "under_5s"]


# ---------------- summary ----------------
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(float(statistics.mean(xs)), 3) if xs else None


def _p95(xs):
    xs = sorted(x for x in xs if x is not None)
    return round(xs[min(len(xs) - 1, int(0.95 * len(xs)))], 2) if xs else None


def summarize(rows):
    by_cfg = defaultdict(list)
    for r in rows:
        by_cfg[r["config"]].append(r)
    fmt = lambda v: "–" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))
    lines = ["# Evaluation summary", "",
             f"{len({r['id'] for r in rows})} questions × {len(by_cfg)} configurations. "
             "Scores are means over the questions where the metric applies.", "",
             "## Overall", "",
             "| Config | Retrieval hit | Refusal correct | Faithfulness | Correctness | Latency p50 (s) | p95 (s) | ≤5s |",
             "|---|---|---|---|---|---|---|---|"]
    for cfg, rs in by_cfg.items():
        lat = [r["latency_s"] for r in rs]
        lines.append(f"| {cfg} | " + " | ".join(fmt(_mean([r[m] for r in rs])) for m in
                     ("retrieval_hit", "refusal_correct", "faithfulness", "correctness")) +
                     f" | {fmt(statistics.median([x for x in lat if x is not None]) if any(lat) else None)} "
                     f"| {fmt(_p95(lat))} | {fmt(_mean([r['under_5s'] for r in rs]))} |")
    cats = sorted({r["category"] for r in rows})
    for metric in ("retrieval_hit", "faithfulness", "correctness"):
        lines += ["", f"## {metric} by question category", "",
                  "| Config | " + " | ".join(cats) + " |", "|---" * (len(cats) + 1) + "|"]
        for cfg, rs in by_cfg.items():
            lines.append(f"| {cfg} | " + " | ".join(
                fmt(_mean([r[metric] for r in rs if r["category"] == c])) for c in cats) + " |")
    return "\n".join(lines) + "\n"


# ---------------- main ----------------
def main():
    from langsmith import Client, evaluate
    from src.retrieval import _bm25, _pc, _store, embed_query

    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--limit", type=int, help="only the first N questions (dry run)")
    ap.add_argument("--concurrency", type=int, default=4)
    a = ap.parse_args()

    client = Client()
    name = ensure_dataset(client)
    examples = list(client.list_examples(dataset_name=name))
    examples.sort(key=lambda e: (e.outputs or {}).get("id", ""))
    if a.limit:
        examples = examples[:a.limit]

    graph.GRAPH = graph.build_graph()  # build once before threads start
    for s in STRATEGIES:
        _store(s); _bm25(s)
    _pc(); embed_query("warm-up")

    configs = FULL if a.full else CORE
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for cfg in configs:
        s, r, rr = cfg
        print(f"\n=== {label(cfg)} ({len(examples)} questions) ===")
        res = evaluate(make_target(s, r, rr), data=examples, evaluators=EVALUATORS,
                       experiment_prefix=f"{s}-{r}-{'rr' if rr else 'norr'}",
                       metadata={"strategy": s, "retriever": r, "rerank": rr, "dataset": name},
                       max_concurrency=a.concurrency)
        for item in res:
            ex, run = item["example"], item["run"]
            scores = {e.key: e.score for e in item["evaluation_results"]["results"]}
            o = run.outputs or {}
            rows.append({"config": label(cfg), "strategy": s, "retriever": r, "rerank": rr,
                         "id": (ex.outputs or {}).get("id"), "category": (ex.outputs or {}).get("category"),
                         "question": (ex.inputs or {}).get("question"), "refused": o.get("refused"),
                         "refusal_reason": o.get("refusal_reason"),
                         **{m: scores.get(m) for m in METRICS},
                         "answer": (o.get("answer") or "")[:500]})
        done = [x for x in rows if x["config"] == label(cfg)]
        print("   " + " | ".join(f"{m}={_mean([x[m] for x in done])}" for m in METRICS))

    suffix = "_dryrun" if a.limit else ""
    with open(OUT / f"eval_rows{suffix}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT / f"eval_summary{suffix}.md").write_text(summarize(rows))
    print(f"\nWrote eval/results/eval_rows{suffix}.csv and eval_summary{suffix}.md")


if __name__ == "__main__":
    main()
