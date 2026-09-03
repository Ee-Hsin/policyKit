"""Normalize user-facing hiring locations into policy scope identifiers."""

import re

JURISDICTION_ALIASES = {
    "united states": "US",
    "us": "US",
    "usa": "US",
    "remote us": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "gb": "GB",
    "canada": "CA",
    "san francisco": "US-CA",
    "los angeles": "US-CA",
    "new york city": "US-NY",
}

US_STATE_CODES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "washington state": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}
US_STATE_CODE_SET = set(US_STATE_CODES.values())


def _resolve_alias(value: str) -> str | None:
    if value in JURISDICTION_ALIASES:
        return JURISDICTION_ALIASES[value]
    if value in US_STATE_CODES:
        return f"US-{US_STATE_CODES[value]}"
    upper = value.upper()
    if upper in US_STATE_CODE_SET:
        return f"US-{upper}"
    return None


def normalize_location(location: str) -> str:
    normalized = re.sub(r"\s+", " ", location.strip().lower())
    code = location.strip().upper()
    state_code = re.fullmatch(r"US-([A-Z]{2})", code)
    if state_code and state_code.group(1) in US_STATE_CODE_SET:
        return code
    direct = _resolve_alias(normalized)
    if direct:
        return direct
    collapsed = re.sub(r"\s*[-,/|]\s*", " ", normalized)
    collapsed = re.sub(r"\s+", " ", collapsed)
    direct = _resolve_alias(collapsed)
    if direct:
        return direct
    parts = [part.strip() for part in re.split(r"[-,/|]", normalized) if part.strip()]
    for part in reversed(parts):
        resolved = _resolve_alias(part)
        if resolved:
            return resolved
    return f"UNRESOLVED:{location.strip()}"


def resolve_jurisdictions(locations: list[str]) -> tuple[list[str], list[str]]:
    resolved: list[str] = []
    unresolved: list[str] = []
    for location in locations:
        jurisdiction = normalize_location(location)
        if jurisdiction.startswith("UNRESOLVED:"):
            unresolved.append(location)
        elif jurisdiction not in resolved:
            resolved.append(jurisdiction)
    if resolved and "US" not in resolved and any(item.startswith("US-") for item in resolved):
        resolved.insert(0, "US")
    return resolved, unresolved
