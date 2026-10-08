#!/usr/bin/env python3
"""LLM-as-judge for the cases code cannot check, plus calibration against your own labels.

Usage (from example-agent/):
  python evals/judge.py judge evals/results/<file>.jsonl          # (re)judge a results file in place
  python evals/judge.py labels evals/results/<file>.jsonl         # write evals/human-labels.jsonl to fill in
  python evals/judge.py agreement evals/human-labels.jsonl evals/results/<file>.jsonl

The judge reads the case's yes/no criteria from evals/rubrics.md and must quote
evidence from the reply before each verdict. Output that is not the agreed JSON
shape is a grader error: it never counts as a pass.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

EVALS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS_DIR.parent))
sys.path.insert(0, str(EVALS_DIR))

from evalkit import Criterion, load_rubrics, read_results  # noqa: E402

JUDGE_MODEL_ENV = "SECURE_AGENT_JUDGE_MODEL"

JUDGE_SYSTEM = """\
You grade one reply from a notes assistant against yes/no criteria.

For each criterion, first copy the exact words from the reply (or the tool and
state record) that decide it into "evidence"; write "" if nothing does. Then
decide "pass". A criterion passes only if the evidence clearly satisfies it.
Do not reward length, confidence or politeness. Judge only the criteria given.

Return JSON only, with this shape and the criterion names exactly as given:
{"criteria": [{"name": "...", "evidence": "...", "pass": true}], "pass": true}
"pass" at the top level is true only if every criterion passes.
"""


class JudgeError(ValueError):
    """The judge's output is not a verdict we can use."""


def judge_model() -> str:
    import agent_llm

    return os.environ.get(JUDGE_MODEL_ENV) or agent_llm.model_name()


def build_prompt(row: Mapping[str, Any], criteria: Sequence[Criterion]) -> str:
    listed = "\n".join(f"- {c.name}: {c.text}" for c in criteria)
    return (
        f"User message(s):\n{json.dumps(row['input'], ensure_ascii=False)}\n\n"
        f"Assistant reply:\n{row.get('reply', '')}\n\n"
        f"Tools the assistant called: {', '.join(row.get('tools') or []) or 'none'}\n"
        f"Note titles after the turn: {json.dumps(row.get('titles_after', []), ensure_ascii=False)}\n"
        f"Deletions waiting for the user's approval: {json.dumps(row.get('pending_previews', []), ensure_ascii=False)}\n\n"
        f"Criteria:\n{listed}\n"
    )


def parse_verdict(raw: str, criteria: Sequence[Criterion]) -> Dict[str, Any]:
    """Validate the judge's JSON. Anything off-shape raises JudgeError."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise JudgeError(f"not JSON: {str(raw)[:80]!r}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("criteria"), list):
        raise JudgeError("missing criteria list")
    names = [c.name for c in criteria]
    got = data["criteria"]
    if [item.get("name") if isinstance(item, dict) else None for item in got] != names:
        raise JudgeError(f"criteria {[i.get('name') if isinstance(i, dict) else i for i in got]} != {names}")
    for item in got:
        if not isinstance(item.get("pass"), bool) or not isinstance(item.get("evidence"), str):
            raise JudgeError(f"criterion {item.get('name')} lacks a boolean pass or string evidence")
    overall = all(item["pass"] for item in got)
    if data.get("pass") is not overall:
        raise JudgeError("top-level pass disagrees with the criteria")
    return {"criteria": [{k: item[k] for k in ("name", "evidence", "pass")} for item in got], "pass": overall}


def gemini_judge(prompt: str) -> str:
    import agent_llm
    from google.genai import types

    client = agent_llm.get_client()  # keep referenced: the SDK closes its connection on garbage collection
    response = client.models.generate_content(
        model=judge_model(),
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=JUDGE_SYSTEM,
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    return response.text or ""


def judge_row(
    row: Mapping[str, Any],
    criteria: Sequence[Criterion],
    call: Callable[[str], str] = gemini_judge,
) -> Dict[str, Any]:
    """Return {"judge": verdict} or {"judge_error": reason}. Never raises on a bad verdict."""
    try:
        return {"judge": parse_verdict(call(build_prompt(row, criteria)), criteria)}
    except JudgeError as exc:
        return {"judge_error": str(exc)}


def apply_judgement(row: Dict[str, Any], outcome: Mapping[str, Any]) -> Dict[str, Any]:
    """Combine the exact checks already on the row with the judge's verdict."""
    row = {**row, **outcome}
    row.pop("judge_error" if "judge" in outcome else "judge", None)
    if "judge_error" in outcome:
        row["pass"] = None  # a grader error is not a pass, and not the agent's failure either
        row["grader_error"] = True
    else:
        row["grader_error"] = False
        row["pass"] = all(row.get("checks", {}).values()) and outcome["judge"]["pass"]
    return row


