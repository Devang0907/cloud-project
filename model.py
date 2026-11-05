"""Transparent, deterministic cloud repatriation cost model (USD)."""

from __future__ import annotations

import math
from copy import deepcopy


DEFAULTS = {
    "storage_tb": 500,
    "servers": 50,
    "hours_per_month": 730,
    "aws_vm_hourly": 0.4032,
    "gcp_vm_hourly": 0.388472,
    "aws_s3_first_50_rate": 0.023,
    "aws_s3_next_450_rate": 0.022,
    "aws_s3_over_500_rate": 0.021,
    "gcp_storage_gib_month": 0.02,
    "cloud_storage_copies": 2,
    "server_purchase": 16598.99,
    "drive_tb": 32,
    "drive_purchase": 1599.99,
    "storage_copies": 2,
    "storage_fill": 0.8,
    "storage_enclosure_purchase": 15000,
    "storage_enclosures": 2,
    "network_hardware_purchase": 20000,
    "migration_once": 25000,
    "racks": 4,
    "rack_space_month": 1400,
    "server_kw": 0.35,
    "enclosure_kw": 0.8,
    "network_kw": 1.2,
    "electricity_kwh": 0.1447,
    "pue": 1.4,
    "staff_fte": 0.5,
    "staff_salary_year": 99130,
    "staff_burden": 1.3,
    "maintenance_year_fraction": 0.03,
    "hardware_life_months": 60,
    "cloud_other_month": 0,
    "onprem_other_month": 0,
    "horizon_months": 120,
}

INTEGER_KEYS = {"servers", "storage_enclosures", "racks", "horizon_months", "hardware_life_months", "storage_copies", "cloud_storage_copies"}
NONZERO_KEYS = {"drive_tb", "storage_fill", "storage_copies", "cloud_storage_copies", "hours_per_month", "hardware_life_months"}


def validate(updates: dict) -> dict:
    if not isinstance(updates, dict):
        raise ValueError("Input must be a JSON object")
    unknown = set(updates) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"Unknown inputs: {', '.join(sorted(unknown))}")
    values = deepcopy(DEFAULTS)
    for key, value in updates.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{key} must be a finite number")
        if value < 0 or (key in NONZERO_KEYS and value == 0):
            raise ValueError(f"{key} must be {'positive' if key in NONZERO_KEYS else 'nonnegative'}")
        if key in INTEGER_KEYS and int(value) != value:
            raise ValueError(f"{key} must be an integer")
        values[key] = value
    if values["storage_fill"] > 1:
        raise ValueError("storage_fill must be at most 1")
    if values["pue"] < 1:
        raise ValueError("pue must be at least 1")
    if values["horizon_months"] < 1 or values["horizon_months"] > 600:
        raise ValueError("horizon_months must be between 1 and 600")
    return values


def calculate(updates: dict | None = None) -> dict:
    v = validate(updates or {})
    # User-defined workload uses decimal TB; providers bill binary GiB.
    gib = v["storage_tb"] * 1_000_000_000_000 / (2 ** 30)
    aws_storage = (
        min(gib, 50 * 1024) * v["aws_s3_first_50_rate"]
        + min(max(gib - 50 * 1024, 0), 450 * 1024) * v["aws_s3_next_450_rate"]
        + max(gib - 500 * 1024, 0) * v["aws_s3_over_500_rate"]
    )
    aws_compute = v["servers"] * v["hours_per_month"] * v["aws_vm_hourly"]
    gcp_compute = v["servers"] * v["hours_per_month"] * v["gcp_vm_hourly"]
    aws_storage *= v["cloud_storage_copies"]
    gcp_storage = gib * v["gcp_storage_gib_month"] * v["cloud_storage_copies"]

    raw_tb = v["storage_tb"] * v["storage_copies"] / v["storage_fill"]
    drives = math.ceil(raw_tb / v["drive_tb"])
    enclosures = max(v["storage_enclosures"], math.ceil(drives / 60))
    capex_parts = {
        "Compute servers": v["servers"] * v["server_purchase"],
        "Storage drives": drives * v["drive_purchase"],
        "Storage enclosures": enclosures * v["storage_enclosure_purchase"],
        "Network hardware": v["network_hardware_purchase"],
        "One-time migration": v["migration_once"],
    }
    capex = sum(capex_parts.values())
    it_kw = v["servers"] * v["server_kw"] + enclosures * v["enclosure_kw"] + v["network_kw"]
    energy = it_kw * v["hours_per_month"] * v["electricity_kwh"]
    monthly_parts = {
        "Rack space": v["racks"] * v["rack_space_month"],
        "IT electricity": energy,
        "Cooling and facility overhead": energy * (v["pue"] - 1),
        "Incremental IT staff": v["staff_fte"] * v["staff_salary_year"] * v["staff_burden"] / 12,
        "Hardware maintenance reserve": (capex - v["migration_once"]) * v["maintenance_year_fraction"] / 12,
        "Other on-premises": v["onprem_other_month"],
    }
    onprem_month = sum(monthly_parts.values())
    cloud = {
        "AWS": {"Compute": aws_compute, "Object storage": aws_storage, "Other cloud": v["cloud_other_month"]},
        "GCP": {"Compute": gcp_compute, "Object storage": gcp_storage, "Other cloud": v["cloud_other_month"]},
    }
    cloud_month = {k: sum(parts.values()) for k, parts in cloud.items()}
    refresh = capex - v["migration_once"]
    onprem_curve = [
        round(capex + onprem_month * m + refresh * ((m - 1) // v["hardware_life_months"] if m else 0), 2)
        for m in range(v["horizon_months"] + 1)
    ]
    curves = {}
    break_even = {}
    cheaper_at_horizon = {}
    cheaper_windows = {}
    for provider, month_cost in cloud_month.items():
        curves[provider] = [round(month_cost * m, 2) for m in range(v["horizon_months"] + 1)]
        cheap_months = [m for m in range(1, v["horizon_months"] + 1) if onprem_curve[m] < curves[provider][m]]
        break_even[provider] = cheap_months[0] if cheap_months else None
        cheaper_at_horizon[provider] = onprem_curve[-1] < curves[provider][-1]
        windows = []
        for m in cheap_months:
            if windows and m == windows[-1][1] + 1:
                windows[-1][1] = m
            else:
                windows.append([m, m])
        cheaper_windows[provider] = windows
    return {
        "inputs": v,
        "cloud_parts": cloud,
        "cloud_month": cloud_month,
        "onprem_capex_parts": capex_parts,
        "onprem_capex": capex,
        "hardware_refresh_cost": refresh,
        "onprem_month_parts": monthly_parts,
        "onprem_month": onprem_month,
        "raw_storage_tb": raw_tb,
        "billable_storage_gib_per_region": gib,
        "drive_count": drives,
        "enclosure_count": enclosures,
        "it_kw": it_kw,
        "breakeven_month": break_even,
        "onprem_cheaper_at_horizon": cheaper_at_horizon,
        "cheaper_windows": cheaper_windows,
        "curves": {**curves, "On premises": onprem_curve},
        "month_axis": list(range(v["horizon_months"] + 1)),
    }
