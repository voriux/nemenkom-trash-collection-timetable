import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from enum import Enum

# Vilnius district municipality republishes the Nemenkom files; nemenkom.lt itself is unreliable.
BASE_URL = "https://vrsa.lt"
SCHEDULE_PAGE = f"{BASE_URL}/atlieku-tvarkymas/atlieku-surinkimo-grafikai/404"
# The page has one section per waste company; other companies' files list the same street names.
COMPANY_SECTION = "Nemenčinės komunalininkas"
# A new period's file appears before the current one ends, so read the current and the next one.
FILES_PER_TYPE = 2

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; HomeAssistant/NemenkomTrash)"}

PACKAGING_KEYWORDS = ["pakuočių atliekų surinkimo grafikas"]
GLASS_KEYWORDS = ["stiklo pakuočių atliekų surinkimo grafikas"]
HOUSEHOLD_KEYWORDS = ["buitinių atliekų surinkimo grafikas"]


class WasteType(Enum):
    PACKAGING = "packaging"
    GLASS = "glass"
    HOUSEHOLD = "household"


@dataclass
class ScheduleFile:
    waste_type: WasteType
    url: str
    title: str
    file_extension: str
    year: int


def _classify_link(title: str, href: str) -> WasteType | None:
    title_lower = title.lower()
    href_lower = href.lower()

    # Glass must be checked before packaging — glass titles also contain "pakuočių".
    # "stiklo" in the title is the reliable discriminator; the full keyword and
    # href stem are additional fallbacks.
    for keyword in GLASS_KEYWORDS:
        if "stiklo" in title_lower or keyword in title_lower or "stiklo" in href_lower:
            return WasteType.GLASS

    for keyword in PACKAGING_KEYWORDS:
        if keyword in title_lower:
            return WasteType.PACKAGING

    for keyword in HOUSEHOLD_KEYWORDS:
        if keyword in title_lower or "buitini" in href_lower:
            return WasteType.HOUSEHOLD

    return None


def _extract_year_month(title: str) -> tuple[int, int]:
    year_match = re.search(r"(\d{4})", title)
    year = int(year_match.group(1)) if year_match else 0

    month_stems = {
        "saus": 1, "vasar": 2, "kov": 3, "baland": 4,
        "gegu": 5, "biržel": 6, "birzel": 6, "liepos": 7,
        "rugpjūč": 8, "rugpjuc": 8, "rugsėj": 9, "rugse": 9,
        "spalio": 10, "lapkr": 11, "gruod": 12,
    }
    title_lower = title.lower()
    month = 0
    for stem, num in month_stems.items():
        if stem in title_lower and num > month:
            month = num

    return (year, month)


def fetch_latest_schedule_files() -> dict[WasteType, list[ScheduleFile]]:
    """Return the newest FILES_PER_TYPE schedule files per waste type, newest first."""
    response = requests.get(SCHEDULE_PAGE, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return parse_schedule_page(response.text)


def parse_schedule_page(page_html: str) -> dict[WasteType, list[ScheduleFile]]:
    soup = BeautifulSoup(page_html, "lxml")
    section = next(
        (s for s in soup.select("section") if s.find("h2") and COMPANY_SECTION in s.find("h2").get_text()),
        None,
    )
    if section is None:
        raise RuntimeError(f"No '{COMPANY_SECTION}' section on {SCHEDULE_PAGE}")

    candidates: dict[WasteType, list[tuple[tuple[int, int], ScheduleFile]]] = {wt: [] for wt in WasteType}

    for anchor in section.find_all("a", href=True):
        href: str = anchor["href"]
        if not (href.endswith(".pdf") or href.endswith(".xlsx")):
            continue

        title = anchor.get_text(strip=True) or href
        waste_type = _classify_link(title, href)
        if waste_type is None:
            continue

        year_month = _extract_year_month(title)
        candidates[waste_type].append((year_month, ScheduleFile(
            waste_type=waste_type,
            url=href if href.startswith("http") else BASE_URL + href,
            title=title,
            file_extension="xlsx" if href.endswith(".xlsx") else "pdf",
            year=year_month[0],
        )))

    result: dict[WasteType, list[ScheduleFile]] = {}
    for waste_type, items in candidates.items():
        items.sort(key=lambda x: x[0], reverse=True)
        result[waste_type] = [f for _, f in items[:FILES_PER_TYPE]]
    return result


def download_file(url: str, timeout: int = 60) -> bytes:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.content
