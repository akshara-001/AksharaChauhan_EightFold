"""
Merge module.
Merges multiple raw source records into a single canonical CandidateRecord.

Merge Policy
------------
Source priority (highest wins for scalar fields):
    1. resume   — candidate-authored, most recently updated
    2. github   — programmatically verifiable
    3. ats      — recruiter-entered (may have typos)
    4. csv      — bulk import (lowest control)

Field-specific rules:
    skills      : Union of all sources (GitHub weighted higher via confidence)
    emails      : Union of all sources, deduped, sorted
    phones      : Union of all sources, deduped, sorted
    experience  : Union from resume > ats (CSV/GitHub rarely have this)
    education   : Union from resume > ats
    links       : Merge dict; per-key first-available wins
    scalar fields (name, location, headline, candidate_id):
                  Highest priority source with non-null value wins.
"""
import hashlib
import logging
from typing import Any, Dict, List, Optional

from normalizers.phone import normalize_phones
from normalizers.skill import normalize_skill
from normalizers.date import normalize_date
from normalizers.name import normalize_name
from normalizers.email import normalize_emails
from merger.confidence import calculate_confidence, explain_confidence

logger = logging.getLogger(__name__)

# Ordered priority list (index 0 = highest priority)
SOURCE_PRIORITY: List[str] = ["resume", "github", "ats", "csv", "notes"]

# Fields that get GitHub's skill-priority override
_SKILL_PRIORITY: List[str] = ["github", "resume", "ats", "csv", "notes"]


def _priority(source: str) -> int:
    """Lower index = higher priority."""
    try:
        return SOURCE_PRIORITY.index(source.lower())
    except ValueError:
        return len(SOURCE_PRIORITY)


def _sort_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort records highest-priority first."""
    return sorted(records, key=lambda r: _priority(r.get("source", "unknown")))


def _pick_scalar(
    records: List[Dict[str, Any]],
    field: str,
    priority_order: Optional[List[str]] = None,
) -> tuple[Optional[Any], Optional[str]]:
    """
    Pick the best value for a scalar field.

    Returns:
        (value, source_name) or (None, None)
    """
    order = priority_order or SOURCE_PRIORITY
    for source in order:
        for r in records:
            if r.get("source", "").lower() == source and r.get(field):
                return r[field], source
    return None, None


def _build_skills(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Union skills across all sources, normalized and deduplicated.
    Returns list of skill objects with name, confidence, sources.
    """
    # skill_key (lowercased canonical) -> {name, sources}
    skill_map: Dict[str, Dict[str, Any]] = {}

    for r in records:
        src = r.get("source", "unknown")
        for raw_skill in r.get("skills", []):
            canonical = normalize_skill(raw_skill)
            if not canonical:
                continue
            key = canonical.lower()
            if key not in skill_map:
                skill_map[key] = {"name": canonical, "sources": []}
            if src not in skill_map[key]["sources"]:
                skill_map[key]["sources"].append(src)

    skills = []
    for data in skill_map.values():
        srcs = data["sources"]
        skills.append({
            "name":       data["name"],
            "confidence": calculate_confidence(srcs),
            "confidence_explanation": explain_confidence(srcs),
            "sources":    srcs,
        })

    # Sort: multi-source first, then by name
    skills.sort(key=lambda s: (-len(s["sources"]), s["name"].lower()))
    return skills