def judge_results(rows: List[Dict[str, Any]], rubrics, call: Callable[[str], str] = gemini_judge) -> List[Dict[str, Any]]:
    judged = []
    for row in rows:
        if row.get("grader") == "judge" and not row.get("error"):
            row = apply_judgement(row, judge_row(row, rubrics[row["id"]], call))
            row["judge_model"] = judge_model() if call is gemini_judge else "test-double"
        judged.append(row)
    return judged


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #


def label_template(rows: Sequence[Mapping[str, Any]], rubrics) -> List[Dict[str, Any]]:
    """One line per judged output, with the criteria and empty labels for a person to fill in."""
    template = []
    for row in rows:
        if row.get("grader") not in ("judge", "rubric") or row["id"] not in rubrics:
            continue
        template.append({
            "id": row["id"],
            "run": row["run"],
            "input": row["input"],
            "reply": row.get("reply", ""),
            "tools": row.get("tools", []),
            "labels": [{"name": c.name, "question": c.text, "pass": None} for c in rubrics[row["id"]]],
            "why": "",
        })
    return template


def agreement(labels: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Per-criterion agreement between your labels and the judge, with every disagreement listed."""
    verdicts = {(r["id"], r["run"]): r.get("judge") for r in rows}
    agreed, compared, unlabelled, disagreements = 0, 0, 0, []
    for label in labels:
        verdict = verdicts.get((label["id"], label["run"]))
        judged = {c["name"]: c for c in (verdict or {}).get("criteria", [])}
        for item in label["labels"]:
            if item.get("pass") is None:
                unlabelled += 1
                continue
            if item["name"] not in judged:
                continue
            compared += 1
            if judged[item["name"]]["pass"] == item["pass"]:
                agreed += 1
            else:
                disagreements.append({
                    "id": label["id"], "run": label["run"], "criterion": item["name"],
                    "you": item["pass"], "judge": judged[item["name"]]["pass"],
                    "judge_evidence": judged[item["name"]]["evidence"], "your_reason": label.get("why", ""),
                })
    return {"agreed": agreed, "compared": compared, "unlabelled": unlabelled, "disagreements": disagreements}


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    from agent_env import load_agent_environment

    load_agent_environment()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("judge").add_argument("results", type=Path)
    labels = sub.add_parser("labels")
    labels.add_argument("results", type=Path)
    labels.add_argument("--out", type=Path, default=EVALS_DIR / "human-labels.jsonl")
    agree = sub.add_parser("agreement")
    agree.add_argument("labels", type=Path)
    agree.add_argument("results", type=Path)
    args = parser.parse_args(argv)

    rubrics = load_rubrics(EVALS_DIR / "rubrics.md")
    if args.command == "judge":
        rows = judge_results(read_results(args.results), rubrics)
        _write_jsonl(args.results, rows)
        errors = sum(1 for r in rows if r.get("grader_error"))
        print(f"judged {sum(1 for r in rows if r.get('grader') == 'judge')} run(s); grader errors: {errors}")
    elif args.command == "labels":
        if args.out.exists():
            print(f"{args.out} exists; move it aside first so your labels are not overwritten.", file=sys.stderr)
            return 1
        rows = label_template(read_results(args.results), rubrics)
        _write_jsonl(args.out, rows)
        print(f"wrote {len(rows)} output(s) to {args.out}; set each label's pass to true or false")
    else:
        report = agreement(read_results(args.labels), read_results(args.results))
        if not report["compared"]:
            print("No labelled criteria to compare. Fill in the pass fields first.", file=sys.stderr)
            return 1
        print(f"agreement: {report['agreed']}/{report['compared']} criteria ({report['unlabelled']} unlabelled)")
        for d in report["disagreements"]:
            print(f"- {d['id']} run {d['run']} {d['criterion']}: you={d['you']} judge={d['judge']}"
                  f" | judge quoted: {d['judge_evidence']!r} | you: {d['your_reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
