"""Live tests for turna_mcp — real requests to turna.com.

Requires network + Chrome TLS impersonation (curl-cffi). The
server is polite by design (~1s between requests), so this file
takes ~40s. Run: python -m unittest discover -s tests -v

Flight data changes constantly; tests assert structure and sane
ranges, not exact fares. Dates are computed relative to today so
the tests stay valid: search uses +30 days out, cheapest uses a
+30..+120 day window.
"""
import unittest
from datetime import date, timedelta

from turna_mcp import flights as F
from turna_mcp import http as H


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


class TestLiveAutocomplete(unittest.TestCase):
    def test_istanbul(self):
        rows = F.parse_suggestions(H.autocomplete("istanbul"))
        codes = [r["code"] for r in rows]
        self.assertIn("IST", codes)
        self.assertIn("SAW", codes)

    def test_ankara(self):
        rows = F.parse_suggestions(H.autocomplete("ankara"))
        self.assertTrue(rows)
        self.assertEqual(rows[0]["code"], "ESB")

    def test_no_match(self):
        rows = F.parse_suggestions(H.autocomplete("zzzqqqx"))
        self.assertEqual(rows, [])


class TestLiveSearch(unittest.TestCase):
    def test_one_way(self):
        raw = H.search_flights(
            [{"Origin": "IST", "Destination": "ESB",
              "DepartureDay": _future(30)}],
            [{"Type": 0, "Count": 1}], "OW", "Economy")
        data = F.parse_search_result(raw)
        self.assertGreater(len(data["outbound"]), 3)
        first = data["outbound"][0]
        self.assertEqual(first["origin"], "IST")
        self.assertEqual(first["destination"], "ESB")
        self.assertGreater(first["total_fare"], 0)
        self.assertTrue(first["segments"])
        self.assertTrue(first["segments"][0]["flight_no"])

    def test_round_trip(self):
        raw = H.search_flights(
            [{"Origin": "IST", "Destination": "ESB",
              "DepartureDay": _future(30)},
             {"Origin": "ESB", "Destination": "IST",
              "DepartureDay": _future(34)}],
            [{"Type": 0, "Count": 1}], "RT", "Economy")
        data = F.parse_search_result(raw)
        self.assertGreater(len(data["outbound"]), 0)
        self.assertGreater(len(data["return"]), 0)


class TestLiveAnalytics(unittest.TestCase):
    def test_cheapest(self):
        rows = F.parse_cheapest(H.cheapest_flights(
            "IST", "ESB", _future(30), _future(120)))
        self.assertGreater(len(rows), 0)
        self.assertGreater(rows[0]["fare"], 0)
        self.assertEqual(rows[0]["currency"], "TRY")

    def test_monthly(self):
        data = F.parse_monthly(H.monthly_fares("IST", "ESB"))
        self.assertGreater(len(data["monthly"]), 5)
        self.assertIsNotNone(data["cheapest_month"])

    def test_daily(self):
        data = F.parse_daily(
            H.daily_prices("IST", "ESB", _future(30), 14), _future(30))
        self.assertEqual(len(data["days"]), 14)
        self.assertEqual(data["currency"], "TRY")

    def test_popular_routes(self):
        rows = F.parse_popular_routes(H.popular_routes())
        self.assertGreater(len(rows), 5)
        self.assertGreater(rows[0]["price"], 0)

    def test_popular_cities(self):
        rows = F.parse_popular_cities(H.popular_cities())
        self.assertGreater(len(rows), 3)


class TestLiveHealth(unittest.TestCase):
    def test_health_ok(self):
        result = H.health_check()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["http_status"], 200)


if __name__ == "__main__":
    unittest.main()
