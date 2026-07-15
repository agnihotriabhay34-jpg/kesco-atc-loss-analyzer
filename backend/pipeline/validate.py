"""Validate uploaded files have the required columns before analysis."""

from . import config


def _norm(s):
    return str(s).strip().lower().replace("  ", " ")


def check_columns(df, file_type):
    """Return (ok, missing_list). file_type is 'consumer' or 'energy'."""
    required = config.CONSUMER_REQUIRED if file_type == "consumer" else config.ENERGY_REQUIRED
    have = [_norm(c) for c in df.columns]
    missing = [c for c in required if _norm(c) not in have]
    return (len(missing) == 0, missing)