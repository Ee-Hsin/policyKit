import pytest

from app.services.jurisdictions import normalize_location, resolve_jurisdictions


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        (" New   York ", "US-NY"),
        ("ny", "US-NY"),
        ("California", "US-CA"),
        ("remote us", "US"),
        ("Remote - US", "US"),
        ("San Francisco", "US-CA"),
        ("San Francisco, CA", "US-CA"),
        ("Massachusetts", "US-MA"),
        ("ma", "US-MA"),
        ("New York, NY", "US-NY"),
        ("London, UK", "GB"),
        ("Toronto, Canada", "CA"),
        ("gb", "GB"),
        ("US-wa", "US-WA"),
        ("Global", "UNRESOLVED:Global"),
        ("zz", "UNRESOLVED:zz"),
        ("Atlantis", "UNRESOLVED:Atlantis"),
    ],
)
def test_normalize_location(location: str, expected: str) -> None:
    assert normalize_location(location) == expected


def test_resolve_jurisdictions_deduplicates_and_adds_country_scope() -> None:
    resolved, unresolved = resolve_jurisdictions(["New York", "ny", "California", "Moon Base"])

    assert resolved == ["US", "US-NY", "US-CA"]
    assert unresolved == ["Moon Base"]


def test_resolve_jurisdictions_does_not_add_duplicate_country_scope() -> None:
    resolved, unresolved = resolve_jurisdictions(["United States", "Washington State"])

    assert resolved == ["US", "US-WA"]
    assert unresolved == []
