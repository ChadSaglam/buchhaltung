from __future__ import annotations

import re
from difflib import SequenceMatcher


def normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def similarity(a: str, b: str) -> float:
    """Return 0..1 similarity score between two vendor strings."""
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def find_best_match(
    vendor: str,
    candidates: list[str],
    threshold: float = 0.72,
) -> tuple[str, float] | None:
    """
    Fuzzy-match vendor against known candidates.
    Returns (best_match, score) or None if below threshold.
    """
    best: tuple[str, float] | None = None
    for candidate in candidates:
        score = similarity(vendor, candidate)
        if score >= threshold and (best is None or score > best[1]):
            best = (candidate, score)
    return best