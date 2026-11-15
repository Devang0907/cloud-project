"""Scenario, projection, sensitivity, and decision-support calculations.

The existing :func:`model.calculate` function remains the financial source of
truth.  This module varies its validated inputs and combines its point-in-time
results into growth-aware projections.
"""

from __future__ import annotations

import math
from copy import deepcopy

from model import DEFAULTS, INTEGER_KEYS, calculate, validate


OPTIONS = ("AWS", "GCP", "On premises")
SCENARIO_KEYS = {"workload_growth_rate", "server_utilization"}
SENSITIVITY_PARAMETERS = (
    ("electricity_kwh", "Electricity price"),
    ("server_purchase", "Server purchase price"),
    ("maintenance_year_fraction", "Hardware maintenance"),
    ("storage_tb", "Storage requirement"),
    ("workload_growth_rate", "Annual workload growth"),
    ("aws_vm_hourly", "AWS compute price"),
    ("gcp_vm_hourly", "GCP compute price"),
    ("server_utilization", "Server utilization"),
    ("hardware_life_months", "Hardware lifecycle"),
)


def _number(name: str, value: object, *, minimum: float = 0, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < minimum or (maximum is not None and value > maximum):
        limit = f" between {minimum} and {maximum}" if maximum is not None else f" at least {minimum}"
        raise ValueError(f"{name} must be{limit}")
    return float(value)


def validate_scenario(values: dict | None = None) -> dict:
    values = deepcopy(values or {})
    if not isinstance(values, dict):
        raise ValueError("Scenario must be a JSON object")
    unknown = set(values) - set(DEFAULTS) - SCENARIO_KEYS
    if unknown:
        raise ValueError(f"Unknown scenario inputs: {', '.join(sorted(unknown))}")
    growth = _number("workload_growth_rate", values.pop("workload_growth_rate", 0), maximum=2)
    utilization = _number("server_utilization", values.pop("server_utilization", 1), minimum=0.01, maximum=1)
    validated = validate(values)
    validated.update(workload_growth_rate=growth, server_utilization=utilization)
    return validated


def _model_inputs(values: dict) -> dict:
    return {key: values[key] for key in DEFAULTS}


def project(values: dict | None = None, horizon_months: int = 60) -> dict:
    """Project costs with compounded workload growth and utilization.

    Growth scales logical storage continuously and required server count in
    whole units.  New capacity is bought when required.  At each lifecycle
    boundary, the then-current hardware estate is replaced with no salvage
    value, matching the baseline model's replacement assumption.
    """
    v = validate_scenario(values)
    horizon = int(_number("horizon_months", horizon_months, minimum=1, maximum=600))
    if horizon != horizon_months:
        raise ValueError("horizon_months must be an integer")

    baseline = calculate(_model_inputs(v))
    curves = {"AWS": [0.0], "GCP": [0.0], "On premises": [round(baseline["onprem_capex"], 2)]}
    installed_hardware = baseline["hardware_refresh_cost"]
    onprem_running = baseline["onprem_capex"]
    first_month = None

    for month in range(1, horizon + 1):
        factor = (1 + v["workload_growth_rate"]) ** (month / 12)
        snapshot_inputs = _model_inputs(v)
        snapshot_inputs["storage_tb"] = v["storage_tb"] * factor
        snapshot_inputs["servers"] = math.ceil(v["servers"] * factor / v["server_utilization"])
        snapshot_inputs["horizon_months"] = 1
        snapshot = calculate(snapshot_inputs)
        if first_month is None:
            first_month = snapshot

        curves["AWS"].append(round(curves["AWS"][-1] + snapshot["cloud_month"]["AWS"], 2))
        curves["GCP"].append(round(curves["GCP"][-1] + snapshot["cloud_month"]["GCP"], 2))
        required_hardware = snapshot["hardware_refresh_cost"]
        growth_purchase = max(0, required_hardware - installed_hardware)
        refresh_purchase = required_hardware if month > 1 and (month - 1) % v["hardware_life_months"] == 0 else 0
        installed_hardware = required_hardware
        onprem_running += snapshot["onprem_month"] + growth_purchase + refresh_purchase
        curves["On premises"].append(round(onprem_running, 2))

    break_even = {}
    for provider in ("AWS", "GCP"):
        months = [m for m in range(1, horizon + 1) if curves["On premises"][m] < curves[provider][m]]
        break_even[provider] = months[0] if months else None

    totals = {period: {option: curves[option][period] for option in OPTIONS} for period in (12, 36, 60) if period <= horizon}
    total_5y = {option: curves[option][min(60, horizon)] for option in OPTIONS}
    ordered = sorted(total_5y, key=total_5y.get)
    monthly = {
        "AWS": first_month["cloud_month"]["AWS"],
        "GCP": first_month["cloud_month"]["GCP"],
        "On premises": first_month["onprem_month"],
    }
    return {
        "assumptions": v,
        "monthly_cost": monthly,
        "annual_cost": totals.get(12),
        "total_3_year": totals.get(36),
        "total_5_year": totals.get(60, total_5y),
        "break_even_month": break_even,
        "best_option": ordered[0],
        "estimated_savings": round(total_5y[ordered[1]] - total_5y[ordered[0]], 2),
        "curves": curves,
        "month_axis": list(range(horizon + 1)),
    }


def default_scenarios(baseline: dict) -> dict:
    """Return editable input assumptions, never precomputed financial results."""
    base = validate_scenario(baseline)
    cost_keys = ("electricity_kwh", "server_purchase", "drive_purchase", "maintenance_year_fraction",
                 "aws_vm_hourly", "gcp_vm_hourly", "gcp_storage_gib_month",
                 "aws_s3_first_50_rate", "aws_s3_next_450_rate", "aws_s3_over_500_rate")
    best = deepcopy(base)
    worst = deepcopy(base)
    for key in cost_keys:
        best[key] = base[key] * 0.85
        worst[key] = base[key] * 1.15
    best["hardware_life_months"] = max(1, round(base["hardware_life_months"] * 1.2))
    worst["hardware_life_months"] = max(1, round(base["hardware_life_months"] * 0.8))
    best["workload_growth_rate"] = max(0, base["workload_growth_rate"] - 0.05)
    worst["workload_growth_rate"] = min(2, base["workload_growth_rate"] + 0.05)
    best["server_utilization"] = min(1, base["server_utilization"] * 1.1)
    worst["server_utilization"] = max(0.01, base["server_utilization"] * 0.9)
    return {"Best case": best, "Base case": base, "Worst case": worst}


def compare_scenarios(baseline: dict | None = None, scenarios: dict | None = None) -> dict:
    base = validate_scenario(baseline)
    definitions = default_scenarios(base) if scenarios is None else scenarios
    if not isinstance(definitions, dict) or not definitions:
        raise ValueError("scenarios must be a non-empty JSON object")
    results = {}
    for name, overrides in definitions.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Scenario names must be non-empty strings")
        if not isinstance(overrides, dict):
            raise ValueError(f"{name} assumptions must be a JSON object")
        merged = deepcopy(base)
        merged.update(overrides)
        results[name] = project(merged, 60)
    return results


def sensitivity_analysis(baseline: dict | None = None, variation: float = 0.2) -> list[dict]:
    base = validate_scenario(baseline)
    variation = _number("sensitivity variation", variation, minimum=0.01, maximum=1)
    base_result = project(base, 60)
    rows = []
    for key, label in SENSITIVITY_PARAMETERS:
        base_value = base[key]
        low_value, high_value = base_value * (1 - variation), base_value * (1 + variation)
        if key == "server_utilization":
            low_value, high_value = max(0.01, low_value), min(1, high_value)
        if key in INTEGER_KEYS:
            low_value, high_value = max(1, round(low_value)), max(1, round(high_value))
        low = project({**base, key: low_value}, 60)
        high = project({**base, key: high_value}, 60)
        option_impacts = {
            option: max(abs(low["total_5_year"][option] - base_result["total_5_year"][option]),
                        abs(high["total_5_year"][option] - base_result["total_5_year"][option]))
            for option in OPTIONS
        }
        rows.append({
            "parameter": key,
            "label": label,
            "low_value": low_value,
            "base_value": base_value,
            "high_value": high_value,
            "low_total_5_year": low["total_5_year"],
            "base_total_5_year": base_result["total_5_year"],
            "high_total_5_year": high["total_5_year"],
            "low_break_even": low["break_even_month"],
            "base_break_even": base_result["break_even_month"],
            "high_break_even": high["break_even_month"],
            "impact": round(max(option_impacts.values()), 2),
            "option_impacts": option_impacts,
        })
    rows.sort(key=lambda row: row["impact"], reverse=True)
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def recommendations(base_result: dict, sensitivity: list[dict]) -> list[str]:
    totals = base_result["total_5_year"]
    ordered = sorted(totals, key=totals.get)
    winner, runner_up = ordered[:2]
    savings = totals[runner_up] - totals[winner]
    messages = [
        f"{winner} is the lowest-cost five-year option, saving ${savings:,.0f} versus {runner_up} under the base assumptions."
    ]
    if winner == "On premises":
        crossings = [m for m in base_result["break_even_month"].values() if m is not None]
        if crossings:
            messages.append(f"On-premises becomes cheaper than at least one cloud provider in month {min(crossings)}; lifecycle refreshes can later reverse that lead.")
    else:
        messages.append("Cloud remains preferable because its avoided upfront hardware cost outweighs on-premises operating savings over five years.")
    if sensitivity:
        top = sensitivity[0]
        messages.append(f"The decision is most exposed to {top['label'].lower()}; the tested low/high range changes at least one five-year total by up to ${top['impact']:,.0f}.")
    return messages


def analyze(payload: dict | None = None) -> dict:
    payload = payload or {}
    if not isinstance(payload, dict):
        raise ValueError("Input must be a JSON object")
    unknown = set(payload) - {"baseline", "scenarios", "sensitivity_variation"}
    if unknown:
        raise ValueError(f"Unknown analysis fields: {', '.join(sorted(unknown))}")
    baseline = validate_scenario(payload.get("baseline"))
    scenario_results = compare_scenarios(baseline, payload.get("scenarios"))
    sensitivity = sensitivity_analysis(baseline, payload.get("sensitivity_variation", 0.2))
    base_result = scenario_results.get("Base case") or project(baseline, 60)
    return {
        "baseline": base_result,
        "scenarios": scenario_results,
        "sensitivity": sensitivity,
        "recommendations": recommendations(base_result, sensitivity),
        "methodology": {
            "sensitivity": "One-at-a-time low/base/high analysis. Impact is the largest absolute change in any option's five-year cumulative cost.",
            "growth": "Annual growth is compounded monthly; storage scales continuously and server count rounds up to whole servers after utilization adjustment.",
            "limitations": "No inflation, discount rate, financing, salvage value, or workload elasticity is modeled. Correlated parameter changes are scenario tests, not one-at-a-time sensitivity tests.",
        },
    }
