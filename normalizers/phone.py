"""
Phone normalizer.
Converts any phone format to E.164 (e.g. +919876543210).
Returns None for unrecognizable/invalid numbers.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Default region for numbers without country code
DEFAULT_REGION = "IN"


def normalize_phone(raw: str, default_region: str = DEFAULT_REGION) -> Optional[str]:
    """
    Normalize a phone number string to E.164 format.

    Examples:
        "9876543210"       -> "+919876543210"
        "+91 9876543210"   -> "+919876543210"
        "91-9876543210"    -> "+919876543210"
        "(800) 555-1234"   -> "+18005551234"
        "not-a-phone"      -> None

    Args:
        raw: Raw phone string from any source.
        default_region: ISO 3166-1 alpha-2 region code to assume when
                        no country code is present.

    Returns:
        E.164 string or None if parsing fails.
    """
    if not raw or not isinstance(raw, str):
        return None

    raw = raw.strip()
    if not raw:
        return None

    try:
        import phonenumbers

        # phonenumbers needs a leading + for numbers that already have country code
        # but written without +  e.g. "919876543210"
        # Heuristic: if starts with 91 and is 12 digits, prepend +
        cleaned = re.sub(r"[\s\-().x]", "", raw)
        if re.match(r"^91\d{10}$", cleaned):
            raw = "+" + cleaned

        parsed = phonenumbers.parse(raw, default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
        else:
            logger.debug(f"Phone number invalid after parsing: {raw!r}")
            return None

    except Exception as e:
        logger.debug(f"Could not parse phone {raw!r}: {e}")
        return None


def normalize_phones(raw_list: list, default_region: str = DEFAULT_REGION) -> list:
    """Normalize a list of phone strings, dedup, drop Nones."""
    seen = set()
    result = []
    for raw in raw_list:
        normed = normalize_phone(raw, default_region)
        if normed and normed not in seen:
            seen.add(normed)
            result.append(normed)
    return result
