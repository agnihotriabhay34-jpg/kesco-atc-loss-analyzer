"""Data cleaning: numbers, feeder codes, outliers, load normalization, cause flags.

Outlier caps are applied per voltage class: LT consumers get a tight cap
(domestic error detection); HT consumers get a loose cap so real large
industrial values aren't erased (only absurd garbage is caught).
"""

import re
import numpy as np
import pandas as pd
from . import config


def to_num(series):
    """Convert text/mixed to numeric; strip commas, symbols, and parenthetical notes."""
    s = series.astype(str)
    s = s.str.replace(r"[,\s₹]", "", regex=True)
    s = s.str.replace(r"\(.*?\)", "", regex=True)
    s = s.replace({"": np.nan, "nan": np.nan, "None": np.nan, "--": np.nan})
    return pd.to_numeric(s, errors="coerce")


def parse_feeder_code(feeder):
    """Extract 'NAME_11digit+3letter' code; return code only if suffix is 11 digits + 3 letters."""
    if not isinstance(feeder, str) or "_" not in feeder:
        return None
    suffix = feeder.rsplit("_", 1)[1].strip()
    return suffix if re.fullmatch(r"\d{11}[A-Za-z]{3}", suffix) else None


def normalise_name(name):
    """Normalise a feeder name for fallback matching."""
    if not isinstance(name, str):
        return ""
    n = name.upper().strip()
    for token in ["SUBSTATION", "FEEDER", "S/S", "SS"]:
        n = n.replace(token, " ")
    return re.sub(r"\s+", " ", n).strip()


def normalise_code(series):
    """Normalise feeder codes for exact matching: string, uppercase, strip spaces."""
    return series.astype(str).str.upper().str.strip().replace(
        {"": np.nan, "NAN": np.nan, "NONE": np.nan})


def cap_by_class(series, is_lt, lt_limit, ht_limit):
    """Cap values above lt_limit for LT rows, above ht_limit for HT rows.

    LT rows use the tight limit (catch domestic errors); HT rows use the
    loose limit (allow real large industrial values, catch only absurd garbage).
    """
    limit = np.where(is_lt, lt_limit, ht_limit)
    return series.where(series.abs() <= limit)


def normalise_load(df):
    """Convert Load to a common kW figure using Load Unit, then cap outliers."""
    if "load" not in df.columns:
        df["load_kw"] = np.nan
        return df
    raw = to_num(df["load"])
    unit = df.get("load_unit", pd.Series([""] * len(df))).astype(str).str.upper().str.strip()
    factor = unit.map(config.LOAD_FACTORS).fillna(1.0)
    df["load_kw"] = (raw * factor).where((raw * factor).abs() <= config.LOAD_CAP_KW)
    return df


def load_band(df):
    """Assign each consumer a load band label from config.LOAD_BANDS."""
    labels = pd.Series(["Unknown"] * len(df), index=df.index)
    lk = df["load_kw"]
    for lo, hi, lab in config.LOAD_BANDS:
        mask = (lk > lo) & (lk <= hi) if lo > 0 else (lk <= hi)
        labels = labels.where(~mask, lab)
    df["load_band"] = labels
    return df


def clean_consumers(df):
    """Raw consumer dataframe (template columns) -> cleaned, flagged dataframe."""
    df = df.rename(columns={k: v for k, v in config.CONSUMER_MAP.items() if k in df.columns})

    # Feeder code comes from its own column (required); normalise for exact matching.
    # Fall back to parsing from the feeder string only if the column is entirely absent.
    if "feeder_code" in df.columns:
        df["feeder_code"] = normalise_code(df["feeder_code"])
    else:
        df["feeder_code"] = normalise_code(df["feeder"].apply(parse_feeder_code))

    # Numeric columns
    for col in ["billed_amount", "pay_amt", "current_assessment", "consumption",
                "arrear", "total_outstanding", "lpsc"]:
        if col in df.columns:
            df[col] = to_num(df[col])

    # Voltage -> LT/HT label FIRST (needed for class-aware capping; HT kept, just labelled)
    volt = df.get("voltage", pd.Series([""] * len(df))).astype(str).str.lower().str.strip()
    df["is_lt"] = volt.isin(config.LT_VOLTAGES)
    is_lt = df["is_lt"].values

    # Outlier removal — LT tight, HT loose (so real large HT values aren't erased)
    if "consumption" in df.columns:
        df["consumption"] = cap_by_class(df["consumption"], is_lt, config.UNIT_CAP_LT, config.UNIT_CAP_HT)
    for col in ["billed_amount", "current_assessment", "pay_amt"]:
        if col in df.columns:
            df[col] = cap_by_class(df[col], is_lt, config.RS_CAP_LT, config.RS_CAP_HT)

    # Load normalization + banding
    df = normalise_load(df)
    df = load_band(df)

    # Billed units = current-month consumption (already unified for prepaid & postpaid
    # in the source data). Keep a prepaid flag for reporting only.
    conn = df.get("connection_type", pd.Series([""] * len(df))).astype(str).str.upper()
    df["is_prepaid"] = conn.str.contains("PREPAID")
    df["units"] = df["consumption"]

    # Cause flags
    status = df.get("status", pd.Series([""] * len(df))).astype(str).str.lower()
    df["in_service"] = status.str.contains("service")
    df["theft_suspect"] = df["in_service"] & (df["units"].fillna(-1) == 0)

    basis = df.get("bill_basis", pd.Series([""] * len(df))).astype(str).str.upper().str.strip()
    df["estimated_bill"] = basis.isin(config.ESTIMATED_BASES)

    mstat = df.get("meter_status", pd.Series([""] * len(df))).astype(str).str.upper().str.strip()
    df["faulty_meter"] = mstat == "F"
    df["no_meter"] = mstat.isin(["", "NAN", "NONE"])

    return df


def clean_energy(df):
    """Clean energy report: keep feeder rows (dt == '--'), parse input, normalise code + name."""
    df = df.rename(columns={k: v for k, v in config.ENERGY_MAP.items() if k in df.columns})
    if "dt" in df.columns:
        df = df[df["dt"].astype(str).str.strip() == "--"].copy()
    df["input_kwh"] = to_num(df["input_kwh"])
    if "feeder_code" in df.columns:
        df["feeder_code"] = normalise_code(df["feeder_code"])
    df["feeder_norm"] = df["feeder"].apply(normalise_name)
    return df