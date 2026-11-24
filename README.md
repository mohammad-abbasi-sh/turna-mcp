# turna-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/turna-mcp

Unofficial **read-only** MCP server for **Turna** (www.turna.com) — Türkiye's flight-ticket search/comparison site: **live flight search** with real fares, **cheapest fares** on a route over a date range, **monthly and daily cheapest-price calendars**, **airport/city autocomplete**, and the site's **popular routes**.

> Part of the "Turkey MCP factory". Not affiliated with Turna. Data comes from Turna's own internal JSON API behind its `/api/proxy` — no login, no API key, read-only.

## For AI agents

- **Search flights**: `turna_search_flights` takes an origin and a destination — IATA code (`"IST"`, `"SAW"`, `"ESB"`, `"ADB"`) or city name (`"istanbul"`, `"ankara"`, `"izmir"`) — plus an outbound date `YYYY-MM-DD` and an optional return date. Returns real flights (times, airline, flight numbers, duration, stops, total fare + currency, cheapest/fastest flags) and the results URL on turna.com.
- **Cheapest fares**: `turna_cheapest_flights` scans a date range (default: tomorrow .. +90 days) and returns the cheapest fares found on the route, with min/median/max stats.
- **Price calendars**: `turna_monthly_fares` returns the average cheapest fare per month (and the cheapest month); `turna_daily_prices` returns the cheapest price for each day in a window (1..120 days) plus the cheapest day.
- **Airports**: `turna_search_airports` resolves names to IATA codes through the site's autocomplete — `"ankara"` → `ESB`, `"izmir"` → `ADB`, `"istanbul"` → `IST` (all airports) and `SAW`.
- **Popular routes**: `turna_popular_routes` lists the site's most popular routes with the cheapest departing fare on each.
- Every response carries `fetched_at` (UTC) and `source: turna.com`.

## Install

```bash
uvx turna-mcp
```

Or add to your MCP client config (e.g. Claude Desktop):

```json
{
  "mcpServers": {
    "turna": {
      "command": "uvx",
      "args": ["turna-mcp"]
    }
  }
}
```

## Tools

| Tool | What it does |
| --- | --- |
| `turna_search_airports` | Search airports/cities by name → IATA codes |
| `turna_search_flights` | Live flight search (one-way or round trip) with real fares |
| `turna_cheapest_flights` | Cheapest fares on a route over a date range (+ stats) |
| `turna_monthly_fares` | Average cheapest fare per month + cheapest month |
| `turna_daily_prices` | Cheapest price per day in a window + cheapest day |
| `turna_popular_routes` | Most popular routes with cheapest departing fare |
| `turna_health` | Is turna.com reachable right now? |

## Example

Live search İstanbul → Ankara, 14 December 2026:

```json
{ "origin": { "code": "IST", "cityName": "İstanbul" },
  "destination": { "code": "ESB", "cityName": "Ankara" },
  "date": "2026-12-14", "trip_type": "OW", "currency": "USD",
  "outbound_count": 17,
  "outbound": [
    { "departure": "2026-12-14T08:00:00", "arrival": "2026-12-14T09:10:00",
      "duration": "01:10", "stops": 0, "is_direct": true,
      "total_fare": 44.38, "is_cheapest": true, "is_fastest": true,
      "segments": [
        { "flight_no": "TK2126", "airline": "Türk Hava Yolları",
          "origin": "IST", "destination": "ESB",
          "baggage": { "amount": 15, "unit": "Kilograms", "pieces": 1 } } ] } ] }
```

Cheapest month İstanbul → Ankara:

```json
{ "monthly": [
    { "year": 2026, "month": 11, "average_fare": 3501.17, "currency": "TRY" },
    { "year": 2026, "month": 12, "average_fare": 3065.32, "currency": "TRY" },
    { "year": 2027, "month": 2, "average_fare": 2926.26, "currency": "TRY" } ],
  "cheapest_month": { "year": 2027, "month": 2, "average_fare": 2926.26, "currency": "TRY" } }
```

## Caveats

- **Live search prices come back in USD** (the site's session currency), while the cheapest/monthly/daily analytics endpoints return **TRY** — each tool reports the currency the API actually returned.
- The API's `TransferCount` field is the **leg count** (1 = direct, 2 = one stop), not a stop count — the server converts it to `stops` and `is_direct` for you.
- The cheapest-fares endpoint returns **no segment details** (its `Segments` arrays are empty even with `FetchSegmentDetails` requested) — use `turna_search_flights` for flight numbers and airlines.
- Dates must be in the **future** and in `YYYY-MM-DD` form; the API rejects past dates and the Turkish `DD.MM.YYYY` form.
- The site's static endpoints are **POST-only** (GET returns HTTP 405) and the API proxy needs a session (a homepage visit first sets the cookies) — the server handles both transparently.
- Transport uses Chrome TLS impersonation; requests are spaced ~1s apart.

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/python -m pytest tests/test_flights.py -v    # offline, recorded fixtures
.venv/bin/python -m pytest tests/test_live.py -v       # live, against www.turna.com
.venv/bin/python tests/smoke_live.py                   # daily CI probe
```

## License

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — free for personal and non-commercial use; commercial use needs a separate license.

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
