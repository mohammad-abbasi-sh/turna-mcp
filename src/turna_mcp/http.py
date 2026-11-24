"""HTTP layer for turna_mcp.

turna.com is a Next.js flight-ticket search/comparison site
(istanbul-ankara, domestic + international). Its pages are
server-rendered, but all flight data comes from an internal JSON
API behind the site's own proxy:

    https://www.turna.com/api/proxy/<endpoint>

The proxy forwards to the site's internal API host
(lb-api-b2cw.prod.turna.internal). Calls need a session: first
GET the homepage (sets saka-session / session-id / session-token
cookies), then send Turna-Session-Id / Turna-Session-Token headers
with every API call, exactly like the site's own JS client does.
No login, no API key. Plain curl gets HTTP 200 on the homepage
(no bot wall on www.turna.com; the cdn.turna.com asset host is
Akamai-walled, but the API proxy is not).

Verified live 2026-11-24 (endpoint shapes reverse-engineered from
the site's own JS chunks, cdn.turna.com/webstatic/prod/4c9f589):
- GET  /v1/meta/autocomplete/flight?term=<q>&languageCode=TR
  -> [{code, id, label, value, country, cityName, isCity,
       airportName, countryName}] (airport/city suggestions)
- POST /v1/meta/flighthome/PopularCities {LanguageCode}
  -> {PopularCities: [{CityName, AutoCompleteResult}]}
- POST /api/v1/analytics/static/HomePopularRoutes {LanguageCode}
  -> {Flights: [{Origin, OriginCity, OriginCityCode, Destination,
     DestinationCity, DestinationCityCode, DepartureDate, Price,
     Currency, RedirectUrl}], BusTrips, Ferries, Hotels, Cars}
- POST /v1/analytics/cheapest/flights_to
  {Origins:[{Code}], Destination:{Code}, MaxNumberOfResults,
   TripType:"OW"|"RT", StartDate, EndDate, FetchSegmentDetails,
   Currency, Language, CallerId:"saka", RoundTripOptions}
  -> [{OutboundDepartureDate, OutboundArrivalDate, NumStops,
     DurationInMinutes, IsRefundable, AvailableSeats, Currency,
     AdultBaseFare, AdultTax, AdultNetFare, Segments, Origin,
     Destination, ...}] (TRY fares)
- POST /v1/analytics/calendar/OneWayMonthly
  {Origin:{Code}, Destination:{Code}, Currency}
  -> {MonthlyFlightFares: [{Year, Month, AverageNetAmount,
     Currency}], MinYearlyFlightFare}
- POST /v1/analytics/calendar/oneway
  {Origin, OriginIsCity, Destination, DestinationIsCity,
   DepartureDay, Currency, Language, NumberOfDays}
  -> {Prices, DailyPrices: [{Price, IsDirect}], Currency}
- POST v2/flight/ticketing/Search
  {SearchForm: {Legs: [{Origin, Destination, DepartureDay}],
   Paxes: [{Type, Count}], Currency, Language,
   CabinClass, TripType}}
  -> {CombinableLegsList: {DepartureFlights, ReturnFlights?},
     SearchResponseUrl, AvailableFilters, ...}
  PaxType enum: 0 = adult, 1 = child, 2 = infant (verified: the
  API rejects "Adult" as a string and accepts 0; child/infant
  follow the .NET enum order). DepartureDay is ISO "YYYY-MM-DD"
  (the API rejects the Turkish "DD.MM.YYYY" form). Live search
  prices come back in USD (the site's session currency), while
  the analytics endpoints return TRY — each tool reports the
  currency the API actually returned.

Caveats found while probing (2026-11-24): the static endpoints
are POST-only (GET -> HTTP 405 "does not support http method
'GET'"); the autocomplete action needs the exact query params
term + languageCode (query= -> 404); the search endpoint is
unforgiving about shape and answers with precise "Required field
missing" errors, which this module surfaces verbatim.
"""
from __future__ import annotations

import time

from curl_cffi import requests as _r

BASE = "https://www.turna.com"
PROXY = f"{BASE}/api/proxy"
TIMEOUT = 90.0
MIN_INTERVAL = 1.0  # seconds between requests — be polite

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
    "Referer": f"{BASE}/",
}

_last_fetch = 0.0
_session: _r.Session | None = None
_session_headers: dict | None = None


class TurnaError(RuntimeError):
    pass


