"""
Config Projection module.
Remaps fields in the merged candidate record according to a user-provided
config — no code changes required, just edit config.json.

─────────────────────────────────────────────────────────────────────────────
REQUIRED TWIST — Configurable Output
─────────────────────────────────────────────────────────────────────────────
The pipeline accepts a runtime config that reshapes the output using the
same engine — no code changes required.  The config can:

  • Select a subset of fields to include.
  • Rename / remap a field from a canonical path (the "from" key).
  • Set per-field normalization (e.g. E.164 for phones, canonical for skills).
  • Toggle provenance and confidence on or off.
  • Choose what to do when a value is missing: null | omit | error.
  • Mark fields as required (raises ConfigError when required+missing+error).

Full config format (config.json):
    {
        "fields": [
            { "path": "full_name",     "type": "string",   "required": true },
            { "path": "primary_email", "from": "emails[0]", "type": "string", "required": true },
            { "path": "phone",         "from": "phones[0]", "type": "string", "normalize": "E164" },
            { "path": "skills",        "from": "skills[].name", "type": "string[]", "normalize": "canonical" }
        ],
        "include_confidence": true,
        "on_missing": "null"
    }

Field entry keys:
    path        (required) Output field name in the projected record.
    from        (optional) Source expression; defaults to same name as path.
    type        (optional) Type coercion: "string" | "number" | "boolean"
                           | "string[]" | "number[]"
    normalize   (optional) Post-resolution normalization:
                           "E164"      → phone → E.164
                           "canonical" → skill → canonical name
                           "lowercase" → str.lower()
                           "uppercase" → str.upper()
                           "titlecase" → str.title()
    required    (optional) bool.  When true and value is missing:
                           • on_missing="omit"  → field silently omitted
                           • on_missing="error" → ConfigProjectionError raised
                           • on_missing="null"  → null written (logged warning)

Top-level config keys:
    include_confidence  bool  (default true)  — keep overall_confidence in output.
    include_provenance  bool  (default false) — keep provenance list in output.
    on_missing          str   (default "null") — "null" | "omit" | "error"

Supported 'from' expression syntax:
    "full_name"         → scalar field
    "emails[0]"         → first element of a list
    "skills[0].name"    → sub-field of the first element of a list
    "links.github"      → nested dict access
    "skills[].name"     → collect sub-field from EVERY element of a list
                          → returns a list of values (used with type "string[]")
─────────────────────────────────────────────────────────────────────────────
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Expression regexes ────────────────────────────────────────────────────────
# "field[N].subfield" or "field[N]"
_INDEX_RE    = re.compile(r"^(\w+)\[(\d+)\](?:\.(\w+))?$")
# "field[].subfield" — collect from all list items
_COLLECT_RE  = re.compile(r"^(\w+)\[\](?:\.(\w+))?$")
# "field.subfield"
_NESTED_RE   = re.compile(r"^(\w+)\.(\w+)$")


class ConfigProjectionError(RuntimeError):
    """Raised when a required field is missing and on_missing='error'."""


# ── Expression resolver ───────────────────────────────────────────────────────

def _resolve(data: Dict[str, Any], expr: str) -> Any:
    """
    Resolve a dot/index access expression against a dict.

    Returns None if any part of the path is missing or out of range.
    Returns a list when the expression uses [] (collect-all).
    Never raises.
    """
    if not expr or not isinstance(expr, str):
        return None

    try:
        # "field[].subfield" — collect subfield from all list items
        m = _COLLECT_RE.match(expr)
        if m:
            field, subfield = m.group(1), m.group(2)
            lst = data.get(field)
            if not isinstance(lst, list):
                return None
            if subfield:
                return [item.get(subfield) for item in lst
                        if isinstance(item, dict) and item.get(subfield) is not None]
            return lst

        # "field[N].subfield" or "field[N]"
        m = _INDEX_RE.match(expr)
        if m:
            field, idx_str, subfield = m.group(1), m.group(2), m.group(3)
            lst = data.get(field)
            if not isinstance(lst, list):
                return None
            idx = int(idx_str)
            if idx >= len(lst):
                return None
            item = lst[idx]
            if subfield:
                return item.get(subfield) if isinstance(item, dict) else None
            return item

        # "field.subfield"
        m2 = _NESTED_RE.match(expr)
        if m2:
            field, subfield = m2.group(1), m2.group(2)
            parent = data.get(field)
            if isinstance(parent, dict):
                return parent.get(subfield)
            return None

        # plain "field"
        return data.get(expr)

    except Exception as exc:
        logger.debug(f"[projector] Failed to resolve {expr!r}: {exc}")
        return None


# ── Per-field normalizers ─────────────────────────────────────────────────────

def _apply_normalize(value: Any, mode: str) -> Any:
    """
    Apply a named normalization to a resolved value.

    Supports scalar values and lists transparently.

    modes:
        E164      → phone number → E.164
        canonical → skill name  → canonical
        lowercase / uppercase / titlecase → string transform
    """
    if value is None:
        return None

    mode_lower = mode.lower()

    # Handle lists: normalize each element
    if isinstance(value, list):
        return [_apply_normalize(item, mode) for item in value]

    if mode_lower == "e164":
        from normalizers.phone import normalize_phone
        return normalize_phone(str(value))

    if mode_lower == "canonical":
        from normalizers.skill import normalize_skill
        return normalize_skill(str(value))

    if isinstance(value, str):
        if mode_lower == "lowercase":
            return value.lower()
        if mode_lower == "uppercase":
            return value.upper()
        if mode_lower == "titlecase":
            return value.title()

    logger.warning(f"[projector] Unknown normalize mode: {mode!r}")
    return value


# ── Type coercion ─────────────────────────────────────────────────────────────

def _coerce_type(value: Any, type_str: str) -> Any:
    """
    Coerce a resolved (and normalized) value to the requested type.

    Supported types: "string" | "number" | "boolean" | "string[]" | "number[]"
    Returns None on coercion failure (logged).
    """
    if value is None:
        return None

    try:
        if type_str == "string":
            return str(value)

        if type_str == "number":
            return float(value) if "." in str(value) else int(value)

        if type_str == "boolean":
            if isinstance(value, bool):
                return value
            return str(value).lower() in ("true", "1", "yes")

        if type_str == "string[]":
            if isinstance(value, list):
                return [str(v) for v in value if v is not None]
            return [str(value)]

        if type_str == "number[]":
            if isinstance(value, list):
                result = []
                for v in value:
                    try:
                        result.append(float(v) if "." in str(v) else int(v))
                    except (ValueError, TypeError):
                        pass
                return result
            return [float(value) if "." in str(value) else int(value)]

    except Exception as exc:
        logger.debug(f"[projector] Type coercion to {type_str!r} failed for {value!r}: {exc}")
    return value


# ── Config loader ─────────────────────────────────────────────────────────────

def load_config(path: str) -> Dict[str, Any]:
    """Load and parse the projection config JSON. Returns {} on failure."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.warning(f"[projector] Config not found: {path!r} — skipping projection")
        return {}
    except json.JSONDecodeError as exc:
        logger.error(f"[projector] Invalid config JSON: {exc}")
        return {}
    except Exception as exc:
        logger.error(f"[projector] Failed to load config: {exc}")
        return {}


