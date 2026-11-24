# turna-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/turna-mcp

**Turna** (www.turna.com) için resmi olmayan **salt okunur** MCP sunucusu — Türkiye'nin uçak bileti arama/karşılaştırma sitesi: **canlı uçuş araması** (gerçek fiyatlarla), bir rotada tarih aralığında **en ucuz fiyatlar**, **aylık ve günlük en ucuz fiyat takvimleri**, **havalimanı/şehir otomatik tamamlama** ve sitenin **popüler rotaları**.

> "Turkey MCP factory" projesinin bir parçasıdır. Turna ile bağlantısı yoktur. Veriler, Turna'nın `/api/proxy` arkasındaki kendi iç JSON API'sinden gelir — giriş gerekmez, API anahtarı gerekmez, salt okunurdur.

## Yapay zekâ ajanları için

- **Uçuş arama**: `turna_search_flights` kalkış ve varış noktası alır — IATA kodu (`"IST"`, `"SAW"`, `"ESB"`, `"ADB"`) veya şehir adı (`"istanbul"`, `"ankara"`, `"izmir"`) — artı gidiş tarihi `YYYY-MM-DD` ve isteğe bağlı dönüş tarihi. Gerçek uçuşları döndürür (saatler, havayolu, uçuş numaraları, süre, aktarma sayısı, toplam ücret + para birimi, en ucuz/en hızlı işaretleri) ve turna.com'daki sonuç sayfasının bağlantısını verir.
- **En ucuz fiyatlar**: `turna_cheapest_flights` bir tarih aralığını tarar (varsayılan: yarın .. +90 gün) ve rotadaki en ucuz fiyatları, en düşük/ortanca/en yüksek istatistikleriyle döndürür.
- **Fiyat takvimleri**: `turna_monthly_fares` ay başına ortalama en ucuz ücreti (ve en ucuz ayı) döndürür; `turna_daily_prices` bir penceredeki (1..120 gün) her gün için en ucuz fiyatı ve en ucuz günü döndürür.
- **Havalimanları**: `turna_search_airports` isimleri sitenin otomatik tamamlamasıyla IATA kodlarına çevirir — `"ankara"` → `ESB`, `"izmir"` → `ADB`, `"istanbul"` → `IST` (tüm havalimanları) ve `SAW`.
- **Popüler rotalar**: `turna_popular_routes` sitenin en popüler rotalarını, her birindeki en ucuz kalkış fiyatıyla listeler.
- Her yanıt `fetched_at` (UTC) ve `source: turna.com` taşır.

## Kurulum

```bash
uvx turna-mcp
```

Veya MCP istemci yapılandırmanıza ekleyin (ör. Claude Desktop):

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

## Araçlar

| Araç | Ne yapar? |
| --- | --- |
| `turna_search_airports` | İsme göre havalimanı/şehir arar → IATA kodları |
| `turna_search_flights` | Canlı uçuş araması (tek yön veya gidiş-dönüş), gerçek fiyatlarla |
| `turna_cheapest_flights` | Bir rotada tarih aralığında en ucuz fiyatlar (+ istatistik) |
| `turna_monthly_fares` | Ay başına ortalama en ucuz ücret + en ucuz ay |
| `turna_daily_prices` | Pencerede gün başına en ucuz fiyat + en ucuz gün |
| `turna_popular_routes` | En ucuz kalkış fiyatıyla en popüler rotalar |
| `turna_health` | turna.com şu an erişilebilir mi? |

## Örnek

Canlı arama İstanbul → Ankara, 14 Aralık 2026:

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

En ucuz ay İstanbul → Ankara:

```json
{ "monthly": [
    { "year": 2026, "month": 11, "average_fare": 3501.17, "currency": "TRY" },
    { "year": 2026, "month": 12, "average_fare": 3065.32, "currency": "TRY" },
    { "year": 2027, "month": 2, "average_fare": 2926.26, "currency": "TRY" } ],
  "cheapest_month": { "year": 2027, "month": 2, "average_fare": 2926.26, "currency": "TRY" } }
```

## Sınırlamalar

- **Canlı arama fiyatları USD olarak döner** (sitenin oturum para birimi); en ucuz/aylık/günlük analiz uç noktaları ise **TRY** döndürür — her araç, API'nin gerçekten döndürdüğü para birimini bildirir.
- API'nin `TransferCount` alanı **bacak sayısıdır** (1 = direkt, 2 = bir aktarma), aktarma sayısı değildir — sunucu bunu sizin için `stops` ve `is_direct` alanlarına çevirir.
- En ucuz fiyatlar uç noktası **segment detayı döndürmez** (`Segments` dizileri, `FetchSegmentDetails` istense bile boştur) — uçuş numaraları ve havayolları için `turna_search_flights` kullanın.
- Tarihler **gelecekte** olmalı ve `YYYY-MM-DD` biçiminde yazılmalıdır; API geçmiş tarihleri ve Türkçe `DD.MM.YYYY` biçimini reddeder.
- Sitenin statik uç noktaları **yalnızca POST** kabul eder (GET, HTTP 405 döndürür) ve API proxy'si oturum ister (önce ana sayfa ziyareti çerezleri ayarlar) — sunucu ikisini de şeffaf biçimde halleder.
- Aktarım, Chrome TLS taklidi kullanır; istekler ~1 sn arayla gönderilir.

## Geliştirme

```bash
python -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/python -m pytest tests/test_flights.py -v    # çevrimdışı, kayıtlı örnekler
.venv/bin/python -m pytest tests/test_live.py -v       # canlı, www.turna.com'a karşı
.venv/bin/python tests/smoke_live.py                   # günlük CI denetimi
```

## Lisans

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — kişisel ve ticari olmayan kullanım için ücretsizdir; ticari kullanım ayrı bir lisans gerektirir.

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