def _pace() -> None:
    global _last_fetch
    wait = MIN_INTERVAL - (time.monotonic() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    _last_fetch = time.monotonic()


def _ensure_session() -> tuple[_r.Session, dict]:
    """Homepage first: sets the session cookies the API proxy wants.

    Returns (session, headers) with Turna-Session-Id/Token filled
    in from the cookies, mirroring the site's own JS client.
    """
    global _session, _session_headers
    if _session is not None and _session_headers is not None:
        return _session, _session_headers
    _pace()
    sess = _r.Session(impersonate="chrome131")
    try:
        resp = sess.get(BASE + "/", headers=_HEADERS, timeout=TIMEOUT)
    except Exception as e:
        raise TurnaError(f"network error fetching {BASE}/: {e}") from e
    if resp.status_code != 200:
        raise TurnaError(
            f"turna.com homepage returned HTTP {resp.status_code}"
        )
    headers = dict(_HEADERS)
    sid = sess.cookies.get("session-id")
    stok = sess.cookies.get("session-token")
    if sid:
        headers["Turna-Session-Id"] = sid
    if stok:
        headers["Turna-Session-Token"] = stok
    _session = sess
    _session_headers = headers
    return sess, headers


def _call(method: str, path: str, payload: dict | None = None,
          params: dict | None = None) -> object:
    """One API call through /api/proxy. Returns parsed JSON."""
    sess, headers = _ensure_session()
    url = f"{PROXY}/{path.lstrip('/')}"
    _pace()
    try:
        if method == "GET":
            resp = sess.get(url, headers=headers, params=params,
                            timeout=TIMEOUT)
        else:
            resp = sess.post(url, headers=headers, json=payload or {},
                             timeout=TIMEOUT)
    except Exception as e:
        raise TurnaError(f"network error calling {path}: {e}") from e
    if resp.status_code in (403, 429):
        raise TurnaError(
            f"turna.com refused the request (HTTP {resp.status_code}, "
            "bot wall / rate limit) — try again later"
        )
    if resp.status_code == 404:
        raise TurnaError(
            f"endpoint not found (HTTP 404): {path} — the site may "
            "have changed its API"
        )
    if resp.status_code != 200:
        raise TurnaError(
            f"unexpected HTTP {resp.status_code} calling {path}"
        )
    try:
        data = resp.json()
    except Exception as e:
        raise TurnaError(
            f"non-JSON response from {path} "
            f"({len(resp.content)} bytes): {e}"
        ) from e
    if isinstance(data, dict) and data.get("ErrorMessage"):
        raise TurnaError(
            f"turna.com API error on {path}: {data['ErrorMessage']}"
        )
    return data


def api_get(path: str, params: dict | None = None) -> object:
    return _call("GET", path, params=params)


def api_post(path: str, payload: dict) -> object:
    return _call("POST", path, payload=payload)


def autocomplete(term: str) -> list:
    data = api_get("/v1/meta/autocomplete/flight",
                   params={"term": term, "languageCode": "TR"})
    if not isinstance(data, list):
        raise TurnaError(
            f"unexpected autocomplete response: {str(data)[:200]}"
        )
    return data


def popular_cities() -> dict:
    data = api_post("/v1/meta/flighthome/PopularCities",
                    {"LanguageCode": "TR"})
    if not isinstance(data, dict):
        raise TurnaError("unexpected popular-cities response")
    return data


def popular_routes() -> dict:
    data = api_post("/api/v1/analytics/static/HomePopularRoutes",
                    {"LanguageCode": "TR"})
    if not isinstance(data, dict):
        raise TurnaError("unexpected popular-routes response")
    return data


def cheapest_flights(origin: str, destination: str,
                     start_date: str, end_date: str,
                     trip_type: str = "OW",
                     max_results: int = 15) -> list:
    data = api_post("/v1/analytics/cheapest/flights_to", {
        "Origins": [{"Code": origin}],
        "Destination": {"Code": destination},
        "MaxNumberOfResults": max_results,
        "TripType": trip_type,
        "StartDate": start_date,
        "EndDate": end_date,
        "FetchSegmentDetails": True,
        "Currency": "TRY",
        "Language": "TR",
        "CallerId": "saka",
        "RoundTripOptions": None,
    })
    if not isinstance(data, list):
        raise TurnaError("unexpected cheapest-flights response")
    return data


def monthly_fares(origin: str, destination: str) -> dict:
    data = api_post("/v1/analytics/calendar/OneWayMonthly", {
        "Origin": {"Code": origin},
        "Destination": {"Code": destination},
        "Currency": "TRY",
    })
    if not isinstance(data, dict):
        raise TurnaError("unexpected monthly-fares response")
    return data


def daily_prices(origin: str, destination: str, start_date: str,
                 days: int = 30) -> dict:
    data = api_post("/v1/analytics/calendar/oneway", {
        "Origin": origin,
        "OriginIsCity": True,
        "Destination": destination,
        "DestinationIsCity": False,
        "DepartureDay": start_date,
        "Currency": "TRY",
        "Language": "TR",
        "NumberOfDays": days,
    })
    if not isinstance(data, dict):
        raise TurnaError("unexpected daily-prices response")
    return data


def search_flights(legs: list, paxes: list, trip_type: str = "OW",
                   cabin: str = "Economy") -> dict:
    data = api_post("v2/flight/ticketing/Search", {
        "SearchForm": {
            "Legs": legs,
            "Paxes": paxes,
            "Currency": "TRY",
            "Language": "TR",
            "CabinClass": cabin,
            "TripType": trip_type,
        },
    })
    if not isinstance(data, dict):
        raise TurnaError("unexpected flight-search response")
    return data


def health_check() -> dict:
    """One polite probe of the source site.

    Returns {"status": "ok"|"blocked"|"error", "http_status": int|None,
    "url": ..., "detail": ...}. Used by the `turna_health` tool
    and the daily smoke CI.
    """
    url = BASE + "/"
    try:
        _ensure_session()
    except TurnaError as e:
        msg = str(e)
        if "403" in msg:
            return {"status": "blocked", "http_status": 403, "url": url,
                    "detail": msg}
        if "429" in msg:
            return {"status": "blocked", "http_status": 429, "url": url,
                    "detail": msg}
        return {"status": "error", "http_status": None, "url": url,
                "detail": msg}
    return {"status": "ok", "http_status": 200, "url": url}