# ── Main projection ───────────────────────────────────────────────────────────

def apply_projection(
    data: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply field remapping from config to the merged candidate record.

    Implements the full "Required twist — configurable output":
      • Field selection & renaming via "fields" list + "from" key.
      • Per-field normalization via "normalize" key (E164 | canonical | …).
      • Type coercion via "type" key (string | number | boolean | string[] | number[]).
      • Required flag: raises ConfigProjectionError when required + on_missing=error.
      • Toggle confidence via "include_confidence" (default: True).
      • Toggle provenance via "include_provenance" (default: False).
      • on_missing behaviour: "null" | "omit" | "error" (default: "null").

    Args:
        data:   Merged candidate record (internal canonical form).
        config: Parsed config dict.

    Returns:
        Projected dict. If config is empty/has no fields, returns data unchanged.

    Raises:
        ConfigProjectionError: If a required field is missing and on_missing="error".
    """
    if not config:
        return data

    fields: List[Dict[str, Any]] = config.get("fields", [])
    if not fields:
        logger.info("[projector] No fields defined in config; returning data as-is")
        return data

    # ── Top-level options ─────────────────────────────────────────────────────
    on_missing: str         = str(config.get("on_missing", "null")).lower()
    include_confidence: bool = bool(config.get("include_confidence", True))
    include_provenance: bool = bool(config.get("include_provenance", False))

    if on_missing not in ("null", "omit", "error"):
        logger.warning(f"[projector] Unknown on_missing value {on_missing!r}; defaulting to 'null'")
        on_missing = "null"

    projected: Dict[str, Any] = {}

    # ── Process each field mapping ────────────────────────────────────────────
    for mapping in fields:
        target_path: Optional[str] = mapping.get("path")
        from_expr:   str           = mapping.get("from") or target_path or ""
        normalize:   Optional[str] = mapping.get("normalize")
        type_str:    Optional[str] = mapping.get("type")
        required:    bool          = bool(mapping.get("required", False))

        if not target_path:
            logger.warning(f"[projector] Skipping invalid mapping (no path): {mapping}")
            continue

        # 1. Resolve value
        value = _resolve(data, from_expr)

        # 2. Handle missing
        if value is None:
            if required:
                msg = f"[projector] Required field {target_path!r} (from {from_expr!r}) is missing"
                if on_missing == "error":
                    raise ConfigProjectionError(msg)
                elif on_missing == "omit":
                    logger.warning(msg + " — omitting field")
                    continue
                else:  # "null"
                    logger.warning(msg + " — writing null")
                    projected[target_path] = None
            else:
                if on_missing == "omit":
                    logger.debug(f"[projector] Missing optional {target_path!r} — omitting")
                    continue
                else:
                    projected[target_path] = None
            continue

        # 3. Per-field normalization
        if normalize:
            value = _apply_normalize(value, normalize)

        # 4. Type coercion
        if type_str:
            value = _coerce_type(value, type_str)

        projected[target_path] = value
        logger.debug(f"[projector] {from_expr!r} -> {target_path!r} = {value!r}")

    # ── Confidence & Provenance toggles ───────────────────────────────────────
    if include_confidence and "overall_confidence" in data:
        projected.setdefault("overall_confidence", data["overall_confidence"])
        logger.debug("[projector] overall_confidence included")
    elif not include_confidence:
        projected.pop("overall_confidence", None)
        logger.debug("[projector] overall_confidence excluded (include_confidence=false)")

    if include_provenance and "provenance" in data:
        projected["provenance"] = data["provenance"]
        logger.debug(f"[projector] provenance included ({len(data['provenance'])} entries)")

    return projected
