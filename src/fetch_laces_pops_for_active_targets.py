import csv
import json
import re
from pathlib import Path
from typing import Any

import requests

INPUT_FILE = Path("data/input/active_measurement_targets.tsv")
RAW_DIR = Path("data/raw/laces/active_measurement_targets")
OUTPUT_FILE = Path("data/processed/laces/active_measurement_laces_pops.tsv")

BASE_URL = "https://manycast.net/api/v1/ip"
TIMEOUT_SECONDS = 20


EU_COUNTRIES = {
    "AT",
    "BE",
    "BG",
    "HR",
    "CY",
    "CZ",
    "DK",
    "EE",
    "FI",
    "FR",
    "DE",
    "GR",
    "HU",
    "IE",
    "IT",
    "LV",
    "LT",
    "LU",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "SK",
    "SI",
    "ES",
    "SE",
}


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", value)


def fetch_laces_ip_result(ipv4: str) -> dict[str, Any]:
    response = requests.get(f"{BASE_URL}/{ipv4}", timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def stringify(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        return "; ".join(str(item) for item in value)

    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)

    return str(value)


def get_locations(data: dict[str, Any]) -> list[dict[str, Any]]:
    locations = data.get("locations")

    if not isinstance(locations, list):
        return []

    return [location for location in locations if isinstance(location, dict)]


def unique_locations(locations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []

    for location in locations:
        location_id = location.get("id")
        city = location.get("city")
        country = location.get("country")
        latitude = location.get("latitude")
        longitude = location.get("longitude")

        key = location_id or f"{city}:{country}:{latitude}:{longitude}"

        if key in seen:
            continue

        seen.add(key)
        unique.append(location)

    return unique


def summarize_locations(data: dict[str, Any]) -> dict[str, Any]:
    locations = unique_locations(get_locations(data))

    pop_ids = sorted(location["id"] for location in locations if location.get("id"))

    pop_cities = sorted(
        f"{location.get('city') or 'Unknown'} ({location.get('country') or '??'})"
        for location in locations
    )

    countries = sorted({location["country"] for location in locations if location.get("country")})

    eu_pop_count = sum(1 for location in locations if location.get("country") in EU_COUNTRIES)

    uk_pop_count = sum(1 for location in locations if location.get("country") == "GB")

    ch_pop_count = sum(1 for location in locations if location.get("country") == "CH")

    unknown_country_pop_count = sum(1 for location in locations if not location.get("country"))

    known_non_eu_pop_count = sum(
        1
        for location in locations
        if location.get("country") and location.get("country") not in EU_COUNTRIES
    )

    return {
        "laces_gcd_pop_count": len(locations),
        "laces_gcd_pop_ids": "; ".join(pop_ids),
        "laces_gcd_pop_cities": "; ".join(pop_cities),
        "laces_gcd_pop_countries": "; ".join(countries),
        "laces_eu_pop_count": eu_pop_count,
        "laces_known_non_eu_pop_count": known_non_eu_pop_count,
        "laces_uk_pop_count": uk_pop_count,
        "laces_ch_pop_count": ch_pop_count,
        "laces_unknown_country_pop_count": unknown_country_pop_count,
    }


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with INPUT_FILE.open(newline="") as file:
        targets = list(csv.DictReader(file, delimiter="\t"))

    rows = []

    for target in targets:
        cctld = target["ccTLD"]
        zone = target["zone"]
        nameserver = target["nameserver"]
        ipv4 = target["ipv4"]
        analysis_role = target["analysis_role"]

        print(f"Fetching LACeS data for {cctld} {nameserver} {ipv4}")

        try:
            data = fetch_laces_ip_result(ipv4)
            status = "ok"
            error = ""
        except requests.RequestException as exception:
            data = {}
            status = "error"
            error = str(exception)

        raw_file = RAW_DIR / (f"{safe_name(cctld)}_{safe_name(nameserver)}_{safe_name(ipv4)}.json")
        raw_file.write_text(json.dumps(data, indent=2, sort_keys=True))

        rows.append(
            {
                "ccTLD": cctld,
                "zone": zone,
                "nameserver": nameserver,
                "ipv4": ipv4,
                "analysis_role": analysis_role,
                "laces_status": status,
                "laces_error": error,
                "laces_prefix": stringify(data.get("prefix")),
                "backing_prefix": stringify(data.get("backing_prefix")),
                "asn": stringify(data.get("ASN") or data.get("asn")),
                "partial_anycast": stringify(data.get("partial")),
                **summarize_locations(data),
            }
        )

    fieldnames = [
        "ccTLD",
        "zone",
        "nameserver",
        "ipv4",
        "analysis_role",
        "laces_status",
        "laces_error",
        "laces_prefix",
        "backing_prefix",
        "asn",
        "partial_anycast",
        "laces_gcd_pop_count",
        "laces_gcd_pop_ids",
        "laces_gcd_pop_cities",
        "laces_gcd_pop_countries",
        "laces_eu_pop_count",
        "laces_known_non_eu_pop_count",
        "laces_uk_pop_count",
        "laces_ch_pop_count",
        "laces_unknown_country_pop_count",
    ]

    with OUTPUT_FILE.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
