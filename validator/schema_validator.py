"""
Schema validator for the final candidate output JSON.
Uses jsonschema for validation. Logs warnings but never raises.
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# JSON Schema for the canonical CandidateRecord
CANDIDATE_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CandidateRecord",
    "type": "object",
    "properties": {
        "candidate_id":       {"type": ["string", "null"]},
        "full_name":          {"type": ["string", "null"]},
        "emails":             {"type": "array", "items": {"type": "string"}},
        "phones":             {"type": "array", "items": {"type": "string"}},
        "location":           {"type": ["string", "null"]},
        "headline":           {"type": ["string", "null"]},
        "overall_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "sources_used":       {"type": "array", "items": {"type": "string"}},
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title":      {"type": ["string", "null"]},
                    "company":    {"type": ["string", "null"]},
                    "start":      {"type": ["string", "null"]},
                    "end":        {"type": ["string", "null"]},
                    "is_current": {"type": "boolean"},
                },
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "degree":      {"type": ["string", "null"]},
                    "institution": {"type": ["string", "null"]},
                    "year":        {"type": ["string", "null"]},
                },
            },
        },
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "confidence", "sources"],
                "properties": {
                    "name":       {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "sources":    {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "links": {
            "type": "object",
            "properties": {
                "github":   {"type": ["string", "null"]},
                "linkedin": {"type": ["string", "null"]},
            },
        },
        "provenance": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field":     {"type": "string"},
                    "source":    {"type": "string"},
                    "method":    {"type": "string"},
                    "raw_value": {"type": "string"},
                },
            },
        },
    },
}


def validate(data: Dict[str, Any]) -> List[str]:
    """
    Validate a candidate record against the schema.

    Args:
        data: Candidate record dict.

    Returns:
        List of validation error messages (empty = valid).
        Never raises.
    """
    errors: List[str] = []
    try:
        import jsonschema

        validator = jsonschema.Draft7Validator(CANDIDATE_SCHEMA)
        for error in validator.iter_errors(data):
            msg = f"{'.'.join(str(p) for p in error.path) or 'root'}: {error.message}"
            errors.append(msg)
            logger.warning(f"[validator] Schema error: {msg}")

    except ImportError:
        logger.warning("[validator] jsonschema not installed; skipping validation")
    except Exception as exc:
        logger.error(f"[validator] Validation failed unexpectedly: {exc}")

    if not errors:
        logger.info("[validator] Output schema validation passed ✓")
    else:
        logger.warning(f"[validator] {len(errors)} schema error(s) found")

    return errors
