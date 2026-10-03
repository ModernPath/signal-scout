"""Pure, conservative conversation grouping and explainable ranking."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

STOP = {"a", "an", "and", "are", "as", "at", "by", "for", "from", "in", "is",
        "new", "of", "on", "or", "the", "to", "with", "about", "how", "why",
        "launches", "launched", "releases", "released", "unveils", "announces", "ai"}
WEIGHTS = {"relevance": 0.30, "velocity": 0.25, "novelty": 0.25, "pov_fit": 0.20}


def terms(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", (value or "").casefold())
            if len(word) > 2 and word not in STOP}


def similarity(left: str, right: str) -> float:
    a, b = terms(left), terms(right)
    if not a or not b:
        return 0.0
    return max(len(a & b) / len(a | b), SequenceMatcher(None, " ".join(sorted(a)),
                                                     " ".join(sorted(b))).ratio() * 0.75)


def cluster_signals(signals: list[dict], *, max_days: int = 14) -> list[dict]:
    """Join only specific, close title matches; topics alone never cause a merge."""
    groups: list[dict] = []
    for item in sorted(signals, key=lambda row: row["id"]):
        target = None
        for group in groups:
            for other in group["signals"]:
                left, right = item.get("published_at"), other.get("published_at")
                if left and right and abs((left - right).days) > max_days:
                    continue
                shared = terms(item["title"]) & terms(other["title"])
                if len(shared) >= 2 and similarity(item["title"], other["title"]) >= 0.55:
                    target = group
                    break
            if target:
                break
        if target:
            target["signals"].append(item)
            target["signal_ids"].append(item["id"])
            target["reason"] = "Shared specific title terms within the time window"
        else:
            groups.append({"signal_ids": [item["id"]], "signals": [item],
                           "reason": "No confident related signal"})
    return groups


def rank_conversation(signals: list[dict], brief: dict | None, prior_content: list[dict],
                      now: datetime, *, topics: tuple[str, ...] = ()) -> dict:
    if not signals:
        raise ValueError("Conversation has no signals")
    corpus = " ".join(str(s.get("title", "")) + " " + str(s.get("snippet", ""))
                      for s in signals)
    words = terms(corpus)
    monitored = set().union(*(terms(t) for t in topics)) if topics else set()
    relevance = min(100, 35 + 20 * len(words & monitored) + 10 * len(signals))

    recent = sum(1 for s in signals if s.get("published_at") and
                 now - timedelta(days=3) <= s["published_at"] <= now)
    prior = sum(1 for s in signals if s.get("published_at") and
                now - timedelta(days=10) <= s["published_at"] < now - timedelta(days=3))
    velocity = None if prior == 0 else min(100, round(50 + 25 * (recent / 3 - prior / 7)))
    velocity = max(0, velocity) if velocity is not None else None

    matches = []
    for content in prior_content:
        score = similarity(corpus, f"{content.get('title', '')} {content.get('text', '')}")
        if score >= 0.25:
            matches.append({"id": content.get("id"), "title": content.get("title"),
                            "similarity": round(score, 3)})
    matches.sort(key=lambda row: row["similarity"], reverse=True)
    novelty = None if not prior_content else round(100 * (1 - matches[0]["similarity"])) if matches else 100

    pov_fit = None
    if brief and all(str(brief.get(key, "")).strip() for key in
                     ("description", "audience", "expertise", "point_of_view", "voice")):
        context = terms(" ".join(str(brief[key]) for key in
                                 ("description", "audience", "expertise", "point_of_view")))
        pov_fit = min(100, round(100 * len(words & context) / max(1, min(4, len(context)))))
    components = {"relevance": relevance, "velocity": velocity,
                  "novelty": novelty, "pov_fit": pov_fit}
    known_weight = sum(WEIGHTS[key] for key, value in components.items() if value is not None)
    total = round(sum(value * WEIGHTS[key] for key, value in components.items()
                      if value is not None) / known_weight) if known_weight else 0
    evidence_ids = sorted({si["id"] for s in signals for si in s.get("source_items", ())})
    why_now = (f"{recent} signal(s) in the last 3 days; " +
               (f"velocity score {velocity}." if velocity is not None else
                "velocity is unknown without earlier activity."))
    if pov_fit is None:
        why_us = "Unavailable until a complete company brief is supplied."
    elif pov_fit < 50:
        why_us = "Company fit is weak; review whether this relates to stated expertise."
    else:
        why_us = f"Relevant to company expertise: {brief['expertise']}."
    angle = ("Build on prior content with a distinct claim; review the cited match." if matches else
             "Explore the specific development and its implications for the stated audience.")
    return {"components": components, "total": total,
            "confidence": round(known_weight, 2), "why_now": why_now,
            "why_us": why_us, "angle": angle, "evidence_source_item_ids": evidence_ids,
            "prior_content_matches": matches[:3]}
