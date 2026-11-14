from app.importer import _parse_date
from datetime import date

def test_parse_iso_date():
    assert _parse_date('2026-10-01') == date(2026,10,1)

def test_parse_invalid_date():
    assert _parse_date('not-a-date') is None