def _build_experience(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge experience entries from resume > ats, deduplicate by title+company."""
    seen: set = set()
    entries: List[Dict[str, Any]] = []

    for source in ["resume", "ats", "csv", "github"]:
        for r in records:
            if r.get("source", "").lower() != source:
                continue
            for exp in r.get("experience", []):
                title = (exp.get("title") or "").strip()
                company = (exp.get("company") or "").strip()
                key = (title.lower(), company.lower())
                if key in seen:
                    continue
                seen.add(key)
                entries.append({
                    "title":      title or None,
                    "company":    company or None,
                    "start":      normalize_date(exp.get("start", "")),
                    "end":        normalize_date(exp.get("end", "")) if exp.get("end", "").lower() not in ("present", "current", "now", "") else None,
                    "is_current": exp.get("end", "").lower() in ("present", "current", "now", ""),
                    "source":     source,
                })
    return entries


def _build_education(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge education entries, deduplicate by degree+institution."""
    seen: set = set()
    entries: List[Dict[str, Any]] = []

    for source in ["resume", "ats", "csv"]:
        for r in records:
            if r.get("source", "").lower() != source:
                continue
            for edu in r.get("education", []):
                degree = (edu.get("degree") or "").strip()
                institution = (edu.get("institution") or "").strip()
                key = (degree.lower(), institution.lower())
                if key in seen:
                    continue
                seen.add(key)
                entries.append({
                    "degree":      degree or None,
                    "institution": institution or None,
                    "year":        edu.get("year") or None,
                    "source":      source,
                })
    return entries


def _build_links(records: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    """Merge links dict; first non-null value per key wins (priority order)."""
    merged: Dict[str, Optional[str]] = {"github": None, "linkedin": None}
    for source in SOURCE_PRIORITY:
        for r in records:
            if r.get("source", "").lower() != source:
                continue
            links = r.get("links", {}) or {}
            for key in merged:
                if merged[key] is None and links.get(key):
                    merged[key] = links[key]
    return merged


def _build_provenance(records: List[Dict[str, Any]], final: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build provenance records documenting where each field's value came from.
    """
    prov: List[Dict[str, Any]] = []

    scalar_fields = ["full_name", "headline", "location", "candidate_id"]
    for field in scalar_fields:
        value = final.get(field)
        if value:
            for r in records:
                if r.get(field) == value:
                    prov.append({
                        "field":     field,
                        "source":    r["source"],
                        "method":    "priority_pick",
                        "raw_value": str(r[field]),
                    })
                    break

    # Emails
    for email in final.get("emails", []):
        for r in records:
            for raw_email in r.get("emails", []):
                if raw_email.lower().strip() == email:
                    prov.append({
                        "field":     "email",
                        "source":    r["source"],
                        "method":    "regex" if r["source"] == "resume" else "structured_field",
                        "raw_value": raw_email,
                    })
                    break

    # Phones
    for phone in final.get("phones", []):
        for r in records:
            for raw_phone in r.get("phones", []):
                prov.append({
                    "field":     "phone",
                    "source":    r["source"],
                    "method":    "regex" if r["source"] == "resume" else "structured_field",
                    "raw_value": raw_phone,
                })
                break

    # Skills
    for skill in final.get("skills", []):
        for src in skill.get("sources", []):
            prov.append({
                "field":     "skill",
                "source":    src,
                "method":    "section_extraction" if src == "resume" else "structured_field",
                "raw_value": skill["name"],
            })

    return prov


def _make_candidate_id(full_name: Optional[str], emails: List[str]) -> str:
    """Generate a deterministic candidate ID from name + primary email."""
    seed = f"{(full_name or '').lower().strip()}:{(emails[0] if emails else '').lower()}"
    return "cand_" + hashlib.sha256(seed.encode()).hexdigest()[:12]


def merge_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge a list of raw source records into a single canonical CandidateRecord.

    Args:
        records: List of raw dicts from parsers (may be empty or contain {}).

    Returns:
        Merged candidate dict. Never raises.
    """
    logger.info(f"[merge] Merging {len(records)} source record(s)")

    # Drop empty records
    valid = [r for r in records if r and isinstance(r, dict) and r.get("source")]
    if not valid:
        logger.warning("[merge] No valid records to merge; returning empty result")
        return _empty_candidate()

    sorted_records = _sort_records(valid)

    # --- Scalar fields (priority pick) ---
    full_name_raw, name_src = _pick_scalar(sorted_records, "full_name")
    full_name = normalize_name(full_name_raw) if full_name_raw else None

    headline, headline_src = _pick_scalar(sorted_records, "headline")
    location, location_src = _pick_scalar(sorted_records, "location")
    candidate_id_raw, _ = _pick_scalar(sorted_records, "candidate_id")

    # --- List fields (union + normalize) ---
    all_emails: List[str] = []
    all_phones: List[str] = []
    for r in sorted_records:
        all_emails.extend(r.get("emails", []))
        all_phones.extend(r.get("phones", []))

    emails = normalize_emails(all_emails)
    phones = normalize_phones(all_phones)

    # --- Skills ---
    skills = _build_skills(sorted_records)

    # --- Experience & Education ---
    experience = _build_experience(sorted_records)
    education = _build_education(sorted_records)

    # --- Links ---
    links = _build_links(sorted_records)

    # --- Candidate ID ---
    candidate_id = candidate_id_raw or _make_candidate_id(full_name, emails)

    # --- Overall confidence ---
    sources_present = list({r["source"] for r in sorted_records})
    from merger.confidence import calculate_confidence
    overall_confidence = calculate_confidence(sources_present)

    final: Dict[str, Any] = {
        "candidate_id":        candidate_id,
        "full_name":           full_name,
        "emails":              emails,
        "phones":              phones,
        "location":            location,
        "headline":            headline,
        "experience":          experience,
        "education":           education,
        "skills":              skills,
        "links":               links,
        "overall_confidence":  overall_confidence,
        "sources_used":        sorted(sources_present),
        "provenance":          [],  # filled below
    }

    final["provenance"] = _build_provenance(sorted_records, final)

    logger.info(
        f"[merge] Result: name={full_name!r}, emails={emails}, "
        f"phones={phones}, skills={len(skills)}, "
        f"overall_confidence={overall_confidence}"
    )
    return final


def _empty_candidate() -> Dict[str, Any]:
    return {
        "candidate_id":       None,
        "full_name":          None,
        "emails":             [],
        "phones":             [],
        "location":           None,
        "headline":           None,
        "experience":         [],
        "education":          [],
        "skills":             [],
        "links":              {"github": None, "linkedin": None},
        "overall_confidence": 0.0,
        "sources_used":       [],
        "provenance":         [],
    }
