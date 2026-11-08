import sys
from datetime import date
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
# Import the scraper modules directly: the package __init__ needs Home Assistant.
sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components" / "nemenkom_trash" / "scraper"))

from pdf_parser import extract_dates_from_pdf  # noqa: E402
from website_scraper import WasteType, parse_schedule_page  # noqa: E402

STREET = ["Vaikystės g.", "vaikystes g."]


def dates(*pairs):
    return [date(2026, m, d) for m, d in pairs]


@pytest.mark.parametrize("fixture, expected", [
    # Vaikystės g. sits on page 2, in a table without its own month header.
    ("2026-q4-packaging.pdf", dates((10, 9), (11, 10), (12, 9))),
    ("2026-q4-glass.pdf", dates((11, 27))),
    # Household layout: streets in column 1, several days per cell.
    ("2026-h2-household.pdf", dates(
        (6, 2), (6, 16), (6, 30), (7, 14), (7, 28), (8, 11), (8, 25), (9, 8), (9, 22),
        (10, 6), (10, 20), (11, 3), (11, 17), (12, 1), (12, 15), (12, 29),
    )),
])
def test_pdf_dates_for_street(fixture, expected):
    assert extract_dates_from_pdf((FIXTURES / fixture).read_bytes(), STREET, year=2026) == expected


def test_page_picks_newest_nemencine_files():
    files = parse_schedule_page((FIXTURES / "vrsa_schedule_page.html").read_text(encoding="utf-8"))
    newest = {wt: fs[0] for wt, fs in files.items()}

    assert all(len(fs) == 2 for fs in files.values())
    assert all("Nemenčinės" in f.title for fs in files.values() for f in fs)
    assert newest[WasteType.HOUSEHOLD].url.endswith("kopija-2026-m.-birzelis-gruodis-men-buitiniu-atlieku-surinkimo-grafikas.pdf")
    assert "stiklo" in newest[WasteType.GLASS].url and "2026-m.-spalio" in newest[WasteType.GLASS].url
    assert "stiklo" not in newest[WasteType.PACKAGING].url and "2026-m.-spalio" in newest[WasteType.PACKAGING].url
    assert {f.year for f in newest.values()} == {2026}
