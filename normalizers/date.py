"""
Date normalizer.
Converts various date formats to ISO YYYY-MM.
Returns None for unparseable input.

Supported inputs:
    "Jan 2023", "January 2023", "01/2023", "2023-01", "2023",
    "01-2023", "Q1 2023" -> "2023-01"
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}

QUARTER_MAP = {"q1": "01", "q2": "04", "q3": "07", "q4": "10"}

# Patterns tried in order
_PATTERNS = [
    # 2023-01 or 2023-1
    (re.compile(r"^(\d{4})[.\-/](\d{1,2})$"), lambda m: f"{m.group(1)}-{int(m.group(2)):02d}"),
    # 01/2023 or 1/2023
    (re.compile(r"^(\d{1,2})[.\-/](\d{4})$"), lambda m: f"{m.group(2)}-{int(m.group(1)):02d}"),
    # Jan 2023 / January 2023
    (
        re.compile(r"^([a-zA-Z]+)\.?\s+(\d{4})$"),
        lambda m: (
            f"{m.group(2)}-{MONTH_MAP[m.group(1).lower()[:3]]}"
            if m.group(1).lower()[:3] in MONTH_MAP else None
        ),
    ),
    # 2023 Jan / 2023 January
    (
        re.compile(r"^(\d{4})\s+([a-zA-Z]+)$"),
        lambda m: (
            f"{m.group(1)}-{MONTH_MAP[m.group(2).lower()[:3]]}"
            if m.group(2).lower()[:3] in MONTH_MAP else None
        ),
    ),
    # Q1 2023
    (
        re.compile(r"^(Q[1-4])\s*(\d{4})$", re.IGNORECASE),
        lambda m: (
            f"{m.group(2)}-{QUARTER_MAP[m.group(1).lower()]}"
        ),
    ),
    # Year only: 2023
    (re.compile(r"^(\d{4})$"), lambda m: f"{m.group(1)}-01"),
]


def normalize_date(raw: str) -> Optional[str]:
    """
    Normalize a date string to YYYY-MM.

    Args:
        raw: Raw date string from any source.

    Returns:
        "YYYY-MM" string or None if parsing fails.
    """
    if not raw or not isinstance(raw, str):
        return None

    raw = raw.strip()
    if not raw or raw.lower() in ("present", "current", "now", "ongoing", "-", "–"):
        return None

    # Try regex patterns
    for pattern, formatter in _PATTERNS:
        m = pattern.match(raw)
        if m:
            try:
                result = formatter(m)
                if result:
                    return result
            except (KeyError, ValueError):
                continue

    # Fallback: try dateutil
    try:
        from dateutil import parser as du_parser

        dt = du_parser.parse(raw, default=None)  # type: ignore
        if dt:
            return dt.strftime("%Y-%m")
    except Exception:
        pass

    logger.debug(f"Could not parse date: {raw!r}")
    return None
