"""Find a request setting that turns off hidden reasoning for the chat model.

Usage:  python -m src.check_reasoning
Prints reasoning tokens + latency for each option; copy the winning line into .env.
"""
import json
import time

from langchain_nebius import ChatNebius

from src.config import CHAT_MODEL

PROMPT = "In one sentence, what is interest rate risk for a bank?"
OPTIONS = {
    "baseline (no change)": {},
    'chat_template_kwargs thinking=false': {"extra_body": {"chat_template_kwargs": {"thinking": False}}},
    'chat_template_kwargs enable_thinking=false': {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
    'thinking type=disabled': {"extra_body": {"thinking": {"type": "disabled"}}},
    'reasoning_effort=low': {"reasoning_effort": "low"},
}


def main():
    print(f"model: {CHAT_MODEL}\n")
    for name, kw in OPTIONS.items():
        try:
            llm = ChatNebius(model=CHAT_MODEL, temperature=0, max_tokens=400, **kw)
            t0 = time.perf_counter()
            m = llm.invoke(PROMPT)
            dt = time.perf_counter() - t0
            u = m.usage_metadata or {}
            r = (u.get("output_token_details") or {}).get("reasoning", 0)
            print(f"{name:45} reasoning={r:<4} output={u.get('output_tokens'):<4} {dt:5.2f}s | {m.content[:60]!r}")
            if kw.get("extra_body") and not r:
                print(f"{'':45} -> .env: NEBIUS_CHAT_EXTRA_BODY='{json.dumps(kw['extra_body'])}'")
            if kw.get("reasoning_effort") and not r:
                print(f"{'':45} -> .env: NEBIUS_REASONING_EFFORT={kw['reasoning_effort']}")
        except Exception as e:
            print(f"{name:45} ERROR {type(e).__name__}: {str(e)[:100]}")


if __name__ == "__main__":
    main()
