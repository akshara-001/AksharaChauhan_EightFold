"""
ATS Parser — Structured source.
Parses an Applicant Tracking System JSON record.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _coerce_list(value: Any) -> List[str]:
    """Coerce value to list of strings gracefully."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    if isinstance(value, str):
        return [s.strip() for s in re.split(r"[,;|]", value) if s.strip()]
    return []


def _parse_experience(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    entries = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entry = {
            "title":   item.get("title") or item.get("role") or None,
            "company": item.get("company") or item.get("employer") or None,
            "start":   item.get("start") or item.get("start_date") or None,
            "end":     item.get("end") or item.get("end_date") or "Present",
        }
        if entry["title"] or entry["company"]:
            entries.append(entry)
    return entries


def _parse_education(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    entries = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entry = {
            "degree":      item.get("degree") or item.get("qualification") or None,
            "institution": item.get("institution") or item.get("school") or item.get("university") or None,
            "year":        str(item.get("year") or item.get("graduation_year") or "") or None,
        }
        if entry["degree"] or entry["institution"]:
            entries.append(entry)
    return entries


def parse(path: str) -> Dict[str, Any]:
    """
    Parse an ATS JSON record file.

    Args:
        path: Path to the ATS JSON file.

    Returns:
        Raw candidate record dict. Returns {} on failure.
    """
    logger.info(f"[ats_parser] Parsing: {path}")

    try:
        with open(path, encoding="utf-8") as fh:
            data: Dict[str, Any] = json.load(fh)
    except FileNotFoundError:
        logger.warning(f"[ats_parser] File not found: {path!r}")
        return {}
    except json.JSONDecodeError as exc:
        logger.error(f"[ats_parser] Invalid JSON in {path!r}: {exc}")
        return {}
    except Exception as exc:
        logger.error(f"[ats_parser] Failed to read {path!r}: {exc}")
        return {}

    try:
        email = data.get("email", "")
        phone = data.get("phone", "")

        emails: List[str] = [email.strip().lower()] if email and email.strip() else []
        phones: List[str] = [phone.strip()] if phone and phone.strip() else []

        record: Dict[str, Any] = {
            "source": "ats",
            "candidate_id": data.get("id") or data.get("candidate_id") or None,
            "full_name":    data.get("name") or data.get("full_name") or None,
            "headline":     data.get("applied_role") or data.get("headline") or None,
            "emails":       emails,
            "phones":       phones,
            "location":     data.get("location") or data.get("city") or None,
            "skills":       _coerce_list(data.get("skills")),
            "experience":   _parse_experience(data.get("experience", [])),
            "education":    _parse_education(data.get("education", [])),
            "links": {
                "github":   data.get("github") or None,
                "linkedin": data.get("linkedin") or None,
            },
        }

        logger.info(
            f"[ats_parser] Extracted: name={record['full_name']!r}, "
            f"skills={len(record['skills'])}, exp={len(record['experience'])}"
        )
        return record

    except Exception as exc:
        logger.error(f"[ats_parser] Unexpected error: {exc}")
        return {}
