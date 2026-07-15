"""Compute billing efficiency, collection efficiency, and AT&C loss.

Feeder matching is done on the explicit feeder_code column (present in BOTH the
consumer and energy files, required by the templates). Codes are normalised
(uppercase/trimmed) in cleaning, so this is an exact code-to-code join.
The displayed feeder NAME is taken from the energy report.
"""

import numpy as np
import pandas as pd
from . import config
from .clean import normalise_name


def collection_efficiency(df):
    """Current-cycle collection: sum(min(pay, assessment)) / sum(assessment) * 100."""
    assess = df["current_assessment"].fillna(0)
    paid = df["pay_amt"].fillna(0)
    collected = np.minimum(paid, assess)
    denom = assess.sum()
    return (collected.sum() / denom * 100) if denom > 0 else np.nan


def build_feeder_table(consumers, energy):
    """Join consumer billed-units and energy input on feeder_code (exact).

    Returns a per-feeder DataFrame indexed by feeder_code with columns:
      billed (kWh billed by consumers), input (kWh energy input),
      feeder_name (display name from energy report), matched (bool).
    Also returns a match_report dict.
    """
    cons = consumers if config.INCLUDE_HT else consumers[consumers["is_lt"]]

    # Billed units per consumer feeder_code
    billed = cons.groupby("feeder_code")["units"].sum(min_count=1)

    # Energy input per feeder_code + a display name per code from the energy file
    if "feeder_code" in energy.columns and energy["feeder_code"].notna().any():
        e = energy.dropna(subset=["feeder_code"])
        input_by_code = e.groupby("feeder_code")["input_kwh"].sum(min_count=1)
        name_by_code = e.groupby("feeder_code")["feeder"].first()
    else:
        # Fallback: energy has no codes -> match by normalised name (imperfect)
        input_by_code = pd.Series(dtype=float)
        name_by_code = pd.Series(dtype=object)

    # Outer join so we can SEE every feeder from both sides
    feeders = pd.DataFrame({"billed": billed}).join(
        pd.DataFrame({"input": input_by_code, "feeder_name": name_by_code}), how="outer"
    )

    feeders["has_billed"] = feeders["billed"].notna() & (feeders["billed"] > 0)
    feeders["has_input"] = feeders["input"].notna() & (feeders["input"] > 0)
    feeders["matched"] = feeders["has_billed"] & feeders["has_input"]

    # Display name: energy name if present, else the code itself
    feeders["feeder_name"] = feeders["feeder_name"].fillna(
        pd.Series(feeders.index, index=feeders.index))

    report = {
        "energy_feeders": int(feeders["has_input"].sum()),
        "consumer_feeders": int(feeders["has_billed"].sum()),
        "matched": int(feeders["matched"].sum()),
        "energy_no_consumers": int((feeders["has_input"] & ~feeders["has_billed"]).sum()),
        "consumers_no_input": int((feeders["has_billed"] & ~feeders["has_input"]).sum()),
        "billed_kwh_unmatched": float(
            feeders.loc[feeders["has_billed"] & ~feeders["has_input"], "billed"].sum()),
    }
    return feeders, report


def billing_efficiency(consumers, energy):
    """Feeder-level billing efficiency using exact code matching.

    Returns (overall_pct, matched_feeder_df, matched_input_mu, flagged_count, match_report).
    Only matched feeders (have both billed + input) are used for efficiency.
    Caps each feeder at 100% and flags feeders where billed > input.
    """
    feeders_all, report = build_feeder_table(consumers, energy)

    # Efficiency only on matched feeders
    m = feeders_all[feeders_all["matched"]].copy()
    raw_eff = m["billed"] / m["input"] * 100
    m["over_100"] = raw_eff > 100
    m["billing_eff"] = raw_eff.clip(upper=100)

    total_billed = m["billed"].sum()
    total_input = m["input"].sum()
    overall = (total_billed / total_input * 100) if total_input > 0 else np.nan
    if not np.isnan(overall):
        overall = min(overall, 100)

    flagged = int(m["over_100"].sum())
    matched_input_mu = total_input / config.KWH_PER_MU
    return overall, m, matched_input_mu, flagged, report


def atc_loss(billing_eff, collection_eff):
    """AT&C loss % = (1 - billing_eff/100 * collection_eff/100) * 100."""
    if billing_eff is None or collection_eff is None:
        return np.nan
    if np.isnan(billing_eff) or np.isnan(collection_eff):
        return np.nan
    return (1 - (billing_eff / 100) * (collection_eff / 100)) * 100
