"""Orchestrate the full analysis: cleaned data -> results dict (dashboard-ready)."""

import numpy as np
import pandas as pd
from . import config, metrics
from .clean import clean_consumers, clean_energy


def _round(v, n=1):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), n)


def _cr(v):
    return _round((v or 0) / config.RS_PER_CRORE, 2)


def outstanding_breakdowns(cons, feeder_names=None):
    out = {}
    os_col = cons["total_outstanding"]
    tmp = cons.assign(
        _pos=os_col.where(os_col > 0, 0).fillna(0),
        _neg=os_col.where(os_col < 0, 0).fillna(0),
    )
    def grp(key, use_names=False):
        g = tmp.groupby(key).agg(dues=("_pos", "sum"), credits=("_neg", "sum"))
        rows = []
        for k, r in g.iterrows():
            if str(k).strip() == "":
                continue
            # For feeders, show the energy-report name instead of the code
            label = str(k)
            if use_names and feeder_names is not None:
                label = str(feeder_names.get(k, k))
            rows.append({
                "name": label,
                "dues_cr": _cr(r["dues"]),
                "credits_cr": _cr(abs(r["credits"])),
                "outstanding_cr": _cr(r["dues"] + r["credits"]),
            })
        rows.sort(key=lambda x: x["dues_cr"] or 0, reverse=True)
        return rows
    out["by_division"] = grp("division")
    out["by_feeder"] = grp("feeder_code", use_names=True)
    out["by_status"] = grp("status")
    out["by_load_band"] = grp("load_band")
    return out


def division_breakdown(cons, energy):
    """Per-division billing eff, collection eff, AT&C, theft."""
    rows = []
    for div, sub in cons.groupby("division"):
        if str(div).strip() == "":
            continue
        be, _, _, _, _ = metrics.billing_efficiency(sub, energy)
        ce = metrics.collection_efficiency(sub)
        atc = metrics.atc_loss(be, ce)
        rows.append({
            "div_name": str(div),
            "billing_eff": _round(be),
            "coll_eff": _round(ce),
            "atc_loss": _round(atc),
            "theft_suspects": int(sub["theft_suspect"].sum()),
            "consumers": int(len(sub)),
        })
    rows.sort(key=lambda r: (r["atc_loss"] is not None, r["atc_loss"] or 0), reverse=True)
    return rows


def feeder_breakdown(feeders_df, cons):
    """Per-feeder billing eff (feeders_df from billing_efficiency).

    Display name comes from the energy report (feeders_df['feeder_name']).
    """
    theft_by_code = cons.groupby("feeder_code")["theft_suspect"].sum()
    rows = []
    for code, r in feeders_df.iterrows():
        rows.append({
            "feeder": str(r.get("feeder_name", code)),
            "billing_eff": _round(r["billing_eff"]),
            "theft_suspects": int(theft_by_code.get(code, 0)),
            "input_under_recorded": bool(r["over_100"]),
        })
    rows.sort(key=lambda r: (r["billing_eff"] is not None, -(r["billing_eff"] or 0)))
    return rows


def cause_overview(cons):
    return {
        "consumers": int(len(cons)),
        "theft_suspects": int(cons["theft_suspect"].sum()),
        "estimated_bills": int(cons["estimated_bill"].sum()),
        "no_meter": int(cons["no_meter"].sum()),
        "faulty_meters": int(cons["faulty_meter"].sum()),
        "prepaid": int(cons["is_prepaid"].sum()),
        "consumers_with_arrears": int((cons["total_outstanding"].fillna(0) > 0).sum()),
        "outstanding_cr": _cr(cons["total_outstanding"].sum()),
        "lpsc_cr": _cr(cons["lpsc"].sum()),
    }


def causes_by_division(cons):
    rows = []
    for div, sub in cons.groupby("division"):
        if str(div).strip() == "":
            continue
        rows.append({
            "div_name": str(div),
            "theft_suspects": int(sub["theft_suspect"].sum()),
            "no_meter": int(sub["no_meter"].sum()),
            "estimated_bills": int(sub["estimated_bill"].sum()),
        })
    rows.sort(key=lambda r: r["theft_suspects"], reverse=True)
    return rows


def payment_modes(cons):
    if "payment_mode" not in cons.columns:
        return []
    g = cons["payment_mode"].astype(str).str.upper().str.strip().value_counts()
    return [{"mode": str(k), "count": int(v)} for k, v in g.items() if k not in ("", "NAN")][:8]


def exception_reasons(cons):
    if "exception_reason" not in cons.columns:
        return []
    g = cons["exception_reason"].astype(str).str.strip().value_counts()
    return [{"reason": str(k), "count": int(v)} for k, v in g.items() if k not in ("", "nan", "None")][:8]


def analyze(consumer_df, energy_df, month_label="Uploaded"):
    """Full analysis. Returns a results dict ready for JSON / dashboard."""
    cons = clean_consumers(consumer_df)
    energy = clean_energy(energy_df)

    be, feeders_df, matched_mu, flagged, match_report = metrics.billing_efficiency(cons, energy)
    feeder_names = feeders_df["feeder_name"].to_dict() if "feeder_name" in feeders_df.columns else {}
    ce = metrics.collection_efficiency(cons)
    atc = metrics.atc_loss(be, ce)

    summary = {
        "month": month_label,
        "consumers": int(len(cons)),
        "billing_eff_pct": _round(be),
        "collection_eff_pct": _round(ce),
        "atc_loss_pct": _round(atc),
        "input_matched_mu": _round(matched_mu),
        "theft_suspects": int(cons["theft_suspect"].sum()),
        "outstanding_cr": _cr(cons["total_outstanding"].sum()),
        "feeders_input_under_recorded": flagged,
        "match_report": match_report,
    }

    return {
        "summary": [summary],
        "causes": [dict(month=month_label, **cause_overview(cons))],
        "months": {
            month_label: {
                "divisions": division_breakdown(cons, energy),
                "feeders": feeder_breakdown(feeders_df, cons),
                "payment_modes": payment_modes(cons),
                "exception_reasons": exception_reasons(cons),
                "outstanding": outstanding_breakdowns(cons, feeder_names),
                "causes_by_division": causes_by_division(cons),
            }
        },
    }