"""Parsers for turna.com flight data + place resolution.

All parsers take already-fetched JSON (from turna_mcp.http) and
return compact plain dicts. No network here, so the offline tests
can run against the recorded fixtures.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from . import http as _http

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# PaxType enum of the Turna API: 0 adult, 1 child, 2 infant.
PAX_TYPES = {"adult": 0, "child": 1, "infant": 2}


def validate_date(value: str, *, name: str = "date") -> str:
    """YYYY-MM-DD, not in the past (the API rejects past dates)."""
    if not value or not _DATE_RE.match(value.strip()):
        raise ValueError(f"{name} must be YYYY-MM-DD, got {value!r}")
    value = value.strip()
    y, m, d = (int(p) for p in value.split("-"))
    try:
        parsed = date(y, m, d)
    except ValueError as e:
        raise ValueError(f"{name} is not a real date: {value}") from e
    if parsed < date.today():
        raise ValueError(f"{name} {value} is in the past")
    return value


def resolve_place(value: str) -> dict:
    """Resolve a user-supplied place to an airport/city code.

    Accepts a 3-letter IATA code ("IST", "ESB") as-is, or a name
    ("istanbul", "ankara", "izmir") resolved through the site's own
    autocomplete: exact code match wins, otherwise the first
    suggestion. Returns the raw suggestion dict.
    """
    value = (value or "").strip()
    if not value:
        raise ValueError("place must not be empty")
    if re.fullmatch(r"[A-Za-z]{3}", value):
        return {"code": value.upper(), "cityName": value.upper(),
                "label": value.upper(), "isCity": False}
    suggestions = _http.autocomplete(value)
    if not suggestions:
        raise ValueError(
            f"no airport or city found for {value!r} on turna.com"
        )
    upper = value.upper()
    for s in suggestions:
        if str(s.get("code", "")).upper() == upper:
            return s
    return suggestions[0]


def parse_suggestions(raw: list) -> list[dict]:
    """Autocomplete rows -> compact airport/city rows."""
    rows = []
    for s in raw or []:
        if not isinstance(s, dict):
            continue
        rows.append({
            "code": s.get("code"),
            "city": s.get("cityName"),
            "airport": s.get("airportName"),
            "country": s.get("countryName"),
            "is_city": bool(s.get("isCity")),
            "label": s.get("label"),
        })
    return rows


def _segment(seg: dict) -> dict:
    details = seg.get("Details") or {}
    bags = details.get("BaggageAllowance") or []
    baggage = None
    if bags:
        b = bags[0]
        baggage = {
            "amount": b.get("AmountNew", b.get("Amount")),
            "unit": b.get("UnitNew", b.get("Unit")),
            "pieces": b.get("PieceCount"),
        }
    return {
        "flight_no": seg.get("FlightNo"),
        "airline": seg.get("MarketingAirlineName")
                   or seg.get("MarketingAirline"),
        "airline_code": seg.get("MarketingAirline"),
        "origin": seg.get("Origin"),
        "destination": seg.get("Destination"),
        "departure": seg.get("DepartureDate"),
        "arrival": seg.get("ArrivalDate"),
        "duration": details.get("Duration") or seg.get("Duration"),
        "booking_class": seg.get("BookingClass"),
        "meal": bool(details.get("IsMealServed")),
        "baggage": baggage,
    }


def parse_search_result(raw: dict) -> dict:
    """Live search response -> {currency, trip_type, outbound, return,
    results_url}. Each flight: times, airline, flight numbers,
    duration, stops, total fare, cheapest/fastest flags."""
    legs = (raw or {}).get("CombinableLegsList") or {}
    out: dict = {
        "results_url": raw.get("SearchResponseUrl"),
        "currency": None,
        "trip_type": None,
        "outbound": [],
        "return": [],
    }

    def _flights(block: dict | None) -> list[dict]:
        if not block:
            return []
        rows = []
        for item in block.get("Items") or []:
            fare = item.get("PriceSummary") or {}
            legs = item.get("TransferCount")
            # NOTE: the API's TransferCount is the LEG count (1 = direct,
            # 2 = one stop), verified against the segments in the
            # 2026-11-24 fixture: 14 items with TransferCount 1 have
            # exactly 1 segment, 3 with TransferCount 2 have 2.
            stops = (legs - 1) if isinstance(legs, int) else None
            rows.append({
                "origin": item.get("Origin"),
                "origin_city": item.get("OriginCityName"),
                "origin_airport": item.get("OriginAirportName"),
                "destination": item.get("Destination"),
                "destination_city": item.get("DestinationCityName"),
                "destination_airport": item.get("DestinationAirportName"),
                "departure": item.get("DepartureDate"),
                "arrival": item.get("ArrivalDate"),
                "duration": item.get("Duration"),
                "stops": stops,
                "is_direct": legs == 1,
                "total_fare": fare.get("TotalFare"),
                "base_fare": fare.get("BaseFare"),
                "tax": fare.get("Tax"),
                "is_cheapest": bool(item.get("IsCheapest")),
                "is_fastest": bool(item.get("IsFastest")),
                "segments": [_segment(s) for s in item.get("Segments") or []],
            })
        return rows

    dep = legs.get("DepartureFlights")
    ret = legs.get("ReturnFlights")
    out["outbound"] = _flights(dep)
    out["return"] = _flights(ret)
    if dep:
        out["currency"] = dep.get("Currency")
        out["trip_type"] = dep.get("TripType")
        out["total_flights"] = dep.get("TotalFlightCount")
    return out


def parse_cheapest(raw: list) -> list[dict]:
    """cheapest/flights_to rows -> compact cheapest-fare rows."""
    rows = []
    for f in raw or []:
        if not isinstance(f, dict):
            continue
        origin = f.get("Origin") or {}
        dest = f.get("Destination") or {}
        rows.append({
            "departure": f.get("OutboundDepartureDate"),
            "arrival": f.get("OutboundArrivalDate"),
            "origin": origin.get("AirportCode"),
            "origin_city": origin.get("CityName"),
            "destination": dest.get("AirportCode"),
            "destination_city": dest.get("CityName"),
            "stops": f.get("NumStops"),
            "is_direct": f.get("NumStops") == 0,
            "duration_minutes": f.get("DurationInMinutes"),
            "refundable": bool(f.get("IsRefundable")),
            "seats_left": f.get("AvailableSeats"),
            "fare": f.get("AdultNetFare"),
            "base_fare": f.get("AdultBaseFare"),
            "tax": f.get("AdultTax"),
            "currency": f.get("Currency"),
        })
    return rows


def parse_monthly(raw: dict) -> dict:
    """OneWayMonthly -> monthly average fares + cheapest month."""
    fares = []
    for m in (raw or {}).get("MonthlyFlightFares") or []:
        fares.append({
            "year": m.get("Year"),
            "month": m.get("Month"),
            "average_fare": m.get("AverageNetAmount"),
            "currency": m.get("Currency"),
        })
    cheapest = None
    if fares:
        cheapest = min(fares, key=lambda r: r["average_fare"] or float("inf"))
    return {
        "monthly": fares,
        "cheapest_month": cheapest,
        "min_yearly_fare": (raw or {}).get("MinYearlyFlightFare"),
    }


def parse_daily(raw: dict, start_date: str) -> dict:
    """oneway calendar -> one row per day with the cheapest price."""
    start = date.fromisoformat(start_date)
    rows = []
    for i, d in enumerate((raw or {}).get("DailyPrices") or []):
        day = start + timedelta(days=i)
        rows.append({
            "date": day.isoformat(),
            "price": d.get("Price"),
            "is_direct": bool(d.get("IsDirect")),
        })
    cheapest = None
    priced = [r for r in rows if r["price"] is not None]
    if priced:
        cheapest = min(priced, key=lambda r: r["price"])
    return {
        "currency": (raw or {}).get("Currency"),
        "days": rows,
        "cheapest_day": cheapest,
    }


def parse_popular_routes(raw: dict) -> list[dict]:
    """HomePopularRoutes Flights -> compact route rows."""
    rows = []
    for f in (raw or {}).get("Flights") or []:
        rows.append({
            "origin": f.get("Origin"),
            "origin_city": f.get("OriginCity"),
            "origin_code": f.get("OriginCityCode"),
            "destination": f.get("Destination"),
            "destination_city": f.get("DestinationCity"),
            "destination_code": f.get("DestinationCityCode"),
            "departure": f.get("DepartureDate"),
            "price": f.get("Price"),
            "currency": f.get("Currency"),
            "url": ("https://www.turna.com" + f["RedirectUrl"]
                   if f.get("RedirectUrl") else None),
        })
    return rows


def parse_popular_cities(raw: dict) -> list[dict]:
    rows = []
    for c in (raw or {}).get("PopularCities") or []:
        ac = c.get("AutoCompleteResult") or {}
        rows.append({
            "city": c.get("CityName"),
            "code": ac.get("code"),
            "label": ac.get("label"),
            "country": ac.get("countryName"),
        })
    return rows


def price_stats(flights: list[dict]) -> dict:
    """min / median / max over a list of rows with a numeric fare/price."""
    values = sorted(
        f["fare"] for f in flights
        if isinstance(f.get("fare"), (int, float))
    )
    if not values:
        values = sorted(
            f["price"] for f in flights
            if isinstance(f.get("price"), (int, float))
        )
    if not values:
        return {"count": len(flights), "currency": None,
                "min": None, "median": None, "max": None}
    n = len(values)
    median = values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2
    currency = next(
        (f.get("currency") for f in flights if f.get("currency")), None)
    return {"count": n, "currency": currency, "min": values[0],
            "median": median, "max": values[-1]}
