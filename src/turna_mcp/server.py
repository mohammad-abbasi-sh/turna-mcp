"""MCP server: unofficial read-only access to turna.com flight data."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP

from . import flights as _F
from . import http as _http

mcp = FastMCP("turna-mcp")

INSTRUCTIONS = """\
Unofficial read-only MCP server for turna.com, Türkiye's flight
ticket search/comparison site (domestic + international) — live
flight search with real fares, cheapest fares on a route, monthly
and daily cheapest-price calendars, airport/city autocomplete,
and the site's popular routes. Data comes from turna.com's own
internal JSON API behind its /api/proxy (no login, no API key;
a homepage visit first sets the session cookies the proxy wants).
Places accept IATA codes ("IST", "SAW", "ESB", "ADB") or city
names ("istanbul", "ankara", "izmir") — names are resolved through
the site's autocomplete. Dates are YYYY-MM-DD and must be in the
future. Live search prices are returned in USD (the site's session
currency); the cheapest/monthly/daily analytics endpoints return
TRY — each tool reports the currency the API actually returned.
Read-only; transport uses Chrome TLS impersonation; requests are
spaced ~1s apart.
Built by Mohammad Abbasi (mohammad-abbasi-sh) — https://almanibama.ir · https://mabbasi.ir — Turkey MCP factory.\
"""


_SOURCE = "turna.com"
_DISCLAIMER = "Unofficial read-only data from turna.com; verify on the site before acting on it."


def _envelope() -> dict:
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": _SOURCE,
        "disclaimer": _DISCLAIMER,
    }


def _ok(payload: dict) -> str:
    return json.dumps({**_envelope(), **payload}, ensure_ascii=False)


def _err(e: Exception) -> str:
    return _ok({"error": str(e)})


def _validate_limit(limit: int, lo: int = 1, hi: int = 30) -> int:
    if not lo <= limit <= hi:
        raise ValueError(f"limit must be between {lo} and {hi}")
    return limit


def _validate_pax(adults: int, children: int, infants: int) -> list:
    if adults < 1 or adults > 9:
        raise ValueError("adults must be between 1 and 9")
    if not 0 <= children <= 8:
        raise ValueError("children must be between 0 and 8")
    if not 0 <= infants <= adults:
        raise ValueError("infants must be between 0 and adults")
    paxes = [{"Type": _F.PAX_TYPES["adult"], "Count": adults}]
    if children:
        paxes.append({"Type": _F.PAX_TYPES["child"], "Count": children})
    if infants:
        paxes.append({"Type": _F.PAX_TYPES["infant"], "Count": infants})
    return paxes


@mcp.tool()
def turna_search_airports(query: str, limit: int = 10) -> str:
    """Search Turna airports/cities by name. query: e.g. "istanbul",
    "ankara", "izmir", "antalya", "londra". limit 1..30. Returns
    matches (IATA code, city, airport, country, is_city) as the
    site's autocomplete returns them — use the code with the other
    tools."""
    try:
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        _validate_limit(limit)
        rows = _F.parse_suggestions(_http.autocomplete(query.strip()))
    except (ValueError, _http.TurnaError) as e:
        return _err(e)
    return _ok({"query": query.strip(), "count": min(limit, len(rows)),
                "airports": rows[:limit]})


@mcp.tool()
def turna_search_flights(origin: str, destination: str, date_: str,
                         return_date: str | None = None,
                         adults: int = 1, children: int = 0,
                         infants: int = 0,
                         cabin: str = "Economy", limit: int = 10) -> str:
    """Live flight search on Turna. origin/destination: IATA code
    ("IST", "ESB") or city name ("istanbul", "ankara"). date_:
    outbound date YYYY-MM-DD (must be in the future). return_date:
    optional return date for a round trip. adults 1..9, children
    0..8, infants 0..adults. cabin: "Economy" or "Business". limit
    1..30 flights per leg. Returns flights (times, airline, flight
    numbers, duration, stops, total fare + currency, cheapest /
    fastest flags) and the results URL on turna.com. Note: live
    search prices come back in USD."""
    try:
        _validate_limit(limit)
        dep = _F.validate_date(date_, name="date_")
        ret = None
        if return_date:
            ret = _F.validate_date(return_date, name="return_date")
            if ret <= dep:
                raise ValueError("return_date must be after date_")
        paxes = _validate_pax(adults, children, infants)
        cabin = (cabin or "Economy").strip().capitalize()
        if cabin not in ("Economy", "Business"):
            raise ValueError('cabin must be "Economy" or "Business"')
        org = _F.resolve_place(origin)
        dst = _F.resolve_place(destination)
        legs = [{"Origin": org["code"], "Destination": dst["code"],
                 "DepartureDay": dep}]
        trip_type = "OW"
        if ret:
            legs.append({"Origin": dst["code"],
                         "Destination": org["code"],
                         "DepartureDay": ret})
            trip_type = "RT"
        raw = _http.search_flights(legs, paxes, trip_type, cabin)
        data = _F.parse_search_result(raw)
    except (ValueError, _http.TurnaError) as e:
        return _err(e)
    return _ok({
        "origin": org, "destination": dst,
        "date": dep, "return_date": ret, "trip_type": trip_type,
        "passengers": {"adults": adults, "children": children,
                       "infants": infants},
        "cabin": cabin,
        "currency": data["currency"],
        "results_url": data["results_url"],
        "outbound_count": len(data["outbound"]),
        "outbound": data["outbound"][:limit],
        "return_count": len(data["return"]),
        "return": data["return"][:limit],
    })


@mcp.tool()
def turna_cheapest_flights(origin: str, destination: str,
                           start_date: str | None = None,
                           end_date: str | None = None,
                           limit: int = 10) -> str:
    """Cheapest fares on a Turna route over a date range.
    origin/destination: IATA code or city name. start_date/end_date:
    YYYY-MM-DD (default: tomorrow .. +90 days). limit 1..30.
    Returns the cheapest flights found (departure/arrival, stops,
    duration, seats left, fare in TRY) plus min/median/max stats."""
    try:
        _validate_limit(limit)
        org = _F.resolve_place(origin)
        dst = _F.resolve_place(destination)
        start = _F.validate_date(start_date, name="start_date") \
            if start_date else (date.today() + timedelta(days=1)).isoformat()
        end = _F.validate_date(end_date, name="end_date") \
            if end_date else (date.today() + timedelta(days=90)).isoformat()
        if end < start:
            raise ValueError("end_date must not be before start_date")
        rows = _F.parse_cheapest(
            _http.cheapest_flights(org["code"], dst["code"], start, end))
    except (ValueError, _http.TurnaError) as e:
        return _err(e)
    return _ok({
        "origin": org, "destination": dst,
        "start_date": start, "end_date": end,
        "count": min(limit, len(rows)),
        "flights": rows[:limit],
        "stats": _F.price_stats(rows),
    })


@mcp.tool()
def turna_monthly_fares(origin: str, destination: str) -> str:
    """Average cheapest fare per month on a Turna route.
    origin/destination: IATA code or city name. Returns monthly
    average fares in TRY plus the cheapest month — the best time
    to fly a route at a glance."""
    try:
        org = _F.resolve_place(origin)
        dst = _F.resolve_place(destination)
        data = _F.parse_monthly(
            _http.monthly_fares(org["code"], dst["code"]))
    except (ValueError, _http.TurnaError) as e:
        return _err(e)
    return _ok({"origin": org, "destination": dst, **data})


@mcp.tool()
def turna_daily_prices(origin: str, destination: str,
                       start_date: str | None = None,
                       days: int = 30) -> str:
    """Cheapest price per day on a Turna route, starting at a date.
    origin/destination: IATA code or city name. start_date:
    YYYY-MM-DD (default: tomorrow). days: 1..120. Returns one row
    per day (date, cheapest price in TRY, direct or not) plus the
    cheapest day in the window."""
    try:
        if not 1 <= days <= 120:
            raise ValueError("days must be between 1 and 120")
        org = _F.resolve_place(origin)
        dst = _F.resolve_place(destination)
        start = _F.validate_date(start_date, name="start_date") \
            if start_date else (date.today() + timedelta(days=1)).isoformat()
        data = _F.parse_daily(
            _http.daily_prices(org["code"], dst["code"], start, days),
            start)
    except (ValueError, _http.TurnaError) as e:
        return _err(e)
    return _ok({"origin": org, "destination": dst,
                "start_date": start, "days": days, **data})


@mcp.tool()
def turna_popular_routes(limit: int = 10) -> str:
    """Turna's most popular flight routes right now, with the
    cheapest departing fare on each. limit 1..30. Returns routes
    (origin/destination cities + codes, next departure, price in
    TRY, link to the route page)."""
    try:
        _validate_limit(limit)
        rows = _F.parse_popular_routes(_http.popular_routes())
    except (ValueError, _http.TurnaError) as e:
        return _err(e)
    return _ok({"count": min(limit, len(rows)),
                "routes": rows[:limit]})


@mcp.tool()
def turna_health() -> str:
    """Check whether turna.com is reachable right now.

    Returns status ok (HTTP 200), blocked (HTTP 403/429 — bot wall
    or rate limit) or error, plus the HTTP status and the probed
    URL. One polite request; it does not fetch any flight data."""
    return _ok(_http.health_check())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
