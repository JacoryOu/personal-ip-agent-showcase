"""Normalized string similarity for the memory subsystem."""

import difflib

def _compute_similarity(s1: str, s2: str) -> float:
    """Calculates normalized string similarity ratio."""
    norm1 = s1.strip().lower()
    norm2 = s2.strip().lower()
    if norm1 == norm2:
        return 1.0
    return difflib.SequenceMatcher(None, norm1, norm2).ratio()
