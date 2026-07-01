# Implementation Details

## Architecture

This is a standard Home Assistant custom component installed via HACS. It follows the [DataUpdateCoordinator pattern](https://developers.home-assistant.io/docs/integration_fetching_data/#coordinated-single-api-poll-for-data-for-all-entities) — a single coordinator fetches all data on a schedule, and sensor entities read from it.

```
HACS installs custom_components/nemenkom_trash/
              │
              ▼
HA loads the integration on startup
              │
              ▼
NemenkomTrashCoordinator (timedelta = update_interval_hours)
  ├── _run_scraper() runs in executor thread (blocking I/O safe)
  │     ├── website_scraper: GET nemenkom.lt → find latest PDF/Excel URLs
  │     ├── pdf_parser: download + pdfplumber → extract dates per waste type
  │     └── excel_parser: download + openpyxl → extract dates
  │
  └── coordinator.data = {"packaging": {...}, "glass": {...}, "household": {...}}
              │
              ▼
6 SensorEntity instances read coordinator.data
  ├── NextCollectionDateSensor  × 3  (device_class=DATE, state = ISO date string)
  └── DaysRemainingSensor       × 3  (unit = days, state = int)
```

## Dependency installation

Python packages are declared in `manifest.json` under `requirements`:

```json
"requirements": [
  "pdfplumber>=0.11.0",
  "beautifulsoup4>=4.12.0",
  "openpyxl>=3.1.0",
  "lxml>=5.0.0"
]
```

Home Assistant automatically installs these into its own Python environment on first load. No virtualenv or pip calls needed.

## PDF structure (confirmed by inspection)

Both packaging and glass timetables are multi-page PDFs with this table layout per page:

| Column 0 | Column 1 | Column 2 | Column 3 | Column 4 |
|----------|----------|----------|----------|----------|
| Location (multiple streets listed) | Waste type | Month 1 | Month 2 | Month 3 |

- **Column 0**: Comma-separated street names, e.g. `"Avižienių mstl. tik. Gailašių g., Skandinavijos al., Vaikystės g."`
- **Column 1**: Waste type label — not used for date extraction
- **Columns 2–4**: Lithuanian month names as headers (`Liepa`/July, `Rugpjūtis`/August, `Rugsėjis`/September); cells contain `"X d."` (day + abbreviation for "diena") or are empty (no collection that month)

**Confirmed rows for Vaikystės g., Q3 2026:**

Packaging:
```
Avižienių mstl. tik. Gailašių g., Skandinavijos al., Vaikystės g.
  Pakuotė  |  10 d.  |  11 d.  |  9 d.
  → 2026-07-10, 2026-08-11, 2026-09-09
```

Glass:
```
Avižienių mstl. Braškyno g., ..., Vaikystės g., ...
  Stiklas  |  (empty)  |  31 d.  |  (empty)
  → 2026-08-31
```

## Excel structure (household waste)

The `.xlsx` file uses one row per street. The street name appears in the first matching column; all subsequent columns hold Excel date serial numbers (openpyxl reads them as Python `datetime` objects when `data_only=True`).

## Street name matching

`_street_aliases()` in `coordinator.py` builds a list of lookup strings:
1. The original configured string (e.g. `"Vaikystės g."`)
2. A diacritics-stripped version (`"vaikyste g."`)

Both PDF and Excel parsers do a case-insensitive substring search of the location cell against all aliases. This handles minor encoding differences in PDFs.

## Executor thread usage

All network I/O and PDF/Excel parsing happens synchronously (requests, pdfplumber, openpyxl are not async). The coordinator wraps `_run_scraper()` in `hass.async_add_executor_job()` so it runs in HA's thread pool without blocking the event loop.

## Config flow

The setup dialog (`config_flow.py`) stores two values in `entry.data`:
- `street` — street name string
- `update_interval_hours` — integer, default 168 (= 7 days)

An options flow allows changing both values post-setup via **Settings → Integrations → Configure**. Saving options triggers a full reload of the config entry (via `_async_update_listener`), which restarts the coordinator with the new interval.

## Sensor unique IDs

Each sensor's unique ID is `{entry_id}_{waste_type}_{suffix}`, e.g.:
- `abc123_packaging_next_date`
- `abc123_packaging_days_remaining`

This ensures sensors survive HA restarts and renames without creating duplicates.

## Device grouping

All six sensors are grouped under a single virtual device (`device_info` with `identifiers={(DOMAIN, entry.entry_id)}`), so they appear together in **Settings → Devices & Services → Devices**.

## Refresh cadence

nemenkom.lt publishes new PDFs quarterly. The default 7-day refresh means the integration picks up a new schedule file within one week of publication. The coordinator also refreshes on HA startup.

### Two refresh clocks, not one

`days_remaining` and `next_date` depend on wall-clock time, not just on the scraped data — they must change every day even though the coordinator only re-scrapes weekly. `CoordinatorEntity` alone does **not** do this: it only calls `async_write_ha_state()` when the coordinator fetches new data or on HA restart, so a purely-dynamic `native_value` property looks correct right after a refresh and then silently goes stale until the next one.

`sensor.py` works around this with its own hourly timer (`async_track_time_interval` in `_BaseSensor.async_added_to_hass`) that calls `async_write_ha_state()` independently of the coordinator. This just re-reads the already-cached `upcoming_dates` and recomputes — no network call, no re-scrape.

## Known limitations

- **Quarter gap**: When the current quarter's PDFs expire and the new ones are not yet published, `upcoming_dates` will be empty and sensors will show `None`. This is expected; the integration recovers automatically on the next successful fetch.
- **PDF layout changes**: If nemenkom.lt redesigns their PDF table structure, `_find_header_row()` or the street cell detection may need updating. Enable `custom_components.nemenkom_trash: debug` logging to diagnose.
- **Glass frequency**: Glass is collected less frequently; some months have no date for a given street. The sensor shows `None` days remaining when no future date exists in the current schedule file.

## Adding support for a different street

In **Settings → Integrations → Nemenkom Trash → Configure**, change the street name. The integration reloads automatically.

If the street name contains diacritics and isn't being matched, check that the PDF spells it the same way. Add extra aliases by modifying `_street_aliases()` in `coordinator.py`.
