import io
import logging
from datetime import date, datetime

import openpyxl
from openpyxl.cell.cell import Cell

logger = logging.getLogger(__name__)


def _as_date(cell: Cell) -> date | None:
    """Return a date if the cell holds a date/datetime value, otherwise None."""
    if isinstance(cell.value, datetime):
        return cell.value.date()
    if isinstance(cell.value, date):
        return cell.value
    # openpyxl can read date cells as floats when data_only=True and the workbook
    # caches are stale. Check the number format as a fallback.
    if isinstance(cell.value, (int, float)) and cell.number_format:
        fmt = cell.number_format.lower()
        if any(x in fmt for x in ["yy", "mm", "dd", "d/"]):
            try:
                return datetime.fromordinal(
                    datetime(1899, 12, 30).toordinal() + int(cell.value)
                ).date()
            except (ValueError, OverflowError):
                pass
    return None


def extract_dates_from_excel(
    excel_bytes: bytes,
    street_aliases: list[str],
) -> list[date]:
    """Extract all collection dates for the given street from an Excel timetable."""
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=True)
    collected: list[date] = []
    aliases_lower = [a.lower() for a in street_aliases]

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for row in ws.iter_rows():
            street_col = None
            for cell in row:
                if cell.value and any(a in str(cell.value).lower() for a in aliases_lower):
                    street_col = cell.column
                    break

            if street_col is None:
                continue

            for cell in row:
                if cell.column <= street_col:
                    continue
                d = _as_date(cell)
                if d:
                    collected.append(d)

    result = sorted(set(collected))
    logger.debug("Excel extracted %d dates", len(result))
    return result
