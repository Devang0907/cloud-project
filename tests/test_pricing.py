import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pricing import google_rate


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class GoogleRateTests(unittest.TestCase):
    def response(self, tiers):
        payload = {
            "rate": {
                "tiers": tiers,
                "unitInfo": {"unit": "GiBy.mo", "unitQuantity": {"value": "1"}},
            }
        }
        return Response(json.dumps(payload).encode())

    def test_accepts_a_leading_free_tier(self):
        tiers = [
            {"startAmount": {"value": "0"}, "listPrice": {"currencyCode": "USD"}},
            {"startAmount": {"value": "5"}, "listPrice": {"currencyCode": "USD", "nanos": 20_000_000}},
        ]
        with patch("pricing.urlopen", return_value=self.response(tiers)):
            self.assertEqual(google_rate("test-key", "test-sku", {"GiBy.mo": 1}), 0.02)

    def test_rejects_multiple_paid_tiers(self):
        tiers = [
            {"startAmount": {"value": "0"}, "listPrice": {"currencyCode": "USD", "nanos": 20_000_000}},
            {"startAmount": {"value": "100"}, "listPrice": {"currencyCode": "USD", "nanos": 10_000_000}},
        ]
        with patch("pricing.urlopen", return_value=self.response(tiers)), self.assertRaises(ValueError):
            google_rate("test-key", "test-sku", {"GiBy.mo": 1})


if __name__ == "__main__":
    unittest.main()
