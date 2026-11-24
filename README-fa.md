# turna-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/turna-mcp

سرور MCP غیررسمی و **فقط‌خواندنی** برای **Turna** (سایت www.turna.com) — سایت جستجو و مقایسهٔ بلیط هواپیما در ترکیه: **جستجوی زندهٔ پرواز** با قیمت‌های واقعی، **ارزان‌ترین قیمت‌ها** در یک مسیر در بازهٔ زمانی، **تقویم‌های ماهانه و روزانهٔ ارزان‌ترین قیمت**، **تکمیل خودکار فرودگاه/شهر** و **مسیرهای محبوب** سایت.

> بخشی از پروژهٔ «Turkey MCP factory». وابسته به Turna نیست. داده‌ها از API داخلی JSON خود Turna پشت `/api/proxy` می‌آیند — بدون ورود، بدون کلید API، فقط‌خواندنی.

## برای ایجنت‌های هوش مصنوعی

- **جستجوی پرواز**: `turna_search_flights` مبدأ و مقصد می‌گیرد — کد یاتا (`"IST"`، `"SAW"`، `"ESB"`، `"ADB"`) یا نام شهر (`"istanbul"`، `"ankara"`، `"izmir"`) — به‌همراه تاریخ رفت `YYYY-MM-DD` و تاریخ برگشت اختیاری. پروازهای واقعی را برمی‌گرداند (ساعت‌ها، ایرلاین، شمارهٔ پرواز، مدت، تعداد توقف، قیمت کل + ارز، برچسب ارزان‌ترین/سریع‌ترین) و پیوند صفحهٔ نتایج در turna.com را می‌دهد.
- **ارزان‌ترین قیمت‌ها**: `turna_cheapest_flights` یک بازهٔ زمانی را می‌گردد (پیش‌فرض: فردا تا ۹۰ روز بعد) و ارزان‌ترین قیمت‌های مسیر را با آمار کمینه/میانه/بیشینه برمی‌گرداند.
- **تقویم‌های قیمت**: `turna_monthly_fares` میانگین ارزان‌ترین قیمت هر ماه (و ارزان‌ترین ماه) را می‌دهد؛ `turna_daily_prices` ارزان‌ترین قیمت هر روز در یک پنجره (۱ تا ۱۲۰ روز) و ارزان‌ترین روز را می‌دهد.
- **فرودگاه‌ها**: `turna_search_airports` نام‌ها را با تکمیل خودکار سایت به کد یاتا تبدیل می‌کند — `"ankara"` → `ESB`، `"izmir"` → `ADB`، `"istanbul"` → `IST` (همهٔ فرودگاه‌ها) و `SAW`.
- **مسیرهای محبوب**: `turna_popular_routes` محبوب‌ترین مسیرهای سایت را با ارزان‌ترین قیمت رفت هرکدام فهرست می‌کند.
- هر پاسخ `fetched_at` (UTC) و `source: turna.com` دارد.

## نصب

```bash
uvx turna-mcp
```

یا به پیکربندی کلاینت MCP خود اضافه کنید (مثلاً Claude Desktop):

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

## ابزارها

| ابزار | چه می‌کند؟ |
| --- | --- |
| `turna_search_airports` | جستجوی فرودگاه/شهر با نام ← کدهای یاتا |
| `turna_search_flights` | جستجوی زندهٔ پرواز (یک‌طرفه یا رفت‌وبرگشت) با قیمت واقعی |
| `turna_cheapest_flights` | ارزان‌ترین قیمت‌های مسیر در بازهٔ زمانی (+ آمار) |
| `turna_monthly_fares` | میانگین ارزان‌ترین قیمت هر ماه + ارزان‌ترین ماه |
| `turna_daily_prices` | ارزان‌ترین قیمت هر روز در پنجره + ارزان‌ترین روز |
| `turna_popular_routes` | محبوب‌ترین مسیرها با ارزان‌ترین قیمت رفت |
| `turna_health` | آیا turna.com در دسترس است؟ |

## نمونه

جستجوی زنده استانبول ← آنکارا، ۱۴ دسامبر ۲۰۲۶:

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

ارزان‌ترین ماه استانبول ← آنکارا:

```json
{ "monthly": [
    { "year": 2026, "month": 11, "average_fare": 3501.17, "currency": "TRY" },
    { "year": 2026, "month": 12, "average_fare": 3065.32, "currency": "TRY" },
    { "year": 2027, "month": 2, "average_fare": 2926.26, "currency": "TRY" } ],
  "cheapest_month": { "year": 2027, "month": 2, "average_fare": 2926.26, "currency": "TRY" } }
```

## محدودیت‌ها

- **قیمت‌های جستجوی زنده به دلار (USD) برمی‌گردند** (ارز جلسهٔ سایت)؛ درحالی‌که endpointهای تحلیلی ارزان‌ترین/ماهانه/روزانه **لیر (TRY)** می‌دهند — هر ابزار ارزی را گزارش می‌کند که API واقعاً برگردانده است.
- فیلد `TransferCount` در API **تعداد بخش پرواز** است (۱ = مستقیم، ۲ = یک توقف)، نه تعداد توقف — سرور آن را برای شما به `stops` و `is_direct` تبدیل می‌کند.
- endpoint ارزان‌ترین قیمت‌ها **جزئیات segment برنمی‌گرداند** (آرایه‌های `Segments` حتی با درخواست `FetchSegmentDetails` خالی‌اند) — برای شمارهٔ پرواز و ایرلاین از `turna_search_flights` استفاده کنید.
- تاریخ‌ها باید در **آینده** و به شکل `YYYY-MM-DD` باشند؛ API تاریخ گذشته و شکل ترکی `DD.MM.YYYY` را رد می‌کند.
- endpointهای ایستای سایت **فقط POST** می‌پذیرند (GET خطای HTTP 405 می‌دهد) و پروکسی API به جلسه نیاز دارد (اول بازدید صفحهٔ اصلی کوکی‌ها را می‌گذارد) — سرور هر دو را شفاف مدیریت می‌کند.
- انتقال با جعل TLS کروم انجام می‌شود؛ درخواست‌ها با فاصلهٔ حدود ۱ ثانیه فرستاده می‌شوند.

## توسعه

```bash
python -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/python -m pytest tests/test_flights.py -v    # آفلاین، با فیکسچرهای ضبط‌شده
.venv/bin/python -m pytest tests/test_live.py -v       # زنده، در برابر www.turna.com
.venv/bin/python tests/smoke_live.py                   # بررسی روزانهٔ CI
```

## لایسنس

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — برای استفادهٔ شخصی و غیرتجاری رایگان است؛ استفادهٔ تجاری به لایسنس جداگانه نیاز دارد.

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
