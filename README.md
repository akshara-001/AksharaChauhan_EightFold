# Candidate Data Transformer
## Architecture

```
[Sources]                [Parsers]          [Normalizers]     [Merger]          [Projector]     [Output]
CSV (structured)    ──► csv_parser.py  ──►                                  
GitHub JSON         ──► github_parser  ──►  phone.py     ──►  merge.py     ──►  config_      ──►  output.json
ATS JSON            ──► ats_parser     ──►  skill.py         confidence.py      projection.py
Resume PDF (Tika)   ──► pdf_parser.py  ──►  date.py
                                            name.py
                                            email.py
```

### Pipeline Stages

| # | Stage | Description |
|---|-------|-------------|
| 1 | **Parse** | Each source parser returns a raw dict — never raises |
| 2 | **Normalize** | Phone→E.164, Skill→canonical, Date→YYYY-MM, Name→Title Case, Email→lowercase |
| 3 | **Merge** | Priority-based scalar pick + union for list fields |
| 4 | **Confidence** | Probabilistic OR: `1 − ∏(1−wᵢ)` |
| 5 | **Validate** | JSON Schema validation; logs errors, never crashes |
| 6 | **Project** | Config-driven field remapping at runtime |

---

## Requirements

### System Requirements

#### Java (for Apache Tika)

Apache Tika requires **Java 8 or later**. Check if Java is installed:

```bash
java -version
```

If not installed, download from [adoptium.net](https://adoptium.net/).

#### Apache Tika Server

Download the Tika server JAR from the [Apache Tika releases](https://tika.apache.org/download.html):

```bash
# Download (replace version as needed)
wget https://downloads.apache.org/tika/3.0.0/tika-server-standard-3.0.0.jar
# Start the server on port 9998
java -jar tika-server-standard-3.0.0.jar --port 9998
```
### Python Requirements
- **Python 3.10+** (uses `match`-free syntax; 3.10+ for `type | None` annotations)
Install all Python dependencies:
```bash
pip install -r requirements.txt
```
| Package | Version | Purpose |
|---------|---------|---------|
| `tika` | 2.6.0 | Apache Tika Python client for PDF extraction |
| `fpdf2` | 2.7.9 | Generate synthetic sample resume PDF |
| `phonenumbers` | 8.13.39 | Phone normalization → E.164 |
| `rapidfuzz` | 3.9.0 | Fuzzy skill name matching |
| `python-dateutil` | 2.9.0 | Flexible date parsing |
| `email-validator` | 2.2.0 | RFC-compliant email validation |
| `jsonschema` | 4.22.0 | Output schema validation |
| `pytest` | 8.2.2 | Test runner |
| `pytest-cov` | 5.0.0 | Test coverage |

---

## Quick Start

```bash
# 1. Clone / enter project directory
cd AKSHARA_EIGHTFOLD

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start Tika server (separate terminal)
java -jar tika-server-standard-*.jar --port 9998

# 4\. Run the full pipeline
python main.py \
  --resume sample_inputs/akshara_resume.pdf \
  --csv sample_inputs/recruiter.csv \
  --github-url https://github.com/Akshara-11410 \
  --ats sample_inputs/ats_record.json \
  --output sample_outputs/output.json
```
## CLI Reference

```
python main.py [OPTIONS]

Options:
  --resume FILE               Resume PDF path
  --csv FILE                  Recruiter CSV path
  --github FILE               GitHub JSON profile path (local file)
  --github-url USERNAME/URL   Fetch live GitHub profile via REST API
                              Accepts: 'torvalds', 'github.com/torvalds',
                                       'https://github.com/torvalds'
  --github-token TOKEN        GitHub personal access token
                              (optional; raises rate limit from 60→5000/hr)
  --ats FILE                  ATS JSON record path
  --config FILE               Output field remapping config (default: config.json)
  --output FILE               Output JSON path (default: sample_outputs/output.json)
  --tika-server URL           Apache Tika server URL (default: http://localhost:9998)
  --no-config                 Skip config projection; output raw merged record
  --candidate-index N         Which CSV row to use (0-indexed, default: 0)
  --log-level LEVEL           DEBUG | INFO | WARNING | ERROR (default: INFO)
```

## Output Schema

```json
{
  "candidate_id":        "cand_abc123def456",
  "full_name":           "Akshara Chauhan",
  "emails":              ["akshaaraa28@gmail.com"],
  "phones":              ["+919876543210"],
  "location":            "Bangalore, India",
  "headline":            "Backend Engineer",
  "experience": [
    { "title": "Backend Engineer", "company": "TechCorp Solutions",
      "start": "2022-01", "end": null, "is_current": true, "source": "resume" }
  ],
  "education": [
    { "degree": "B.Tech CSE", "institution": "NIT Raipur", "year": "2022", "source": "resume" }
  ],
  "skills": [
    { "name": "C++", "confidence": 0.985, "confidence_explanation": "0.985 (resume ✓ 0.85, github ✓ 0.90) → Probabilistic OR", "sources": ["resume", "github"] }
  ],
  "links":               { "github": "https://github.com/akshara-dev", "linkedin": "..." },
  "overall_confidence":  0.987,
  "sources_used":        ["ats", "csv", "github", "resume"],
  "provenance": [
    { "field": "email", "source": "resume", "method": "regex", "raw_value": "akshara@gmail.com" }
  ]
}
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ -v --cov=. --cov-report=term-missing

# Run a specific test file
python -m pytest tests/test_merge.py -v
```