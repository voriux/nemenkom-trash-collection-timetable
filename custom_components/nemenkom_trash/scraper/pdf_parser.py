"""
PDF parser for nemenkom.lt waste collection timetables.

Confirmed table structure (inspected July–September 2026 PDFs):
  Column 0: Location/street names — one cell lists multiple streets, comma-separated
  Column 1: Waste type label ("Pakuotė", "Stiklas", ...)
  Column 2+: Month columns — header is a Lithuanian month name, cells contain "X d." or empty

Example packaging row:
  "Avižienių mstl. tik. Gailašių g., Skandinavijos al., Vaikystės g." | Pakuotė | 10 d. | 11 d. | 9 d.

Example glass row:
  "Avižienių mstl. ... Vaikystės g., ..." | Stiklas | (empty) | 31 d. | (empty)
"""

import io
import re
import logging
from datetime import date, datetime

import pdfplumber

logger = logging.getLogger(__name__)

HEADER_TO_MONTH: dict[str, int] = {
    "sausis": 1, "sausio": 1,
    "vasaris": 2, "vasario": 2,
    "kovas": 3, "kovo": 3,
    "balandis": 4, "balandžio": 4,
    "gegužė": 5, "gegužės": 5,
    "birželis": 6, "birželio": 6,
    "liepa": 7, "liepos": 7,
    "rugpjūtis": 8, "rugpjūčio": 8,
    "rugsėjis": 9, "rugsėjo": 9,
    "spalis": 10, "spalio": 10,
    "lapkritis": 11, "lapkričio": 11,
    "gruodis": 12, "gruodžio": 12,
}

# Matches "10 d.", "10d.", "10", "10."
DAY_PATTERN = re.compile(r"^\s*(\d{1,2})\s*d?\.?\s*$")


def _cell_str(cell) -> str:
    return (cell or "").strip()


def _build_col_month_map(row: list) -> dict[int, int]:
    col_months: dict[int, int] = {}
    for col_idx, cell in enumerate(row):
        text = _cell_str(cell).lower()
        for name, num in HEADER_TO_MONTH.items():
            if name in text:
                col_months[col_idx] = num
                break
    return col_months


def _find_header_row(table: list[list]) -> tuple[int, dict[int, int]]:
    for row_idx, row in enumerate(table[:6]):
        col_months = _build_col_month_map(row)
        if col_months:
            return row_idx, col_months
    return -1, {}


def _street_in_cell(text: str, street_aliases: list[str]) -> bool:
    text_lower = text.lower()
    return any(alias.lower() in text_lower for alias in street_aliases)


def _parse_day(text: str) -> int | None:
    m = DAY_PATTERN.match(text)
    if m:
        day = int(m.group(1))
        if 1 <= day <= 31:
            return day
    return None


def extract_dates_from_pdf(
    pdf_bytes: bytes,
    street_aliases: list[str],
    target_year: int | None = None,
) -> list[date]:
    """Extract all collection dates for the given street from a PDF timetable."""
    if target_year is None:
        target_year = datetime.now().year

    collected: list[date] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            for table in page.extract_tables() or []:
                if not table:
                    continue

                header_idx, col_months = _find_header_row(table)
                if not col_months:
                    continue

                for row_idx, row in enumerate(table):
                    if row_idx <= header_idx:
                        continue

                    location = _cell_str(row[0] if row else "")
                    if not _street_in_cell(location, street_aliases):
                        continue

                    logger.debug("Page %d row %d matched: %s", page_num + 1, row_idx, location)

                    for col_idx, cell in enumerate(row):
                        month = col_months.get(col_idx)
                        if month is None:
                            continue
                        day = _parse_day(_cell_str(cell))
                        if day is not None:
                            try:
                                collected.append(date(target_year, month, day))
                            except ValueError:
                                pass

    result = sorted(set(collected))
    logger.debug("PDF extracted %d dates", len(result))
    return result
