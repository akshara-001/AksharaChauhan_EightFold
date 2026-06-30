"""
Confidence scoring module.

Formula: Probabilistic OR (independent evidence)
    confidence = 1 - ∏(1 - weight_i)   for each confirming source i

This models each source as an independent "witness": the more sources
that agree on a fact, the higher our confidence, even if each source
alone is imperfect.

Source weights represent baseline reliability:
    Resume    : 0.85 — candidate-authored, recent, but may exaggerate
    GitHub    : 0.90 — programmatically verified identity + skills
    ATS       : 0.80 — recruiter-entered, possible data-entry errors
    CSV       : 0.75 — bulk import, lowest editorial control
    Notes     : 0.50 — informal, subjective
"""
from typing import List, Optional

# Source name -> base reliability weight
SOURCE_WEIGHTS: dict[str, float] = {
    "resume":  0.85,
    "github":  0.90,
    "ats":     0.80,
    "csv":     0.75,
    "notes":   0.50,
}

_MAX_CONFIDENCE = 0.99  # never claim certainty


def calculate_confidence(sources: List[str]) -> float:
    """
    Calculate field confidence using Probabilistic OR.

    Args:
        sources: List of source names that confirmed this field/value.
                 Example: ["resume", "github"]

    Returns:
        Confidence score in [0.0, 0.99].
        Returns 0.0 for empty source list.

    Examples:
        ["resume"]              -> 0.85
        ["resume", "github"]   -> 1 - (0.15)(0.10) = 0.985 -> capped 0.99
        ["csv"]                 -> 0.75
        []                      -> 0.0
    """
    if not sources:
        return 0.0

    product = 1.0
    for source in sources:
        weight = SOURCE_WEIGHTS.get(source.lower(), 0.5)
        product *= (1.0 - weight)

    return min(round(1.0 - product, 4), _MAX_CONFIDENCE)


def explain_confidence(sources: List[str]) -> str:
    """
    Human-readable explanation of a confidence score.

    Returns a string like:
        "0.985 (resume ✓ 0.85, github ✓ 0.90) → Probabilistic OR"
    """
    if not sources:
        return "0.0 (no sources)"

    score = calculate_confidence(sources)
    parts = []
    for src in sources:
        w = SOURCE_WEIGHTS.get(src.lower(), 0.5)
        parts.append(f"{src} ✓ {w}")

    return f"{score} ({', '.join(parts)}) → Probabilistic OR"
