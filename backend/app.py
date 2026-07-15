"""KESCO AT&C Analysis — API backend (Flask).

This is the API-only backend, meant to be deployed separately from the frontend
(which lives on Vercel). CORS is enabled so the Vercel frontend can call these endpoints.
"""

import io
import os

import pandas as pd
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from pipeline.analyze import analyze
from pipeline.validate import check_columns
from pipeline.report import build_report

app = Flask(__name__)

# Allow the frontend (Vercel) to call this API.
# Set ALLOWED_ORIGIN to your Vercel URL in production, e.g. https://kesco-atc.vercel.app
# Default "*" allows any origin (fine for a demo).
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGIN}})

MAX_UPLOAD_MB = int(os.environ.get("KESCO_MAX_UPLOAD_MB", "60"))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


@app.route("/")
def home():
    return jsonify({"ok": True, "service": "KESCO AT&C Analysis API",
                    "endpoints": ["/analyze", "/download-report"]})


@app.route("/health")
def health():
    return jsonify({"ok": True})


def _read_csv(file_storage, label):
    try:
        return pd.read_csv(io.BytesIO(file_storage.read()), dtype=str)
    except Exception as e:
        raise ValueError(f"Could not read the {label} file as CSV: {e}")


@app.route("/analyze", methods=["POST"])
def run_analysis():
    consumer_file = request.files.get("consumer")
    energy_file = request.files.get("energy")
    month = request.form.get("month", "Data snapshot")

    if consumer_file is None or energy_file is None:
        return jsonify({"ok": False, "error": "Both consumer and energy files are required."}), 400

    try:
        consumer_df = _read_csv(consumer_file, "consumer")
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    try:
        energy_df = _read_csv(energy_file, "energy")
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    ok_c, missing_c = check_columns(consumer_df, "consumer")
    ok_e, missing_e = check_columns(energy_df, "energy")
    if not ok_c or not ok_e:
        return jsonify({"ok": False, "error": "Missing required columns.",
                        "missing_consumer": missing_c, "missing_energy": missing_e}), 422

    try:
        results = analyze(consumer_df, energy_df, month_label=month)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Analysis failed: {e}"}), 500

    return jsonify({"ok": True, "data": results})


@app.route("/download-report", methods=["POST"])
def download_report():
    payload = request.get_json(silent=True) or {}
    results = payload.get("data")
    fmt = payload.get("format", "xlsx")
    level = payload.get("level", "summary")
    period = (payload.get("period") or "").strip()
    if not results:
        return jsonify({"ok": False, "error": "No analysis data provided."}), 400
    if period and results.get("summary"):
        results["summary"][0]["month"] = period
    try:
        content, mime, ext = build_report(results, fmt, level)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Report generation failed: {e}"}), 500
    label = (period or "snapshot").replace(" ", "_")
    fname = f"KESCO_ATC_{level}_{label}.{ext}"
    return Response(content, mimetype=mime,
                    headers={"Content-Disposition": f"attachment; filename={fname}"})


@app.errorhandler(413)
def too_large(e):
    return jsonify({"ok": False,
                    "error": f"File too large. Maximum upload size is {MAX_UPLOAD_MB} MB."}), 413


if __name__ == "__main__":
    debug = os.environ.get("KESCO_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
