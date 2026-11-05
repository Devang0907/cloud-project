import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import calculate


class ModelTests(unittest.TestCase):
    def test_baseline_price_arithmetic_and_refresh_reversal(self):
        result = calculate()
        self.assertAlmostEqual(result["cloud_month"]["AWS"], 35308.29664154)
        self.assertAlmostEqual(result["cloud_month"]["GCP"], 32805.67949231)
        self.assertEqual(result["drive_count"], 40)
        self.assertEqual(result["breakeven_month"], {"AWS": 52, "GCP": 59})
        self.assertLess(result["curves"]["On premises"][60], result["curves"]["AWS"][60])
        self.assertGreater(result["curves"]["On premises"][61], result["curves"]["AWS"][61])

    def test_storage_and_hardware_scale(self):
        result = calculate({"storage_tb": 2000, "cloud_storage_copies": 1})
        self.assertEqual(result["drive_count"], 157)
        self.assertEqual(result["enclosure_count"], 3)
        self.assertAlmostEqual(result["cloud_parts"]["GCP"]["Object storage"], 37252.90298462)

    def test_validation_rejects_invalid_assumptions(self):
        for update in ({"pue": 0.5}, {"storage_fill": 1.1}, {"servers": 2.5}, {"unknown": 1}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                calculate(update)


if __name__ == "__main__":
    unittest.main()
