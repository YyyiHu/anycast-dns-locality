#!/usr/bin/env python3

import argparse
import csv
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests

ATLAS_PROBES_URL = "https://atlas.ripe.net/api/v2/probes/"

EU_COUNTRIES = [
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
]

REQUIRED_PROBE_TAG = "system-ipv4-works"


def read_targets(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file, delimiter="\t"))

    if not rows:
        raise ValueError(f"Target TSV is empty: {path}")

    required_columns = {"ccTLD", "zone", "nameserver", "ipv4", "analysis_role"}
    missing = required_columns.difference(rows[0].keys())

    if missing:
        raise ValueError(f"Missing target TSV columns: {sorted(missing)}")

    return rows


def get_tag_slugs(probe: dict[str, Any]) -> set[str]:
    tags = probe.get("tags") or []

    return {tag.get("slug", "") for tag in tags if isinstance(tag, dict)}


def is_usable_ipv4_probe(probe: dict[str, Any], country: str) -> bool:
    status = probe.get("status") or {}

    if status.get("id") != 1:
        return False

    if probe.get("country_code") != country:
        return False

    if not probe.get("address_v4"):
        return False

    if probe.get("asn_v4") in (None, ""):
        return False

    return REQUIRED_PROBE_TAG in get_tag_slugs(probe)


def fetch_country_probes(country: str, timeout: int) -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []

    params: dict[str, Any] | None = {
        "country_code": country,
        "status": 1,
        "page_size": 500,
    }

    url: str | None = ATLAS_PROBES_URL

    while url:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()

        data = response.json()

        for probe in data.get("results", []):
            if is_usable_ipv4_probe(probe, country):
                probes.append(probe)

        url = data.get("next")
        params = None

    return probes


