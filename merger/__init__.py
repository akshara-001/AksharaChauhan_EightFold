"""Merger package."""
from .confidence import calculate_confidence, SOURCE_WEIGHTS
from .merge import merge_records

__all__ = ["calculate_confidence", "SOURCE_WEIGHTS", "merge_records"]
