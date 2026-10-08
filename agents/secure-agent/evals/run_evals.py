#!/usr/bin/env python3
"""Run the eval cases against the real Secure Agent and save one line per run.

Usage (from example-agent/):
  python evals/run_evals.py --limit 2                    # smoke run: two cases, real model
  python evals/run_evals.py --label baseline             # every case, 3 runs each
  python evals/run_evals.py --label baseline --judge     # ...and grade judge cases with the LLM judge
  EXAMPLE_AGENT_MODEL=<other> python evals/run_evals.py --label <other> --judge
  python evals/run_evals.py --compare evals/results/A.jsonl evals/results/B.jsonl
  python evals/run_evals.py --summary evals/results/A.jsonl
  python evals/run_evals.py --offline --limit 3          # exercise the runner without a model

Each run starts from an empty, throwaway data directory with the case's
planted notes, so runs never touch your own notes or each other. Results go to
evals/results/<date>-<label>.jsonl.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional

EVALS_DIR = Path(__file__).resolve().parent
AGENT_DIR = EVALS_DIR.parent
sys.path.insert(0, str(AGENT_DIR))
sys.path.insert(0, str(EVALS_DIR))

from evalkit import (  # noqa: E402
    Case,
    Observation,
    category_counts,
    compare,
    grade_exact,
    load_cases,
    load_rubrics,
    read_results,
    summarize,
)

CASES = EVALS_DIR / "cases.jsonl"
RUBRICS = EVALS_DIR / "rubrics.md"
PRICES = EVALS_DIR / "prices.json"
RESULTS_DIR = EVALS_DIR / "results"
OFFLINE_MODEL_LABEL = "offline-router"
EVAL_USER = "eval-user"
OTHER_USER = "other-user"  # owns setup.other_notes; the eval user must never reach them


@contextlib.contextmanager
def case_environment(case: Case) -> Iterator[Path]:
    """A fresh data dir with the case's planted notes, and the case's env overrides."""
    from memory.memory import DATA_DIR_ENV

    overrides = {**case.env}
    saved = {key: os.environ.get(key) for key in [*overrides, DATA_DIR_ENV]}
    with tempfile.TemporaryDirectory(prefix="eval-") as tmp:
        data_dir = Path(tmp) / "data"
        os.environ.update(overrides)
        os.environ[DATA_DIR_ENV] = str(data_dir)  # the summarizer subagent reads it too
        try:
            yield data_dir
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def plant(store, owner: str, notes: List[Mapping[str, Any]]) -> None:
    from example_core import Note, normalize_tags, utc_now

    for i, row in enumerate(notes):
        store.add(Note(
            id=row.get("id", f"note_plant{i:04d}"),
            owner=owner,
            title=row["title"],
            body=row.get("body", ""),
            tags=normalize_tags(row.get("tags")),
            created_at=row.get("created_at", utc_now()),
        ))


def run_case(case: Case, run: int, *, offline: bool) -> Dict[str, Any]:
    """Send the case's message(s) through chat_reply and grade what it left behind."""
    import agent_llm
    from example_chat import chat_reply
    from memory.memory import NoteStore

    # The run's model, read before the case's own env overrides: fail-02 swaps in a
    # model that does not exist, and that name must not become the run's label.
    model = OFFLINE_MODEL_LABEL if offline else agent_llm.model_name()
    with case_environment(case) as data_dir:
        store = NoteStore(data_dir)
        plant(store, EVAL_USER, case.setup.get("notes", []))
        plant(store, OTHER_USER, case.setup.get("other_notes", []))
        before = [n.to_dict() for n in store.all(EVAL_USER)]
        other_before = [n.to_dict() for n in store.all(OTHER_USER)]
        row: Dict[str, Any] = {
            "id": case.id, "run": run, "category": case.category, "grader": case.grader,
            "blocking": case.blocking, "input": case.input, "model": model,
        }
        tools: List[str] = []
        replies: List[str] = []
        used_llm = []
        pending: List[Dict[str, Any]] = []
        usage = None
        history: List[Dict[str, str]] = []
        start = time.perf_counter()
        try:
            with (contextlib.nullcontext() if offline else _usage()) as usage:
                for message in case.messages:
                    result = chat_reply(store, EVAL_USER, message, history=history, offline=offline)
                    history = result.history
                    tools.extend(result.tools_used)
                    pending.extend(result.pending_actions)
                    replies.append(result.reply)
                    used_llm.append(result.used_llm)
        except Exception as exc:  # noqa: BLE001 — a crash is a failed run, recorded with its reason
            row["error"] = f"{type(exc).__name__}: {exc}"
        row["ms"] = round((time.perf_counter() - start) * 1000)

        after = [n.to_dict() for n in store.all(EVAL_USER)]
        other_after = [n.to_dict() for n in store.all(OTHER_USER)]
        reply = "\n\n".join(replies)
        checks = grade_exact(case.expect, Observation(
            reply, tools, before, after, all(used_llm) and bool(used_llm),
            pending=pending, other_before=other_before, other_after=other_after,
        ))
        row.update({
            "tools": tools,
            "used_llm": all(used_llm) and bool(used_llm),
            "tokens_in": usage.tokens_in if usage else 0,
            "tokens_out": usage.tokens_out if usage else 0,
            "model_calls": usage.calls if usage else 0,
            "checks": checks,
            "reply": reply,
            "titles_after": [n["title"] for n in after],
            "pending_previews": [a["preview"] for a in pending],
        })
        if row.get("error") or not all(checks.values()):
            row["pass"] = False  # a failed exact check fails the run whatever a judge would say
        elif case.grader == "exact":
            row["pass"] = True
        else:
            row["pass"] = None  # judge: graded by evals/judge.py; rubric: graded by a person
        return row


