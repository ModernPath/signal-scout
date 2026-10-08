"""Pure eval logic: case and rubric loading, exact graders, statistics, comparison.

No model calls, no file writes. Everything here is unit-tested in
tests/test_evals.py, so the numbers the runner prints can be trusted before
they are used to judge the agent.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

CATEGORIES = ("ordinary", "edge", "ambiguous", "unanswerable", "hostile", "failure")
GRADERS = ("exact", "judge", "rubric")

# Every key an exact grader understands. A misspelt key would otherwise be
# ignored, and a case with no working check passes every run.
EXACT_CHECKS = (
    "tools_called",
    "tools_not_called",
    "note_count",
    "note_count_unchanged",
    "note_exists",
    "note_absent",
    "notes_kept",
    "reply_mentions",
    "reply_excludes",
    "used_llm",
    "pending_actions",
    "pending_preview_mentions",
    "pending_preview_excludes",
    "other_user_untouched",
)


class CaseError(ValueError):
    """A case or rubric file that cannot be trusted as written."""


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    input: Any  # a message, or a list of messages sent in one conversation
    expect: Mapping[str, Any]
    grader: str
    blocking: bool = False
    setup: Mapping[str, Any] = field(default_factory=dict)
    env: Mapping[str, str] = field(default_factory=dict)
    note: str = ""

    @property
    def messages(self) -> List[str]:
        return list(self.input) if isinstance(self.input, list) else [self.input]


def load_cases(path: Path, rubrics: Optional[Mapping[str, Sequence["Criterion"]]] = None) -> List[Case]:
    """Read cases.jsonl and refuse anything a run could silently misread."""
    cases: List[Case] = []
    seen = set()
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CaseError(f"{path}:{lineno}: not JSON ({exc})") from exc
        case = Case(
            id=row["id"],
            category=row["category"],
            input=row["input"],
            expect=row.get("expect", {}),
            grader=row["grader"],
            blocking=bool(row.get("blocking", False)),
            setup=row.get("setup", {}),
            env=row.get("env", {}),
            note=row.get("note", ""),
        )
        _validate(case, lineno, seen, rubrics)
        seen.add(case.id)
        cases.append(case)
    if not cases:
        raise CaseError(f"{path}: no cases")
    return cases


def _validate(case: Case, lineno: int, seen: set, rubrics) -> None:
    where = f"line {lineno} ({case.id})"
    if case.id in seen:
        raise CaseError(f"{where}: duplicate id")
    if case.category not in CATEGORIES:
        raise CaseError(f"{where}: unknown category {case.category!r}")
    if case.grader not in GRADERS:
        raise CaseError(f"{where}: unknown grader {case.grader!r}")
    unknown = set(case.expect) - set(EXACT_CHECKS)
    if unknown:
        raise CaseError(f"{where}: unknown expect key(s) {sorted(unknown)}; known: {', '.join(EXACT_CHECKS)}")
    if case.grader == "exact" and not case.expect:
        raise CaseError(f"{where}: an exact case needs at least one check, or it passes every run")
    if case.grader in ("judge", "rubric") and rubrics is not None and not rubrics.get(case.id):
        raise CaseError(f"{where}: grader {case.grader} needs criteria under '## {case.id}' in rubrics.md")


def category_counts(cases: Iterable[Case]) -> Dict[str, int]:
    counts = {c: 0 for c in CATEGORIES}
    for case in cases:
        counts[case.category] += 1
    return counts


# --------------------------------------------------------------------------- #
# Rubrics
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Criterion:
    name: str
    text: str


_RUBRIC_HEADING = re.compile(r"^##\s+(?P<id>[\w-]+)\s*$")
_RUBRIC_ITEM = re.compile(r"^-\s+`?(?P<name>[a-z0-9_]+)`?\s*[:—-]\s*(?P<text>.+)$")


def load_rubrics(path: Path) -> Dict[str, List[Criterion]]:
    """Parse rubrics.md: `## <case-id>` headings, each followed by `- name: yes/no question`."""
    rubrics: Dict[str, List[Criterion]] = {}
    current: Optional[str] = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        heading = _RUBRIC_HEADING.match(line)
        if heading:
            current = heading.group("id")
            rubrics[current] = []
            continue
        item = _RUBRIC_ITEM.match(line.strip())
        if current and item:
            rubrics[current].append(Criterion(item.group("name"), item.group("text").strip()))
    return rubrics


# --------------------------------------------------------------------------- #
# Exact graders
# --------------------------------------------------------------------------- #


@dataclass
class Observation:
    """Everything a run leaves behind that a grader may look at."""

    reply: str
    tools: List[str]
    notes_before: List[Mapping[str, Any]]
    notes_after: List[Mapping[str, Any]]
    used_llm: bool
    pending: List[Mapping[str, Any]] = field(default_factory=list)
    other_before: List[Mapping[str, Any]] = field(default_factory=list)
    other_after: List[Mapping[str, Any]] = field(default_factory=list)


def grade_exact(expect: Mapping[str, Any], obs: Observation) -> Dict[str, bool]:
    """Apply every exact check in `expect`. Returns {check: passed}."""
    results: Dict[str, bool] = {}
    titles_after = [n["title"].lower() for n in obs.notes_after]
    reply = obs.reply.lower()

    for key, want in expect.items():
        if key == "tools_called":
            results[key] = all(tool in obs.tools for tool in want)
        elif key == "tools_not_called":
            results[key] = not any(tool in obs.tools for tool in want)
        elif key == "note_count":
            results[key] = len(obs.notes_after) == want
        elif key == "note_count_unchanged":
            results[key] = (len(obs.notes_after) == len(obs.notes_before)) == bool(want)
        elif key == "note_exists":
            results[key] = any(_note_matches(n, want) for n in obs.notes_after)
        elif key == "note_absent":
            results[key] = not any(want["title_contains"].lower() in t for t in titles_after)
        elif key == "notes_kept":
            kept = {n["id"] for n in obs.notes_after}
            results[key] = all(note_id in kept for note_id in want)
        elif key == "reply_mentions":
            results[key] = all(text.lower() in reply for text in want)
        elif key == "reply_excludes":
            results[key] = not any(text.lower() in reply for text in want)
        elif key == "used_llm":
            results[key] = obs.used_llm == bool(want)
        elif key == "pending_actions":
            results[key] = len(obs.pending) == want
        elif key == "pending_preview_mentions":
            previews = " ".join(a["preview"] for a in obs.pending).lower()
            results[key] = bool(obs.pending) and all(text.lower() in previews for text in want)
        elif key == "pending_preview_excludes":
            previews = " ".join(a["preview"] for a in obs.pending).lower()
            results[key] = not any(text.lower() in previews for text in want)
        elif key == "other_user_untouched":
            results[key] = (obs.other_after == obs.other_before) == bool(want)
        else:  # load_cases rejects these; keep the grader honest if called directly
            raise CaseError(f"unknown exact check {key!r}")
    return results


def _note_matches(note: Mapping[str, Any], want: Mapping[str, Any]) -> bool:
    if "title_contains" in want and want["title_contains"].lower() not in note["title"].lower():
        return False
    if "body_contains" in want and want["body_contains"].lower() not in note.get("body", "").lower():
        return False
    return all(tag in note.get("tags", []) for tag in want.get("tags", []))


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    """Nearest-rank percentile: the smallest value with at least q% of runs at or below it."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


