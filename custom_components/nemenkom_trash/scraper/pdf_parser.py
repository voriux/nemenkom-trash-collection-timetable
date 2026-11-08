"""
PDF parser for Nemenčinės komunalininkas waste collection timetables (published on vrsa.lt).

Two layouts are in use (inspected Oct–Dec 2026 files):

Packaging / glass:
  Col 0: locations (many streets in one cell) | Col 1: waste type | Col 2+: months ("Spalio", ...)
  Cells: "9 d." or empty. Only the first page's table carries the month header row;
  tables on later pages continue it without a header.

Household:
  Col 0: seniūnija | Col 1: villages and streets | Col 2: weekday | Col 3+: months ("Birželis", ...)
  Cells: several days, e.g. "1d., 15d., 29d.,".

So the parser treats every non-month column as location text and reads every day number in a month cell.
"""

import io
import re
import logging
import unicodedata
from datetime import date

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

# Every day number in a cell: "9 d.", "14d., 28d.,", "2 d., 16 d., 30 d."
DAY_PATTERN = re.compile(r"\b(\d{1,2})\s*d\b")


def _cell_str(cell) -> str:
    return (cell or "").strip()


def _build_col_month_map(row: list) -> dict[int, int]:
    col_months: dict[int, int] = {}
    # Whole-cell match only: street names like "Kovo 11-osios g." must not read as a header.
    for col_idx, cell in enumerate(row):
        num = HEADER_TO_MONTH.get(_cell_str(cell).lower())
        if num:
            col_months[col_idx] = num
    return col_months


def _find_header_row(table: list[list]) -> tuple[int, dict[int, int]]:
    for row_idx, row in enumerate(table[:6]):
        col_months = _build_col_month_map(row)
        if col_months:
            return row_idx, col_months
    return -1, {}


def _normalize(text: str) -> str:
    """Lowercase, drop diacritics, collapse whitespace; PDF cells wrap mid-name ("Žirgupės\\ng.")."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split())


def _street_in_cell(text: str, street_aliases: list[str]) -> bool:
    text = _normalize(text)
    return any(_normalize(alias) in text for alias in street_aliases)


def _parse_days(text: str) -> list[int]:
    return [d for d in map(int, DAY_PATTERN.findall(text)) if 1 <= d <= 31]


def extract_dates_from_pdf(pdf_bytes: bytes, street_aliases: list[str], year: int) -> list[date]:
    """Extract all collection dates for the given street from a PDF timetable covering one year."""
    collected: list[date] = []
    col_months: dict[int, int] = {}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            for table in page.extract_tables() or []:
                header_idx, own_months = _find_header_row(table)
                if own_months:
                    col_months = own_months
                elif not col_months:
                    continue

                for row_idx, row in enumerate(table):
                    if row_idx <= header_idx:
                        continue

                    location = " ".join(_cell_str(c) for i, c in enumerate(row) if i not in col_months)
                    if not _street_in_cell(location, street_aliases):
                        continue

                    logger.debug("Page %d row %d matched: %s", page_num + 1, row_idx, location)

                    for col_idx, month in col_months.items():
                        if col_idx >= len(row):
                            continue
                        for day in _parse_days(_cell_str(row[col_idx])):
                            try:
                                collected.append(date(year, month, day))
                            except ValueError:
                                pass

    result = sorted(set(collected))
    logger.debug("PDF extracted %d dates", len(result))
    return result
