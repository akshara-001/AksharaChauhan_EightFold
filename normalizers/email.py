"""
Email normalizer.
Lowercases and validates RFC-5322 email addresses.
Returns None for invalid emails.
"""
import logging
import re
from typing import Optional, List

logger = logging.getLogger(__name__)

# Simple RFC-5322 inspired pattern (covers 99% of real cases)
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def normalize_email(raw: str) -> Optional[str]:
    """
    Normalize an email address.

    Rules:
      - Strip whitespace
      - Lowercase
      - Validate format
      - Return None if invalid

    Args:
        raw: Raw email string from any source.

    Returns:
        Lowercased email string or None.
    """
    if not raw or not isinstance(raw, str):
        return None

    normalized = raw.strip().lower()
    if not normalized:
        return None

    # Try email-validator for strict RFC validation first
    try:
        from email_validator import validate_email, EmailNotValidError

        valid = validate_email(normalized, check_deliverability=False)
        return valid.normalized  # type: ignore
    except ImportError:
        pass  # fall back to regex
    except Exception:
        return None

    # Regex fallback
    if _EMAIL_RE.match(normalized):
        return normalized

    logger.debug(f"Invalid email rejected: {raw!r}")
    return None


def normalize_emails(raw_list: List[str]) -> List[str]:
    """Normalize a list of emails, deduplicate, drop invalids."""
    seen: set = set()
    result: List[str] = []
    for raw in raw_list:
        normed = normalize_email(raw)
        if normed and normed not in seen:
            seen.add(normed)
            result.append(normed)
    return result
