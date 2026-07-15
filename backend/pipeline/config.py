# ---------- Outlier caps (values beyond these are data errors -> NaN) ----------
UNIT_CAP_LT = 500_000          # LT: catch domestic data errors
UNIT_CAP_HT = 50_000_000       # HT: allow real industrial, catch only absurd
RS_CAP_LT = 5_000_000
RS_CAP_HT = 500_000_000
LOAD_CAP_KW = 5_000       # kW; loads above this are data errors

# ---------- Voltage classification (label only; HT is NOT dropped) ----------
LT_VOLTAGES = {"0.230", "0.230kv", "0.400", "0.400kv"}
INCLUDE_HT = True         # keep HT consumers in the analysis this time

# ---------- Bill-basis codes that mean an estimated (non-actual-reading) bill ----------
ESTIMATED_BASES = {"PROV", "ASS", "CEIL"}

# ---------- Load unit normalization to kW ----------
LOAD_FACTORS = {"KW": 1.0, "BHP": 0.746, "KVA": 0.9}

# ---------- Load bands (normalized kW), fitted to actual KESCO data ----------
LOAD_BANDS = [
    (0, 1, "\u22641 kW"),
    (1, 2, "1-2 kW"),
    (2, 3, "2-3 kW"),
    (3, 5, "3-5 kW"),
    (5, 10, "5-10 kW"),
    (10, 25, "10-25 kW"),
    (25, float("inf"), "25+ kW"),
]

# ---------- Required columns (analysis fails without these) ----------
CONSUMER_REQUIRED = [
    "Division", "Feeder", "Feeder Code", "A/c No", "Supply Type", "Status", "Bill Basis",
    "Total Bill Amount (Rs)", "Last Paid Amount (Rs)", "Current Assessment (Rs)",
    "Current Month Consumption (kWh)", "Supply Voltage (kV)", "Connection Type",
    "Meter Status", "Arrear (Rs)", "Total Outstanding (Rs)", "LPSC (Rs)", "Payment Mode",
]
ENERGY_REQUIRED = ["Division", "Feeder", "Feeder Code", "Feeder Consumption (kWh)"]

# ---------- Template header -> internal name ----------
CONSUMER_MAP = {
    "Division": "division",
    "Sub Division": "sub_division",
    "Feeder": "feeder",
    "Feeder Code": "feeder_code",
    "A/c No": "acct_id",
    "Supply Type": "supply_type",
    "Category": "category",
    "Status": "status",
    "Bill Basis": "bill_basis",
    "Total Bill Amount (Rs)": "billed_amount",
    "Last Paid Amount (Rs)": "pay_amt",
    "Current Assessment (Rs)": "current_assessment",
    "Current Month Consumption (kWh)": "consumption",
    "Supply Voltage (kV)": "voltage",
    "Connection Type": "connection_type",
    "Meter Status": "meter_status",
    "Meter Exception Reason": "exception_reason",
    "Arrear (Rs)": "arrear",
    "Total Outstanding (Rs)": "total_outstanding",
    "LPSC (Rs)": "lpsc",
    "Payment Mode": "payment_mode",
    "Load": "load",
    "Load Unit": "load_unit",
}
ENERGY_MAP = {
    "Division": "division",
    "Feeder": "feeder",
    "Feeder Code": "feeder_code",
    "Feeder Consumption (kWh)": "input_kwh",
}

# ---------- Unit conversions ----------
KWH_PER_MU = 1_000_000       # 1 Million Unit = 1,000,000 kWh
RS_PER_CRORE = 10_000_000    # 1 crore = 10 million rupees