"""Normalize user-facing hiring locations into policy scope identifiers."""

import re

JURISDICTION_ALIASES = {
    "global": "GLOBAL",
    "united states": "US",
    "us": "US",
    "usa": "US",
    "new york": "US-NY",
    "ny": "US-NY",
    "california": "US-CA",
    "ca": "US-CA",
    "colorado": "US-CO",
    "co": "US-CO",
    "washington": "US-WA",
    "washington state": "US-WA",
    "wa": "US-WA",
    "remote us": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "canada": "CA",
}


def normalize_location(location: str) -> str:
    normalized = re.sub(r"\s+", " ", location.strip().lower())
    if normalized in JURISDICTION_ALIASES:
        return JURISDICTION_ALIASES[normalized]
    if re.fullmatch(r"[A-Za-z]{2}(?:-[A-Za-z]{2,3})?", location.strip()):
        return location.strip().upper()
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
