"""Offline tests for turna_mcp.flights — recorded real turna.com
API responses (2026-11-24, via /api/proxy with a homepage session):

- autocomplete-istanbul.json: GET /v1/meta/autocomplete/flight
  ?term=istanbul — 3 suggestions (IST city, SAW airport, IST dup).
- autocomplete-ankara.json: 1 suggestion (ESB).
- autocomplete-izmir.json: 1 suggestion (ADB).
- popular-cities.json: POST PopularCities — 8 cities.
- popular-routes.json: POST HomePopularRoutes — 14 flights + 13
  bus trips (+ ferries/hotels/cars, unused).
- cheapest-ist-esb.json: POST flights_to IST->ESB — 15 fares
  (TRY 2012.99..2122.53, all direct, Segments empty despite
  FetchSegmentDetails=true).
- monthly-ist-esb.json: POST OneWayMonthly IST->ESB — 12 months
  (Nov 2026..Oct 2027), cheapest Feb 2027 (2926.26 TRY).
- daily-ist-esb.json: POST oneway IST->ESB from 2026-12-01 —
  30 days, cheapest 1401.00 TRY.
- search-ist-esb-20261214.json: POST Search IST->ESB 2026-12-14 —
  17 flights, USD 44.38+, THY + Pegasus; TransferCount is the LEG
  count (1 = direct).
- search-ist-esb-rt.json: POST Search IST->ESB 2026-12-14 +
  ESB->IST 2026-12-18 — 17 outbound + 18 return.
"""
import json
import os
import unittest

from turna_mcp import flights as F

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name: str):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


