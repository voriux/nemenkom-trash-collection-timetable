# Nemenkom Trash Collection Schedule

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration that automatically fetches waste collection dates for your street from [nemenkom.lt](https://www.nemenkom.lt/buitiniu-ir-pakuociu-atlieku-surinkimo-grafikas/) and creates sensors you can use in dashboards and push-notification automations.

No external scripts, no cron jobs, no virtual environments — everything runs inside Home Assistant.

## What it tracks

| Waste type | Source | Typical frequency |
|---|---|---|
| Packaging (Paper/Plastic/Metal) | PDF | Every 2–3 weeks |
| Glass | PDF | Monthly |
| Household Waste | Excel (.xlsx) | Weekly |

## Sensors created

For each waste type you get **two sensors**:

| Sensor | Example state | Description |
|---|---|---|
| `sensor.packaging_paper_plastic_metal_next_collection` | `2026-07-10` | ISO date of the next collection |
| `sensor.packaging_paper_plastic_metal_days_remaining` | `11` | Days until the next collection |
| `sensor.glass_next_collection` | `2026-08-31` | — |
| `sensor.glass_days_remaining` | `63` | — |
| `sensor.household_waste_next_collection` | `2026-07-01` | — |
| `sensor.household_waste_days_remaining` | `2` | — |

All sensors also carry `upcoming_dates` as an attribute (list of ISO date strings).

## Installation via HACS

### Step 1 — Add as a custom repository

1. Open HACS in Home Assistant
2. Click the three-dot menu → **Custom repositories**
3. Enter the URL of this repository and choose **Integration**
4. Click **Add**

### Step 2 — Install

1. Search for **Nemenkom Trash Collection** in HACS
2. Click **Download**
3. Restart Home Assistant

### Step 3 — Configure

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Nemenkom Trash Collection**
3. Enter your street name exactly as it appears in the nemenkom.lt PDFs (e.g. `Vaikystės g.`)
4. Set the refresh interval (default: 168 hours = weekly)
5. Click **Submit**

HA installs the required Python libraries (`pdfplumber`, `beautifulsoup4`, `openpyxl`, `lxml`) automatically on first load.

## Dashboard card

Paste this into a **Manual card** in Lovelace:

```yaml
type: entities
title: Trash Collection
entities:
  - entity: sensor.trash_collection_vaikystes_g_packaging_paper_plastic_metal_days_remaining
    name: Packaging
    icon: mdi:recycle
  - entity: sensor.trash_collection_vaikystes_g_glass_days_remaining
    name: Glass
    icon: mdi:bottle-wine
  - entity: sensor.trash_collection_vaikystes_g_household_waste_days_remaining
    name: Household Waste
    icon: mdi:trash-can
```

### Color-coded Tile cards (core HA, no HACS needed)

Each `*_days_remaining` sensor carries an `urgency` attribute (`critical` / `warning` / `normal`) computed server-side — red when the collection is today or overdue, yellow when it's less than 2 days away, otherwise green. The built-in **Tile card** can template its color straight from that attribute:

```yaml
type: tile
entity: sensor.trash_collection_vaikystes_g_packaging_paper_plastic_metal_days_remaining
name: Packaging
icon: mdi:recycle
color: >-
  {% set u = state_attr(entity, 'urgency') %}
  {% if u == 'critical' %}red
  {% elif u == 'warning' %}yellow
  {% else %}green{% endif %}
```

Duplicate for `sensor.trash_collection_vaikystes_g_glass_days_remaining` and `sensor.trash_collection_vaikystes_g_household_waste_days_remaining`.

### Mushroom card (requires [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom))

```yaml
type: custom:mushroom-template-card
primary: Packaging collection
secondary: >
  {% set d = states('sensor.trash_collection_vaikystes_g_packaging_paper_plastic_metal_days_remaining') | int(-1) %}
  {% if d == 0 %}Today!
  {% elif d == 1 %}Tomorrow
  {% elif d > 1 %}In {{ d }} days
  {% else %}No upcoming dates{% endif %}
icon: mdi:recycle
icon_color: >
  {% set u = state_attr('sensor.trash_collection_vaikystes_g_packaging_paper_plastic_metal_days_remaining', 'urgency') %}
  {% if u == 'critical' %}red
  {% elif u == 'warning' %}yellow
  {% else %}green{% endif %}
```

## Notification automation

Go to **Settings → Automations → Create Automation** and paste this YAML (adjust the `notify` service to match your phone):

```yaml
alias: "Notify: Packaging collection tomorrow"
trigger:
  - platform: time
    at: "19:00:00"
condition:
  - condition: numeric_state
    entity_id: sensor.trash_collection_vaikystes_g_packaging_paper_plastic_metal_days_remaining
    below: 2
    above: -1
action:
  - service: notify.mobile_app_f8
    data:
      title: "♻️ Packaging collection tomorrow"
      message: >
        Put out the packaging bin tonight.
        Next collection: {{ states('sensor.trash_collection_vaikystes_g_packaging_paper_plastic_metal_next_collection') }}.
```

```yaml
alias: "Notify: Glass collection tomorrow"
trigger:
  - platform: time
    at: "19:00:00"
condition:
  - condition: numeric_state
    entity_id: sensor.trash_collection_vaikystes_g_glass_days_remaining
    below: 2
    above: -1
action:
  - service: notify.mobile_app_f8
    data:
      title: "♻️ Glass collection tomorrow"
      message: >
        Put out the glass bin tonight.
        Next collection: {{ states('sensor.trash_collection_vaikystes_g_glass_next_collection') }}.
```

```yaml
alias: "Notify: Household waste collection tomorrow"
trigger:
  - platform: time
    at: "19:00:00"
condition:
  - condition: numeric_state
    entity_id: sensor.trash_collection_vaikystes_g_household_waste_days_remaining
    below: 2
    above: -1
action:
  - service: notify.mobile_app_f8
    data:
      title: "♻️ Household waste collection tomorrow"
      message: >
        Put out the house hold waste bin tonight.
        Next collection: {{ states('sensor.trash_collection_vaikystes_g_household_waste_next_collection') }}.
```

## Troubleshooting

**No dates found for a type**
The PDF layout may have changed. Enable debug logging in `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.nemenkom_trash: debug
```
Then check **Settings → System → Logs**.

**Integration fails to load**
Check that HA can reach `nemenkom.lt`. The integration requires outbound HTTPS access.

**Wrong street matched**
The street name is matched as a substring of the location cell. If your street name is a substring of another street's name, add a more specific alias or file an issue.

## Project structure

```
custom_components/nemenkom_trash/
├── manifest.json          ← declares Python deps, loaded by HA
├── __init__.py            ← entry setup / teardown
├── config_flow.py         ← UI setup wizard
├── coordinator.py         ← DataUpdateCoordinator, runs scraper weekly
├── sensor.py              ← 6 sensor entities (date + days per waste type)
├── const.py
├── strings.json
├── translations/
│   └── en.json
└── scraper/
    ├── website_scraper.py ← scrapes nemenkom.lt for latest PDF/Excel URLs
    ├── pdf_parser.py      ← extracts dates from PDF timetable tables
    └── excel_parser.py    ← extracts dates from Excel timetable files
```