def select_country_probes(
    probes: list[dict[str, Any]],
    requested_per_country: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    shuffled = probes[:]
    rng.shuffle(shuffled)

    selected: list[dict[str, Any]] = []
    used_asns: set[int] = set()

    for probe in shuffled:
        asn_v4 = probe.get("asn_v4")

        if asn_v4 in used_asns:
            continue

        selected.append(probe)
        used_asns.add(asn_v4)

        if len(selected) == requested_per_country:
            return selected

    for probe in shuffled:
        if probe in selected:
            continue

        selected.append(probe)

        if len(selected) == requested_per_country:
            return selected

    return selected


def build_probe_panel(
    probes_per_country: int,
    seed: int,
    timeout: int,
    allow_shortage: bool,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    panel: list[dict[str, Any]] = []
    shortages: dict[str, int] = {}

    for country in EU_COUNTRIES:
        probes = fetch_country_probes(country=country, timeout=timeout)
        selected = select_country_probes(
            probes=probes,
            requested_per_country=probes_per_country,
            rng=rng,
        )

        if len(selected) < probes_per_country:
            shortages[country] = len(selected)

        print(f"{country}: selected {len(selected)} of {len(probes)} usable connected IPv4 probes")

        for probe in selected:
            panel.append(
                {
                    "probe_id": probe["id"],
                    "country": country,
                    "asn_v4": probe.get("asn_v4"),
                    "is_anchor": probe.get("is_anchor"),
                }
            )

    if shortages and not allow_shortage:
        shortage_text = ", ".join(
            f"{country}={count}" for country, count in sorted(shortages.items())
        )

        raise RuntimeError(
            f"Not enough usable probes for all EU countries. "
            f"Requested {probes_per_country} per country, but got: {shortage_text}. "
            f"Either reduce --probes-per-country or rerun with --allow-shortage."
        )

    return panel


def write_probe_panel(panel: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "probe_id",
        "country",
        "asn_v4",
        "is_anchor",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(panel)


def normalize_zone(zone: str) -> str:
    return f"{zone.strip().lstrip('.')}."


def safe_tag(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(".", "-")
        .replace("_", "-")
        .replace("/", "-")
        .replace("@", "-")
        .replace(" ", "-")
    )


def build_definition(row: dict[str, str], campaign_tag: str) -> dict[str, Any]:
    zone = normalize_zone(row["zone"])
    nameserver = row["nameserver"].strip()
    target_ip = row["ipv4"].strip()
    role = row["analysis_role"].strip()

    return {
        "description": f"{campaign_tag} SOA NSID {zone} via {nameserver} {target_ip}",
        "type": "dns",
        "af": 4,
        "target": target_ip,
        "query_argument": zone,
        "query_type": "SOA",
        "query_class": "IN",
        "use_probe_resolver": False,
        "set_rd_bit": False,
        "set_nsid_bit": True,
        "include_abuf": True,
        "include_qbuf": True,
        "resolve_on_probe": False,
        "tags": [
            "thesis",
            "authoritative-dns",
            "cctld",
            "soa",
            "nsid",
            campaign_tag,
            f"zone-{safe_tag(zone)}",
            f"ns-{safe_tag(nameserver)}",
            f"role-{safe_tag(role)}",
        ],
    }


def build_payload(
    targets: list[dict[str, str]],
    probe_panel: list[dict[str, Any]],
    campaign_tag: str,
    start_delay_seconds: int,
) -> dict[str, Any]:
    probe_ids = [str(row["probe_id"]) for row in probe_panel]

    return {
        "definitions": [build_definition(row=row, campaign_tag=campaign_tag) for row in targets],
        "probes": [
            {
                "requested": len(probe_ids),
                "type": "probes",
                "value": ",".join(probe_ids),
            }
        ],
        "is_oneoff": True,
        "is_public": True,
        "start_time": int(time.time()) + start_delay_seconds,
    }


def write_json(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def print_probe_panel_summary(panel: list[dict[str, Any]]) -> None:
    country_counts: dict[str, int] = defaultdict(int)
    country_asns: dict[str, set[int]] = defaultdict(set)

    for probe in panel:
        country = str(probe["country"])
        country_counts[country] += 1

        asn_v4 = probe.get("asn_v4")
        if asn_v4 not in (None, ""):
            country_asns[country].add(int(asn_v4))

    print()
    print("Country probe counts:")

    for country in EU_COUNTRIES:
        print(
            f"  {country}: {country_counts[country]} probes, "
            f"{len(country_asns[country])} distinct IPv4 ASNs"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the dry run RIPE Atlas SOA NSID campaign payload."
    )

    parser.add_argument(
        "--targets",
        default="data/input/active_measurement_targets.tsv",
        help="Input active target TSV.",
    )

    parser.add_argument(
        "--probe-panel",
        default="data/input/eu_probe_panel.tsv",
        help="Output fixed EU probe panel TSV.",
    )

    parser.add_argument(
        "--output",
        default="results/atlas/atlas_dns_soa_nsid_dry_run.json",
        help="Output dry run Atlas JSON payload.",
    )

    parser.add_argument(
        "--probes-per-country",
        type=int,
        default=3,
        help="Number of probes to select per EU country.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=20260522,
        help="Random seed for reproducible probe selection.",
    )

    parser.add_argument(
        "--campaign-tag",
        default="thesis-anycast-locality",
        help="Campaign tag added to measurement definitions.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout for RIPE Atlas probe API requests.",
    )

    parser.add_argument(
        "--start-delay-seconds",
        type=int,
        default=600,
        help="Start time delay stored in the generated Atlas payload.",
    )

    parser.add_argument(
        "--allow-shortage",
        action="store_true",
        help="Allow countries with fewer selected probes than requested.",
    )

    args = parser.parse_args()

    if args.probes_per_country < 1:
        raise ValueError("--probes-per-country must be at least 1.")

    targets = read_targets(Path(args.targets))

    probe_panel = build_probe_panel(
        probes_per_country=args.probes_per_country,
        seed=args.seed,
        timeout=args.timeout,
        allow_shortage=args.allow_shortage,
    )

    write_probe_panel(
        panel=probe_panel,
        output_path=Path(args.probe_panel),
    )

    payload = build_payload(
        targets=targets,
        probe_panel=probe_panel,
        campaign_tag=args.campaign_tag,
        start_delay_seconds=args.start_delay_seconds,
    )

    write_json(
        payload=payload,
        output_path=Path(args.output),
    )

    print_probe_panel_summary(probe_panel)

    print()
    print(f"Wrote fixed probe panel to {args.probe_panel}")
    print(f"Wrote dry run payload to {args.output}")
    print(f"Targets: {len(targets)}")
    print(f"Selected probes: {len(probe_panel)}")
    print(f"Expected one off DNS results: {len(targets) * len(probe_panel)}")
    print("No RIPE Atlas measurement was submitted.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.RequestException as error:
        print(f"RIPE Atlas API request failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