class TestSuggestions(unittest.TestCase):
    def test_istanbul(self):
        rows = F.parse_suggestions(_load("autocomplete-istanbul.json"))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["code"], "IST")
        self.assertEqual(rows[0]["city"], "İstanbul")
        self.assertTrue(rows[0]["is_city"])
        self.assertEqual(rows[1]["code"], "SAW")
        self.assertFalse(rows[1]["is_city"])

    def test_ankara_is_esb(self):
        rows = F.parse_suggestions(_load("autocomplete-ankara.json"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "ESB")
        self.assertEqual(rows[0]["city"], "Ankara")

    def test_izmir_is_adb(self):
        rows = F.parse_suggestions(_load("autocomplete-izmir.json"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "ADB")


class TestSearchParse(unittest.TestCase):
    def test_one_way(self):
        data = F.parse_search_result(_load("search-ist-esb-20261214.json"))
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["trip_type"], "OW")
        self.assertEqual(len(data["outbound"]), 17)
        self.assertEqual(data["return"], [])
        self.assertTrue(data["results_url"].endswith("?adult=1"))
        first = data["outbound"][0]
        self.assertEqual(first["origin"], "IST")
        self.assertEqual(first["destination"], "ESB")
        self.assertEqual(first["departure"], "2026-12-14T08:00:00")
        self.assertEqual(first["arrival"], "2026-12-14T09:10:00")
        self.assertEqual(first["duration"], "01:10")
        self.assertEqual(first["stops"], 0)
        self.assertTrue(first["is_direct"])
        self.assertAlmostEqual(first["total_fare"], 44.38)
        self.assertEqual(first["segments"][0]["flight_no"], "TK2126")
        self.assertEqual(first["segments"][0]["airline"],
                         "Türk Hava Yolları")
        self.assertEqual(first["segments"][0]["baggage"]["amount"], 15)

    def test_one_stop_flight(self):
        data = F.parse_search_result(_load("search-ist-esb-20261214.json"))
        connecting = [f for f in data["outbound"] if f["stops"] == 1]
        self.assertEqual(len(connecting), 3)
        self.assertEqual(len(connecting[0]["segments"]), 2)
        self.assertFalse(connecting[0]["is_direct"])

    def test_cheapest_and_fastest_flags(self):
        data = F.parse_search_result(_load("search-ist-esb-20261214.json"))
        self.assertEqual(
            sum(1 for f in data["outbound"] if f["is_cheapest"]), 1)
        self.assertEqual(
            sum(1 for f in data["outbound"] if f["is_fastest"]), 1)

    def test_round_trip(self):
        data = F.parse_search_result(_load("search-ist-esb-rt.json"))
        self.assertEqual(data["trip_type"], "RT")
        self.assertEqual(len(data["outbound"]), 17)
        self.assertEqual(len(data["return"]), 18)
        self.assertEqual(data["return"][0]["origin"], "ESB")
        self.assertEqual(data["return"][0]["destination"], "IST")


class TestCheapest(unittest.TestCase):
    def test_rows(self):
        rows = F.parse_cheapest(_load("cheapest-ist-esb.json"))
        self.assertEqual(len(rows), 15)
        first = rows[0]
        self.assertEqual(first["departure"], "2027-02-20T09:00:00")
        self.assertEqual(first["fare"], 2012.99)
        self.assertEqual(first["currency"], "TRY")
        self.assertEqual(first["stops"], 0)
        self.assertTrue(first["is_direct"])
        self.assertEqual(first["duration_minutes"], 70)

    def test_stats(self):
        rows = F.parse_cheapest(_load("cheapest-ist-esb.json"))
        stats = F.price_stats(rows)
        self.assertEqual(stats["count"], 15)
        self.assertEqual(stats["currency"], "TRY")
        self.assertEqual(stats["min"], 2012.99)
        self.assertEqual(stats["median"], 2122.53)
        self.assertEqual(stats["max"], 2122.53)


class TestCalendars(unittest.TestCase):
    def test_monthly(self):
        data = F.parse_monthly(_load("monthly-ist-esb.json"))
        self.assertEqual(len(data["monthly"]), 12)
        self.assertEqual(data["monthly"][0]["year"], 2026)
        self.assertEqual(data["monthly"][0]["month"], 11)
        self.assertAlmostEqual(data["monthly"][0]["average_fare"], 3501.17)
        self.assertEqual(data["cheapest_month"]["month"], 2)
        self.assertEqual(data["cheapest_month"]["year"], 2027)
        self.assertAlmostEqual(
            data["cheapest_month"]["average_fare"], 2926.26, places=1)

    def test_daily(self):
        data = F.parse_daily(_load("daily-ist-esb.json"), "2026-12-01")
        self.assertEqual(len(data["days"]), 30)
        self.assertEqual(data["days"][0]["date"], "2026-12-01")
        self.assertEqual(data["days"][0]["price"], 1401.0)
        self.assertTrue(data["days"][0]["is_direct"])
        self.assertEqual(data["currency"], "TRY")
        self.assertEqual(data["cheapest_day"]["price"], 1401.0)


class TestPopular(unittest.TestCase):
    def test_routes(self):
        rows = F.parse_popular_routes(_load("popular-routes.json"))
        self.assertEqual(len(rows), 14)
        first = rows[0]
        self.assertEqual(first["origin_code"], "IST")
        self.assertEqual(first["destination_code"], "AYT")
        self.assertEqual(first["price"], 1397.6)
        self.assertEqual(first["currency"], "TRY")
        self.assertTrue(first["url"].endswith("/ucak-bileti/istanbul-antalya"))

    def test_cities(self):
        rows = F.parse_popular_cities(_load("popular-cities.json"))
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["city"], "New York")
        self.assertEqual(rows[0]["code"], "NYC")


class TestValidation(unittest.TestCase):
    def test_bad_date_format(self):
        with self.assertRaises(ValueError):
            F.validate_date("14.12.2026")

    def test_past_date(self):
        with self.assertRaises(ValueError):
            F.validate_date("2020-01-01")

    def test_good_date(self):
        self.assertEqual(F.validate_date("2030-06-15"), "2030-06-15")


if __name__ == "__main__":
    unittest.main()
