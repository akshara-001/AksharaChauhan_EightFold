"""
Candidate Data Transformer — CLI Entry Point

Usage:
    python main.py [options]

Examples:
    # Full run with all sources
    python main.py \\
        --resume sample_inputs/resume.pdf \\
        --csv sample_inputs/recruiter.csv \\
        --github sample_inputs/github_profile.json \\
        --ats sample_inputs/ats_record.json \\
        --config config.json \\
        --output sample_outputs/output.json

    # Minimal run (CSV only, no config remapping)
    python main.py --csv sample_inputs/recruiter.csv

    # Custom Tika server
    python main.py --resume resume.pdf --tika-server http://localhost:9998
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _section(title: str) -> None:
    logger.info(f"{'─' * 50}")
    logger.info(f"  {title}")
    logger.info(f"{'─' * 50}")


# ── Argument parsing ───────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Candidate Data Transformer: merge multi-source candidate data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--resume",      metavar="FILE", help="Resume PDF path")
    parser.add_argument("--csv",         metavar="FILE", help="Recruiter CSV path")
    parser.add_argument("--github",      metavar="FILE", help="GitHub JSON profile path (local file)")
    parser.add_argument(
        "--github-url", metavar="USERNAME_OR_URL",
        help="Fetch live GitHub profile (e.g. 'torvalds' or 'github.com/torvalds')",
    )
    parser.add_argument(
        "--github-token", metavar="TOKEN",
        help="GitHub personal access token (optional; raises rate limit from 60 to 5000/hr)",
    )
    parser.add_argument("--ats",         metavar="FILE", help="ATS JSON record path")
    parser.add_argument(
        "--config", metavar="FILE", default="config.json",
        help="Output field remapping config (default: config.json)",
    )
    parser.add_argument(
        "--output", metavar="FILE", default="sample_outputs/output.json",
        help="Output JSON path (default: sample_outputs/output.json)",
    )
    parser.add_argument(
        "--tika-server", metavar="URL", default="http://localhost:9998",
        help="Apache Tika server URL (default: http://localhost:9998)",
    )
    parser.add_argument(
        "--no-config", action="store_true",
        help="Skip config projection; output raw merged record",
    )
    parser.add_argument(
        "--candidate-index", type=int, default=0, metavar="N",
        help="Which row to use from the CSV (0-indexed, default: 0)",
    )
    parser.add_argument(
        "--validate", action="store_true", default=True,
        help="Validate output against schema (default: True)",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser.parse_args()


# ── Pipeline ───────────────────────────────────────────────────────────────────

def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    """Execute the full transformation pipeline. Never raises."""
    start = time.time()

    # ── 1. Parse sources ──────────────────────────────────────────────────────
    _section("STEP 1 — Parsing Sources")
    raw_records: List[Dict[str, Any]] = []

    if args.resume:
        logger.info(f"Reading resume PDF: {args.resume}")
        from parsers.pdf_parser import parse as parse_pdf
        record = parse_pdf(args.resume, tika_server=args.tika_server)
        if record:
            raw_records.append(record)
        else:
            logger.warning("Resume parsing returned no data — skipping")
    else:
        logger.info("No resume provided — skipping PDF source")

    if args.csv:
        logger.info(f"Reading recruiter CSV: {args.csv}")
        from parsers.csv_parser import parse as parse_csv
        csv_records = parse_csv(args.csv)
        if csv_records:
            idx = min(args.candidate_index, len(csv_records) - 1)
            raw_records.append(csv_records[idx])
            logger.info(f"Using CSV row {idx} of {len(csv_records)}")
        else:
            logger.warning("CSV parsing returned no data — skipping")
    else:
        logger.info("No CSV provided — skipping CSV source")

    if args.github:
        logger.info(f"Reading GitHub profile (file): {args.github}")
        from parsers.github_parser import parse as parse_github
        record = parse_github(args.github)
        if record:
            raw_records.append(record)
        else:
            logger.warning("GitHub file parsing returned no data — skipping")
    elif args.github_url:
        logger.info(f"Fetching live GitHub profile: {args.github_url}")
        from parsers.github_fetcher import fetch as fetch_github
        record = fetch_github(
            args.github_url,
            token=args.github_token,
        )
        if record:
            raw_records.append(record)
            logger.info(
                f"Live GitHub fetch: name={record.get('full_name')!r}, "
                f"skills={len(record.get('skills', []))}, "
                f"repos={record.get('_meta', {}).get('public_repos', '?')}"
            )
        else:
            logger.warning("Live GitHub fetch returned no data — skipping")
    else:
        logger.info("No GitHub source provided — skipping GitHub")

    if args.ats:
        logger.info(f"Reading ATS record: {args.ats}")
        from parsers.ats_parser import parse as parse_ats
        record = parse_ats(args.ats)
        if record:
            raw_records.append(record)
        else:
            logger.warning("ATS parsing returned no data — skipping")
    else:
        logger.info("No ATS record provided — skipping ATS source")

    if not raw_records:
        logger.error("No valid source data found. Returning empty candidate record.")
        from merger.merge import _empty_candidate
        return _empty_candidate()

    logger.info(f"Parsed {len(raw_records)} source(s): "
                f"{[r.get('source') for r in raw_records]}")

    # ── 2. Normalize ──────────────────────────────────────────────────────────
    _section("STEP 2 — Normalization (handled inside parsers and merger)")
    logger.info("Field normalization applied: phone→E.164, skill→canonical, "
                "date→YYYY-MM, name→title-case, email→lowercase+validated")

    # ── 3. Merge ──────────────────────────────────────────────────────────────
    _section("STEP 3 — Merging Records")
    from merger.merge import merge_records
    merged = merge_records(raw_records)

    logger.info(f"Merge complete: name={merged.get('full_name')!r}, "
                f"emails={merged.get('emails')}, "
                f"skills={len(merged.get('skills', []))}, "
                f"overall_confidence={merged.get('overall_confidence')}")

    # ── 4. Validate schema ────────────────────────────────────────────────────
    _section("STEP 4 — Schema Validation")
    from validator.schema_validator import validate
    errors = validate(merged)
    if errors:
        for e in errors:
            logger.warning(f"  ✗ {e}")
    else:
        logger.info("  ✓ Schema valid")

    # ── 5. Apply config projection ────────────────────────────────────────────
    _section("STEP 5 — Config Projection")
    output = merged

    if not args.no_config and os.path.exists(args.config):
        from projector.config_projection import load_config, apply_projection
        config = load_config(args.config)
        if config:
            output = apply_projection(merged, config)
            logger.info(f"Projection applied: {len(config.get('fields', []))} field(s) remapped")
        else:
            logger.warning("Config load failed — outputting un-projected merged record")
    else:
        logger.info("Skipping projection (--no-config or config file absent)")

    elapsed = time.time() - start
    logger.info(f"Pipeline completed in {elapsed:.3f}s")
    return output


# ── Output ─────────────────────────────────────────────────────────────────────

def write_output(data: Dict[str, Any], path: str) -> None:
    """Write JSON output to file. Never raises."""
    try:
        out_dir = os.path.dirname(path)
        if out_dir:  # only makedirs if there's an actual directory component
            os.makedirs(out_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Output written to: {path}")
    except Exception as exc:
        logger.error(f"Failed to write output to {path!r}: {exc}")
        # Fallback: print to stdout
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # If no sources provided, run on all sample inputs
    no_sources = not any([args.resume, args.csv, args.github, args.github_url, args.ats])
    if no_sources:
        logger.info("No sources specified — running on all sample_inputs/ files")
        args.resume = "sample_inputs/resume.pdf"
        args.csv    = "sample_inputs/recruiter.csv"
        args.github = "sample_inputs/github_profile.json"
        args.ats    = "sample_inputs/ats_record.json"

    _section("CANDIDATE DATA TRANSFORMER")
    logger.info(f"Sources: resume={args.resume}, csv={args.csv}, "
                f"github={args.github}, ats={args.ats}")
    logger.info(f"Config: {args.config}  |  Output: {args.output}")
    logger.info(f"Tika server: {args.tika_server}")

    output = run_pipeline(args)

    _section("STEP 6 — Writing Output")
    write_output(output, args.output)

    # Also print to stdout for quick inspection
    print("\n" + "=" * 60)
    print("OUTPUT JSON")
    print("=" * 60)
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
