"""
Name normalizer.
Applies title-case and collapses whitespace.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Particles that should stay lowercase (unless first word)
_LOWER_PARTICLES = {"van", "de", "der", "von", "le", "la", "bin", "binti"}


def normalize_name(raw: str) -> Optional[str]:
    """
    Normalize a candidate's name.

    Rules:
      - Strip leading/trailing whitespace
      - Collapse internal whitespace (multiple spaces, tabs)
      - Title-case each word, except particles like 'de', 'van', etc.
      - Return None for empty/missing input

    Examples:
      "priyanshu choudhary" -> "Priyanshu Choudhary"
      "JOHN   DE SOUZA"     -> "John de Souza"
      "  "                  -> None
    """
    if not raw or not isinstance(raw, str):
        return None

    stripped = re.sub(r"\s+", " ", raw.strip())
    if not stripped:
        return None

    words = stripped.split()
    result = []
    for i, word in enumerate(words):
        lower = word.lower()
        if i == 0 or lower not in _LOWER_PARTICLES:
            result.append(word.capitalize())
        else:
            result.append(lower)

    return " ".join(result)