@dataclass
class CaseSummary:
    id: str
    category: str
    blocking: bool
    runs: int
    passed: int
    graded: int  # runs with a verdict; judge cases without a judge run have none
    grader_errors: int

    @property
    def pass_at_k(self) -> Optional[bool]:
        """At least one run passed."""
        return self.passed > 0 if self.graded else None

    @property
    def pass_hat_k(self) -> Optional[bool]:
        """Every run passed. Closer to what a user experiences than pass@k."""
        return self.passed == self.runs if self.graded == self.runs else None

    @property
    def label(self) -> str:
        return f"{self.passed}/{self.runs}" if self.graded == self.runs else f"{self.passed}/{self.graded} graded of {self.runs}"


def summarize(results: Sequence[Mapping[str, Any]], prices: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Per-case and overall numbers for one results file."""
    by_case: Dict[str, CaseSummary] = {}
    for row in results:
        s = by_case.setdefault(
            row["id"],
            CaseSummary(row["id"], row.get("category", ""), bool(row.get("blocking")), 0, 0, 0, 0),
        )
        s.runs += 1
        if row.get("pass") is not None:
            s.graded += 1
            s.passed += int(bool(row["pass"]))
        if row.get("grader_error"):
            s.grader_errors += 1

    cases = list(by_case.values())
    complete = [c for c in cases if c.graded == c.runs]
    ms = [row["ms"] for row in results if row.get("ms") is not None]
    tokens_in = sum(row.get("tokens_in") or 0 for row in results)
    tokens_out = sum(row.get("tokens_out") or 0 for row in results)
    models = sorted({row.get("model", "") for row in results})

    return {
        "models": models,
        "cases": cases,
        "runs": len(results),
        "graded_runs": sum(c.graded for c in cases),
        "passed_runs": sum(c.passed for c in cases),
        "pass_hat_k": sum(1 for c in complete if c.pass_hat_k),
        "complete_cases": len(complete),
        "ungraded_cases": [c.id for c in cases if c.graded < c.runs],
        "grader_errors": sum(c.grader_errors for c in cases),
        "blocking_failures": [c.id for c in cases if c.blocking and c.graded and c.passed < c.runs],
        "p50_ms": percentile(ms, 50),
        "p90_ms": percentile(ms, 90),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd(models, tokens_in, tokens_out, prices),
    }


def cost_usd(models: Sequence[str], tokens_in: int, tokens_out: int, prices: Optional[Mapping[str, Any]]) -> Optional[float]:
    """Tokens × dated price. None when the price for the run's model has not been filled in."""
    if not prices or len(models) != 1:
        return None
    entry = prices.get("models", {}).get(models[0])
    if not entry or entry.get("input_per_million") is None or entry.get("output_per_million") is None:
        return None
    return tokens_in / 1e6 * entry["input_per_million"] + tokens_out / 1e6 * entry["output_per_million"]


def compare(baseline: Sequence[Mapping[str, Any]], candidate: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Cases whose pass count changed between two results files. A flip is a case to rerun, not a verdict."""
    before = {c.id: c for c in summarize(baseline)["cases"]}
    after = {c.id: c for c in summarize(candidate)["cases"]}
    flips = []
    for case_id in sorted(before.keys() & after.keys()):
        b, a = before[case_id], after[case_id]
        if (b.passed, b.graded) != (a.passed, a.graded):
            flips.append({"id": case_id, "blocking": b.blocking, "baseline": b.label, "candidate": a.label,
                          "direction": "better" if a.passed > b.passed else "worse" if a.passed < b.passed else "changed"})
    missing = sorted(before.keys() ^ after.keys())
    if missing:
        flips.append({"id": ", ".join(missing), "blocking": False, "baseline": "", "candidate": "",
                      "direction": "not in both files"})
    return flips


def read_results(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
