"""
PDF Parser — Unstructured source.
Uses Apache Tika to extract text from resume PDFs, then applies
regex heuristics to pull out structured fields.

Tika server must be running locally (default: http://localhost:9998).
Start it with:
    java -jar tika-server-standard-*.jar --port 9998
"""
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tika extraction
# ---------------------------------------------------------------------------

def _extract_text_tika(path: str, server: str) -> str:
    """Call Apache Tika REST API via the tika Python package."""
    try:
        from tika import parser as tika_parser  # type: ignore

        logger.info(f"Calling Tika server at {server} for {path}")
        parsed = tika_parser.from_file(path, serverEndpoint=server)
        content: str = parsed.get("content") or ""
        return content.strip()
    except ImportError:
        logger.error("tika package not installed. Run: pip install tika")
        return ""
    except Exception as exc:
        logger.error(f"Tika extraction failed for {path!r}: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Field extractors (regex heuristics on raw text)
# ---------------------------------------------------------------------------

def _extract_emails(text: str) -> List[str]:
    return list(dict.fromkeys(  # preserve order, deduplicate
        re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    ))


def _extract_phones(text: str) -> List[str]:
    """Broad phone pattern; normalizer will filter invalids later."""
    raw = re.findall(r"(?<!\d)(?:\+?\d[\d\s\-().]{7,14}\d)(?!\d)", text)
    return list(dict.fromkeys(p.strip() for p in raw))


def _extract_name(text: str) -> Optional[str]:
    """Heuristic: first non-empty line that looks like a person's name."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        words = line.split()
        # 2–5 words, no digits, no special chars except hyphens/apostrophes
        if (
            2 <= len(words) <= 5
            and not any(ch.isdigit() for ch in line)
            and re.match(r"^[A-Za-z\s'\-]+$", line)
        ):
            return line
    return None


def _extract_headline(text: str) -> Optional[str]:
    """Heuristic: second meaningful line is often the job title/headline."""
    count = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        count += 1
        if count == 2:
            words = line.split()
            if 1 <= len(words) <= 8 and not any(ch.isdigit() for ch in line):
                return line
    return None


def _extract_section(text: str, header_pattern: str) -> Optional[str]:
    """Extract text between a section header and the next blank+header."""
    match = re.search(
        rf"(?:^|\n)[ \t]*{header_pattern}[ \t]*[:\-]?[ \t]*\n(.*?)(?=\n[ \t]*(?:{SECTION_HEADERS})[ \t]*[:\-]?[ \t]*\n|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else None


SECTION_HEADERS = (
    r"skills?|technical skills?|core competencies|"
    r"experience|work experience|employment history|"
    r"education|academic background|qualification|"
    r"projects?|certifications?|achievements?|"
    r"links?|contact|summary|objective|profile"
)


def _extract_skills(text: str) -> List[str]:
    section = _extract_section(text, r"(?:skills?|technical skills?|core competencies)")
    if not section:
        return []
    tokens = re.split(r"[,\n•·|/\\]", section)
    return [t.strip() for t in tokens if t.strip() and len(t.strip()) > 1]


def _extract_experience(text: str) -> List[Dict[str, Any]]:
    section = _extract_section(text, r"(?:experience|work experience|employment)")
    if not section:
        return []

    date_re = re.compile(
        r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4}"
        r"|\d{1,2}[/\-]\d{4}|\d{4})",
        re.IGNORECASE,
    )

    entries: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}
    lines = [l.strip() for l in section.splitlines() if l.strip()]

    for line in lines:
        dates = date_re.findall(line)
        if dates:
            if current:
                entries.append(current)
                current = {}
            if len(dates) >= 2:
                current["start"] = dates[0]
                current["end"] = dates[1]
            else:
                current["start"] = dates[0]
        elif not current.get("title"):
            current["title"] = line
        elif not current.get("company"):
            current["company"] = line

    if current:
        entries.append(current)

    return entries


def _extract_education(text: str) -> List[Dict[str, Any]]:
    section = _extract_section(text, r"(?:education|academic|qualification)")
    if not section:
        return []

    year_re = re.compile(r"\b(20\d{2}|19\d{2})\b")
    entries: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}
    lines = [l.strip() for l in section.splitlines() if l.strip()]

    for line in lines:
        year_m = year_re.search(line)
        if year_m:
            current["year"] = year_m.group(1)
            remainder = year_re.sub("", line).strip(" ,|–-")
            parts = re.split(r"[,|–-]", remainder, maxsplit=1)
            if len(parts) >= 2:
                current.setdefault("degree", parts[0].strip())
                current.setdefault("institution", parts[1].strip())
            elif parts[0].strip():
                current.setdefault("degree", parts[0].strip())
            if current:
                entries.append(current)
                current = {}
        else:
            parts = re.split(r"[,|–-]", line, maxsplit=1)
            if len(parts) == 2:
                current.setdefault("degree", parts[0].strip())
                current.setdefault("institution", parts[1].strip())
            elif line:
                current.setdefault("degree", line)

    if current:
        entries.append(current)

    return entries


def _extract_links(text: str) -> Dict[str, Optional[str]]:
    links: Dict[str, Optional[str]] = {"github": None, "linkedin": None}
    gh = re.search(r"github\.com/([a-zA-Z0-9\-_]+)", text, re.IGNORECASE)
    li = re.search(r"linkedin\.com/in/([a-zA-Z0-9\-_]+)", text, re.IGNORECASE)
    if gh:
        links["github"] = f"https://github.com/{gh.group(1)}"
    if li:
        links["linkedin"] = f"https://linkedin.com/in/{li.group(1)}"
    return links


def _extract_location(text: str) -> Optional[str]:
    """Look for a line matching 'City, State' or 'City, Country' pattern."""
    for line in text.splitlines()[:15]:  # check only top of document
        line = line.strip()
        if re.match(r"^[A-Za-z\s]+,\s*[A-Za-z\s]+$", line) and 3 <= len(line) <= 50:
            return line
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(
    path: str,
    tika_server: str = "http://localhost:9998",
) -> Dict[str, Any]:
    """
    Parse a resume PDF using Apache Tika.

    Args:
        path: Path to the PDF file.
        tika_server: Base URL of the running Tika server.

    Returns:
        Raw candidate record dict. Never raises — returns {} on failure.
    """
    logger.info(f"[pdf_parser] Parsing: {path}")

    try:
        text = _extract_text_tika(path, tika_server)
        if not text:
            logger.warning(f"[pdf_parser] No text extracted from {path!r}")
            return {}

        record: Dict[str, Any] = {
            "source": "resume",
            "full_name": _extract_name(text),
            "headline": _extract_headline(text),
            "emails": _extract_emails(text),
            "phones": _extract_phones(text),
            "skills": _extract_skills(text),
            "experience": _extract_experience(text),
            "education": _extract_education(text),
            "links": _extract_links(text),
            "location": _extract_location(text),
        }

        logger.info(
            f"[pdf_parser] Extracted: name={record['full_name']!r}, "
            f"skills={len(record['skills'])}, emails={len(record['emails'])}"
        )
        return record

    except Exception as exc:
        logger.error(f"[pdf_parser] Unexpected error parsing {path!r}: {exc}")
        return {}
