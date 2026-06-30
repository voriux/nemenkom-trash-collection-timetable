"""DataUpdateCoordinator — fetches and parses the nemenkom.lt schedules."""

import logging
from datetime import date, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, WASTE_TYPES
from .scraper.website_scraper import WasteType, fetch_latest_schedule_files, download_file
from .scraper.pdf_parser import extract_dates_from_pdf
from .scraper.excel_parser import extract_dates_from_excel

logger = logging.getLogger(__name__)


def _street_aliases(street: str) -> list[str]:
    """Return lookup aliases for the configured street name.

    Adds both the original string and a diacritics-stripped variant so that
    minor encoding differences in PDFs don't break matching.
    """
    aliases = [street]
    stripped = (
        street.lower()
        .replace("ė", "e").replace("ę", "e").replace("ū", "u").replace("ų", "u")
        .replace("ą", "a").replace("š", "s").replace("ž", "z").replace("č", "c")
        .replace("į", "i").replace("ï", "i")
    )
    if stripped not in aliases:
        aliases.append(stripped)
    return aliases


def _build_collection_info(dates: list[date]) -> dict:
    # Store all dates as ISO strings; sensors recompute next_date and days_remaining
    # dynamically against date.today() so the value stays accurate between scrapes.
    future = sorted(d for d in dates if d >= date.today())
    return {"upcoming_dates": [d.isoformat() for d in future]}


def _run_scraper(street: str) -> dict[str, dict]:
    """Synchronous scraper — called in an executor thread by the coordinator."""
    aliases = _street_aliases(street)
    current_year = date.today().year

    schedule_files = fetch_latest_schedule_files()
    result: dict[str, dict] = {wt: _build_collection_info([]) for wt in WASTE_TYPES}

    for waste_type_enum, schedule_file in schedule_files.items():
        waste_key = waste_type_enum.value
        logger.debug("Downloading %s: %s", waste_key, schedule_file.url)

        try:
            raw = download_file(schedule_file.url)
        except Exception as exc:
            logger.warning("Download failed for %s: %s", waste_key, exc)
            continue

        try:
            if schedule_file.file_extension == "xlsx":
                dates = extract_dates_from_excel(raw, aliases)
            else:
                dates = extract_dates_from_pdf(raw, aliases, target_year=current_year)
        except Exception as exc:
            logger.warning("Parse failed for %s: %s", waste_key, exc)
            continue

        logger.debug("Found %d dates for %s", len(dates), waste_key)
        result[waste_key] = _build_collection_info(dates)

    if not any(result.get(wt, {}).get("upcoming_dates") for wt in WASTE_TYPES):
        raise RuntimeError(
            "No schedule data found for any waste type — "
            "the website may be unreachable or the page structure has changed"
        )

    return result


class NemenkomTrashCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Coordinator that periodically refreshes the trash collection schedule."""

    def __init__(self, hass: HomeAssistant, street: str, update_interval_hours: int) -> None:
        self.street = street
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(hours=update_interval_hours),
        )

    async def _async_update_data(self) -> dict[str, dict]:
        try:
            return await self.hass.async_add_executor_job(_run_scraper, self.street)
        except Exception as exc:
            raise UpdateFailed(f"Error fetching nemenkom.lt schedule: {exc}") from exc
