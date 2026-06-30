"""
CSV Parser — Structured source.
Parses recruiter CSV files into a list of raw candidate record dicts.
Handles flexible column naming conventions.
"""
import csv
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Column name aliases (lowercase)
_COL_ALIASES: Dict[str, set] = {
    "candidate_id": {"candidate_id", "id", "applicant_id"},
    "full_name":    {"full_name", "name", "candidate_name", "applicant_name"},
    "email":        {"email", "email_address", "e_mail", "mail"},
    "phone":        {"phone", "mobile", "phone_number", "contact", "cell"},
    "location":     {"location", "city", "address", "region"},
    "headline":     {"headline", "title", "current_role", "position"},
    "skills":       {"skills", "skill", "technologies", "tech_stack", "expertise"},
    "github":       {"github", "github_url", "github_profile"},
    "linkedin":     {"linkedin", "linkedin_url", "linkedin_profile"},
    "notes":        {"notes", "recruiter_notes", "comments", "remarks"},
}


def _resolve_columns(headers: List[str]) -> Dict[str, Optional[str]]:
    """Map logical field names to actual CSV column names."""
    header_lower = {h.lower().strip(): h for h in headers}
    resolved: Dict[str, Optional[str]] = {}
    for field, aliases in _COL_ALIASES.items():
        for alias in aliases:
            if alias in header_lower:
                resolved[field] = header_lower[alias]
                break
        else:
            resolved[field] = None
    return resolved


def _split_skills(raw: str) -> List[str]:
    if not raw:
        return []
    return [s.strip() for s in re.split(r"[,;|/]", raw) if s.strip()]


def parse(path: str) -> List[Dict[str, Any]]:
    """
    Parse a recruiter CSV file.

    Args:
        path: Path to the CSV file.

    Returns:
        List of raw candidate record dicts. Returns [] on any failure.
    """
    logger.info(f"[csv_parser] Parsing: {path}")
    records: List[Dict[str, Any]] = []

    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            headers: List[str] = list(reader.fieldnames or [])

            if not headers:
                logger.warning(f"[csv_parser] CSV has no headers: {path!r}")
                return []

            cols = _resolve_columns(headers)
            logger.debug(f"[csv_parser] Column mapping: {cols}")

            for row_num, row in enumerate(reader, start=2):
                try:
                    def get(field: str) -> str:
                        col = cols.get(field)
                        return row.get(col, "").strip() if col else ""

                    email_raw = get("email")
                    phone_raw = get("phone")
                    skills_raw = get("skills")

                    record: Dict[str, Any] = {
                        "source": "csv",
                        "candidate_id": get("candidate_id") or None,
                        "full_name": get("full_name") or None,
                        "emails": [email_raw.lower()] if email_raw else [],
                        "phones": [phone_raw] if phone_raw else [],
                        "location": get("location") or None,
                        "headline": get("headline") or None,
                        "skills": _split_skills(skills_raw),
                        "experience": [],
                        "education": [],
                        "links": {
                            "github": get("github") or None,
                            "linkedin": get("linkedin") or None,
                        },
                        "_notes": get("notes") or None,
                    }
                    records.append(record)

                except Exception as row_err:
                    logger.warning(f"[csv_parser] Skipping row {row_num}: {row_err}")
                    continue

        logger.info(f"[csv_parser] Parsed {len(records)} record(s)")

    except FileNotFoundError:
        logger.warning(f"[csv_parser] File not found: {path!r}")
    except Exception as exc:
        logger.error(f"[csv_parser] Failed to parse {path!r}: {exc}")

    return records