def _usage():
    from usage import count_usage

    return count_usage()


def print_summary(rows: List[Dict[str, Any]], *, title: str, prices: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    s = summarize(rows, prices)
    print(f"\n{title} — model {', '.join(s['models'])}")
    print(f"{'case':<14}{'category':<14}{'runs passed':<16}blocking")
    for c in s["cases"]:
        print(f"{c.id:<14}{c.category:<14}{c.label:<16}{'BLOCKING' if c.blocking else ''}")
    print(f"\npassed runs: {s['passed_runs']}/{s['graded_runs']} graded ({s['runs']} total)")
    print(f"cases passing every run (pass^k): {s['pass_hat_k']}/{s['complete_cases']}")
    print(f"blocking failures: {', '.join(s['blocking_failures']) or 'none'}")
    if s["ungraded_cases"]:
        print(f"not graded yet: {', '.join(s['ungraded_cases'])} (judge: run with --judge; rubric: a person grades)")
    if s["grader_errors"]:
        print(f"grader errors (not counted as passes): {s['grader_errors']}")
    if s["p90_ms"] is not None:
        print(f"latency p50 {s['p50_ms'] / 1000:.1f} s, p90 {s['p90_ms'] / 1000:.1f} s")
    print(f"tokens in {s['tokens_in']}, out {s['tokens_out']}")
    cost = s["cost_usd"]
    print(f"cost: {'$%.4f' % cost if cost is not None else 'n/a — add dated prices for this model to evals/prices.json'}")

    fell_back = [r["id"] for r in rows if r.get("model") != OFFLINE_MODEL_LABEL and not r.get("used_llm")
                 and r.get("checks", {}).get("used_llm") is None]
    if fell_back:
        print(f"WARNING: {len(fell_back)} run(s) were answered by the offline router, not the model "
              f"({', '.join(sorted(set(fell_back)))}). Check the key and model name before trusting these numbers.")
    return s


def load_prices() -> Optional[Dict[str, Any]]:
    return json.loads(PRICES.read_text(encoding="utf-8")) if PRICES.exists() else None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trials", type=int, default=3, help="runs per case (default 3)")
    parser.add_argument("--limit", type=int, help="run only the first N cases")
    parser.add_argument("--cases", help="comma-separated case ids to run")
    parser.add_argument("--label", help="results file name part (default: the model name)")
    parser.add_argument("--out", type=Path, help="explicit results file")
    parser.add_argument("--offline", action="store_true", help="use the offline router instead of a model")
    parser.add_argument("--judge", action="store_true", help="grade judge cases with evals/judge.py after the runs")
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("BASELINE", "CANDIDATE"))
    parser.add_argument("--summary", type=Path, metavar="RESULTS", help="print the summary of a saved results file")
    args = parser.parse_args(argv)

    prices = load_prices()
    if args.compare:
        base, cand = (read_results(p) for p in args.compare)
        print_summary(base, title=f"BASELINE {args.compare[0].name}", prices=prices)
        print_summary(cand, title=f"CANDIDATE {args.compare[1].name}", prices=prices)
        flips = compare(base, cand)
        print("\ncases that changed (rerun these before drawing a conclusion):")
        for f in flips or [{"id": "none"}]:
            print(f"- {f['id']}: {f.get('baseline', '')} -> {f.get('candidate', '')} {f.get('direction', '')}"
                  f"{' BLOCKING' if f.get('blocking') else ''}")
        return 0
    if args.summary:
        print_summary(read_results(args.summary), title=args.summary.name, prices=prices)
        return 0

    from agent_env import load_agent_environment
    import agent_llm

    load_agent_environment()
    if args.offline:
        os.environ[agent_llm.OFFLINE_ENV] = "1"
    elif not agent_llm.llm_available():
        print("No model available: set GEMINI_API_KEY (and unset EXAMPLE_AGENT_OFFLINE), or pass --offline.",
              file=sys.stderr)
        return 2

    rubrics = load_rubrics(RUBRICS)
    cases = load_cases(CASES, rubrics)
    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [c for c in cases if c.id in wanted]
    if args.limit:
        cases = cases[: args.limit]

    model = OFFLINE_MODEL_LABEL if args.offline else agent_llm.model_name()
    label = args.label or model
    out = args.out or RESULTS_DIR / f"{date.today().isoformat()}-{label}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    counts = ", ".join(f"{k} {v}" for k, v in category_counts(cases).items() if v)
    print(f"{len(cases)} case(s) × {args.trials} run(s) with {model} -> {out}\n({counts})")

    rows: List[Dict[str, Any]] = []
    with out.open("w", encoding="utf-8") as fh:
        for case in cases:
            for run in range(1, args.trials + 1):
                row = run_case(case, run, offline=args.offline)
                rows.append(row)
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                mark = {True: "pass", False: "FAIL", None: "to grade"}[row["pass"]]
                print(f"  {case.id} run {run}: {mark}  tools={','.join(row['tools']) or '-'}  {row['ms']} ms"
                      + (f"  error={row['error']}" if row.get("error") else ""))

    if args.judge and not args.offline:
        import judge

        rows = judge.judge_results(rows, rubrics)
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    print_summary(rows, title=out.name, prices=prices)
    return 0


if __name__ == "__main__":
    sys.exit(main())
