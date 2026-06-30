# Candidate Data Transformer — Design Document

## Problem Statement

Recruiters receive candidate information from many sources — each with different schemas, field names, and formatting conventions. The goal is to build a pipeline that ingests multiple such sources, resolves conflicts, and produces a single, normalized, confidence-annotated JSON record.

---

## Pipeline Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                         INPUT SOURCES                            │
│  Resume PDF   Recruiter CSV   GitHub JSON   ATS JSON             │
│  (unstructured) (structured)  (semi-struct) (structured)         │
└────────┬──────────┬──────────────┬──────────────┬───────────────┘
         │          │              │              │
         ▼          ▼              ▼              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    PARSERS (per-source)                          │
│  pdf_parser   csv_parser     github_parser  ats_parser           │
│  (Apache Tika + regex heuristics)                                │
│  → Each returns a raw dict or {} on failure. Never raises.       │
└────────────────────────────┬─────────────────────────────────────┘
                             │  List[RawRecord]
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                       NORMALIZERS                                │
│  phone.py   → E.164 format via phonenumbers lib                  │
│  skill.py   → Canonical map + rapidfuzz fuzzy (≥85%)            │
│  date.py    → YYYY-MM via regex patterns + dateutil fallback     │
│  name.py    → Title Case + particle handling + whitespace        │
│  email.py   → Lowercase + RFC validation                         │
└────────────────────────────┬─────────────────────────────────────┘
                             │  Normalized RawRecords
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                        MERGER                                    │
│  merge.py — Applies source priority + field-specific rules:      │
│    Scalar fields:  Highest-priority non-null value wins          │
│    List fields:    Union from all sources, deduplicated          │
│    Skills:         Union + normalized, sources tracked           │
│    Experience:     resume > ats, deduplicated by title+company   │
│                                                                  │
│  confidence.py — Probabilistic OR:                               │
│    confidence = 1 − ∏(1 − wᵢ)  for confirming sources          │
└────────────────────────────┬─────────────────────────────────────┘
                             │  CandidateRecord
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                  SCHEMA VALIDATOR                                │
│  Validates output against JSON Schema (Draft-07).               │
│  Logs warnings. Never raises.                                    │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                  CONFIG PROJECTOR                                │
│  Reads config.json at runtime.                                   │
│  Remaps field names using expressions:                           │
│    "emails[0]", "skills[0].name", "links.github"                │
│  No code changes required.                                       │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
                     output.json  +  stdout
```

---

## Merge Policy

Source priority (highest → lowest):

| Rank | Source       | Rationale |
|------|-------------|-----------|
| 1    | Resume PDF  | Candidate-authored; most recently updated |
| 2    | GitHub JSON | Programmatically verified identity and skills |
| 3    | ATS JSON    | Recruiter-entered; may contain data-entry errors |
| 4    | CSV         | Bulk import with lowest editorial control |

Scalar conflict rule: For fields like `full_name`, `location`, `headline` — the value from the highest-ranked source that has a non-null entry wins. Both the winning and losing values are recorded in `provenance`.

Field-specific overrides:
- `skills` — Union from all sources. GitHub gets confidence boost due to higher source weight.
- `emails / phones` — Union from all, normalized, deduplicated.
- `experience / education` — From resume > ats, deduplicated by key fields.
- `links` — Per-key first-available wins (github, linkedin separately).

Rationale: A resume is the primary artifact candidates prepare for job applications and is the most recently curated. GitHub confirms technical identity but may lack professional narrative. ATS data is accurate at time of entry but may contain transcription errors. CSV is the most error-prone (bulk operations, copy-paste).

---

## Confidence Policy

Formula: Probabilistic OR (independent evidence model)

```
confidence = 1 − ∏(1 − wᵢ)
```

Each source is modeled as an independent "witness". The more witnesses agree on a fact, the higher the confidence — even if each witness alone is imperfect.

Source weights:

| Source  | Weight | Basis |
|---------|--------|-------|
| GitHub  | 0.90   | Programmatically verified |
| Resume  | 0.85   | Candidate-authored |
| ATS     | 0.80   | Recruiter-entered |
| CSV     | 0.75   | Bulk import |
| Notes   | 0.50   | Informal / subjective |

Examples:
```
resume only:           1 − (1−0.85)          = 0.85
github only:           1 − (1−0.90)          = 0.90
resume + github:       1 − (0.15)(0.10)      = 0.985
resume + github + ats: 1 − (0.15)(0.10)(0.20)= 0.997 → capped 0.99
```

---

## Output Schema

```json
{
  "candidate_id": "string",
  "full_name": "string | null",
  "emails": ["string"],
  "phones": ["string (E.164)"],
  "location": "string | null",
  "headline": "string | null",
  "experience": [{ "title": "?", "company": "?", "start": "YYYY-MM", "end": "YYYY-MM | null", "is_current": bool }],
  "education":  [{ "degree": "?", "institution": "?", "year": "YYYY" }],
  "skills":     [{ "name": "?", "confidence": 0.0–0.99, "sources": ["..."] }],
  "links":      { "github": "url | null", "linkedin": "url | null" },
  "overall_confidence": 0.0–0.99,
  "sources_used": ["string"],
  "provenance": [{ "field": "?", "source": "?", "method": "?", "raw_value": "?" }]
}
```

Missing values → `null` or `[]`. No field is required in the output.

---

## Normalization Rules

| Field | Input Examples | Output | Library |
|-------|---------------|--------|---------|
| Phone | `9876543210`, `+91 9876...`, `91-9876...` | `+919876543210` | `phonenumbers` |
| Skill | `nodejs`, `Node JS`, `NODE.JS` | `Node.js` | canonical map + `rapidfuzz` |
| Date  | `Jan 2023`, `01/2023`, `2023-01`, `2023` | `2023-01` | regex + `dateutil` |
| Name  | `JOHN DE SOUZA`, `john smith` | `John de Souza` | custom |
| Email | `ABC@Gmail.COM` | `abc@gmail.com` | `email-validator` |

---

## Edge Cases & Assumptions

| Case | Handling |
|------|----------|
| Missing source file | Parser returns `{}`, pipeline continues |
| Empty CSV | Returns `[]`, pipeline continues |
| Corrupt PDF | Tika exception caught, returns `{}` |
| Invalid phone | Normalized to `null`, noted in provenance |
| Duplicate emails | Normalized + deduplicated via `set()` |
| Conflicting names | Higher-priority source wins; both in provenance |
| Skill variants | Canonical map + fuzzy match (85% threshold) |
| Unparseable dates | Returns `null` |
| No sources at all | Returns empty CandidateRecord (no crash) |

**Assumptions:**
1. PDFs are text-based (not scanned); OCR out of scope.
2. Default region for phones without country code: India (+91).
3. "Present" end dates stored as `is_current: true`, `end: null`.
4. Unknown skills not in canonical map are kept as-is (title-cased).
5. One candidate per pipeline run (CSV row selected by `--candidate-index`).
