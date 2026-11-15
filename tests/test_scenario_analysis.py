import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scenario_analysis import analyze, compare_scenarios, project, sensitivity_analysis


class ScenarioAnalysisTests(unittest.TestCase):
    def test_what_if_change_recalculates_only_affected_costs(self):
        baseline = project({}, 60)
        expensive_power = project({"electricity_kwh": 0.30}, 60)
        self.assertEqual(baseline["total_5_year"]["AWS"], expensive_power["total_5_year"]["AWS"])
        self.assertEqual(baseline["total_5_year"]["GCP"], expensive_power["total_5_year"]["GCP"])
        self.assertGreater(expensive_power["total_5_year"]["On premises"], baseline["total_5_year"]["On premises"])

    def test_growth_and_utilization_increase_capacity_cost(self):
        no_growth = project({"workload_growth_rate": 0, "server_utilization": 1}, 60)
        growth = project({"workload_growth_rate": 0.10, "server_utilization": 0.8}, 60)
        for option in ("AWS", "GCP", "On premises"):
            with self.subTest(option=option):
                self.assertGreater(growth["total_5_year"][option], no_growth["total_5_year"][option])

    def test_scenarios_are_calculated_from_exposed_assumptions(self):
        results = compare_scenarios({"workload_growth_rate": 0.05, "server_utilization": 0.8})
        self.assertEqual(set(results), {"Best case", "Base case", "Worst case"})
        self.assertLess(results["Best case"]["assumptions"]["aws_vm_hourly"], results["Base case"]["assumptions"]["aws_vm_hourly"])
        self.assertGreater(results["Worst case"]["assumptions"]["aws_vm_hourly"], results["Base case"]["assumptions"]["aws_vm_hourly"])
        for result in results.values():
            self.assertIn(result["best_option"], ("AWS", "GCP", "On premises"))
            self.assertGreaterEqual(result["estimated_savings"], 0)

    def test_break_even_matches_first_lower_curve_month(self):
        result = project({}, 60)
        for provider in ("AWS", "GCP"):
            expected = next((m for m in range(1, 61) if result["curves"]["On premises"][m] < result["curves"][provider][m]), None)
            self.assertEqual(result["break_even_month"][provider], expected)

    def test_sensitivity_is_ranked_by_actual_impact(self):
        rows = sensitivity_analysis({}, 0.20)
        self.assertEqual([row["rank"] for row in rows], list(range(1, len(rows) + 1)))
        self.assertEqual([row["impact"] for row in rows], sorted((row["impact"] for row in rows), reverse=True))
        for row in rows:
            actual = max(
                abs(row[side][option] - row["base_total_5_year"][option])
                for side in ("low_total_5_year", "high_total_5_year")
                for option in ("AWS", "GCP", "On premises")
            )
            self.assertAlmostEqual(row["impact"], actual, places=2)

    def test_invalid_inputs_and_analysis_payloads(self):
        invalid = (
            ({"server_utilization": 0}, 60),
            ({"workload_growth_rate": -0.1}, 60),
            ({}, 0),
        )
        for values, horizon in invalid:
            with self.subTest(values=values, horizon=horizon), self.assertRaises(ValueError):
                project(values, horizon)
        with self.assertRaises(ValueError):
            analyze({"unexpected": 1})
        with self.assertRaises(ValueError):
            sensitivity_analysis({}, 1.1)

    def test_analysis_integration_has_no_hardcoded_recommendation(self):
        baseline = analyze({"baseline": {"workload_growth_rate": 0, "server_utilization": 1}})
        costly_hardware = analyze({"baseline": {"server_purchase": 100000, "workload_growth_rate": 0, "server_utilization": 1}})
        self.assertNotEqual(baseline["baseline"]["total_5_year"], costly_hardware["baseline"]["total_5_year"])
        winner = costly_hardware["baseline"]["best_option"]
        self.assertIn(winner, costly_hardware["recommendations"][0])


if __name__ == "__main__":
    unittest.main()
