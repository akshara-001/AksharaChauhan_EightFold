"""Parsers for various candidate data sources."""
from .csv_parser import parse as parse_csv
from .pdf_parser import parse as parse_pdf
from .github_parser import parse as parse_github
from .github_fetcher import fetch as fetch_github   # live GitHub REST API
from .ats_parser import parse as parse_ats

__all__ = ["parse_csv", "parse_pdf", "parse_github", "fetch_github", "parse_ats"]
