import csv
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

CREATED_FILE = Path("results/atlas/created_measurements.json")
PLAN_FILE = Path("results/atlas/measurement_plan.json")
RAW_RESULTS_DIR = Path("data/raw/atlas/results")
INVENTORY_FILE = Path("data/processed/atlas_fetch_inventory.tsv")

ATLAS_BASE_URL = "https://atlas.ripe.net/api/v2"
TIMEOUT_SECONDS = 30
EXPECTED_PROBE_COUNT = 81


def load_api_key() -> str | None:
    load_dotenv()
    return os.getenv("ATLAS_API_KEY")


def build_headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}

    return {"Authorization": f"Key {api_key}"}


def load_created_measurements() -> list[dict[str, Any]]:
    if not CREATED_FILE.exists():
        raise FileNotFoundError(f"Created measurements file not found: {CREATED_FILE}")

    data = json.loads(CREATED_FILE.read_text())
    measurements = data.get("created_measurements")

    if not isinstance(measurements, list) or not measurements:
        raise ValueError("created_measurements.json does not contain created_measurements.")

    return measurements


def load_expected_probe_ids() -> set[int]:
    if not PLAN_FILE.exists():
        raise FileNotFoundError(f"Measurement plan file not found: {PLAN_FILE}")

    data = json.loads(PLAN_FILE.read_text())
    probes = data.get("probes")

    if not isinstance(probes, list) or len(probes) != 1:
        raise ValueError("measurement_plan.json must contain exactly one probe selection.")

    probe_selection = probes[0]
    probe_value = probe_selection.get("value")

    if not isinstance(probe_value, str) or not probe_value:
        raise ValueError("Probe selection must contain comma separated probe IDs.")

    probe_ids = {int(probe_id) for probe_id in probe_value.split(",") if probe_id.strip()}

    if len(probe_ids) != EXPECTED_PROBE_COUNT:
        raise ValueError(f"Expected {EXPECTED_PROBE_COUNT} probe IDs, found {len(probe_ids)}.")

    return probe_ids


def get_measurement_status(measurement_id: int, headers: dict[str, str]) -> str:
    url = f"{ATLAS_BASE_URL}/measurements/{measurement_id}/"
    response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()

    data = response.json()
    status = data.get("status", {})

    if isinstance(status, dict):
        return str(status.get("name") or status.get("id") or "unknown")

    return str(status)


def get_latest_results(measurement_id: int, headers: dict[str, str]) -> list[dict[str, Any]]:
    url = f"{ATLAS_BASE_URL}/measurements/{measurement_id}/latest/"
    response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()

    data = response.json()

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        results = data.get("results")
        if isinstance(results, list):
            return results

    raise ValueError(f"Unexpected result shape for measurement {measurement_id}")


def get_seen_probe_ids(results: list[dict[str, Any]]) -> set[int]:
    seen_probe_ids = set()

    for result in results:
        probe_id = result.get("prb_id")

        if probe_id is None:
            continue

        seen_probe_ids.add(int(probe_id))

    return seen_probe_ids


def write_raw_results(measurement_id: int, results: list[dict[str, Any]]) -> Path:
    RAW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    output_file = RAW_RESULTS_DIR / f"{measurement_id}.json"
    output_file.write_text(json.dumps(results, indent=2, sort_keys=True))

    return output_file


def main() -> None:
    api_key = load_api_key()
    headers = build_headers(api_key)

    expected_probe_ids = load_expected_probe_ids()
    measurements = load_created_measurements()

    inventory_rows = []
    missing_probe_counter = Counter()

    for measurement in measurements:
        measurement_id = int(measurement["measurement_id"])
        target = measurement["target"]
        query_argument = measurement["query_argument"]
        description = measurement["description"]

        print(f"Fetching {measurement_id}: {description}")

        try:
            status = get_measurement_status(measurement_id, headers)
            results = get_latest_results(measurement_id, headers)
            raw_file = write_raw_results(measurement_id, results)

            seen_probe_ids = get_seen_probe_ids(results)
            missing_probe_ids = sorted(expected_probe_ids - seen_probe_ids)

            result_count = len(results)
            missing_count = len(missing_probe_ids)
            fetch_status = "ok"
            error = ""

            for probe_id in missing_probe_ids:
                missing_probe_counter[probe_id] += 1

            print(
                f"  status={status} "
                f"results={result_count}/{EXPECTED_PROBE_COUNT} "
                f"missing={missing_probe_ids} "
                f"raw={raw_file}"
            )

        except requests.RequestException as exception:
            status = "request_error"
            result_count = 0
            missing_count = EXPECTED_PROBE_COUNT
            missing_probe_ids = sorted(expected_probe_ids)
            raw_file = ""
            fetch_status = "error"
            error = str(exception)

            print(f"  error={error}")

        except ValueError as exception:
            status = "parse_error"
            result_count = 0
            missing_count = EXPECTED_PROBE_COUNT
            missing_probe_ids = sorted(expected_probe_ids)
            raw_file = ""
            fetch_status = "error"
            error = str(exception)

            print(f"  error={error}")

        inventory_rows.append(
            {
                "measurement_id": measurement_id,
                "target": target,
                "query_argument": query_argument,
                "description": description,
                "atlas_status": status,
                "fetch_status": fetch_status,
                "result_count": result_count,
                "expected_probe_count": EXPECTED_PROBE_COUNT,
                "missing_count": missing_count,
                "missing_probe_ids": ",".join(str(probe_id) for probe_id in missing_probe_ids),
                "raw_file": str(raw_file),
                "error": error,
                "fetched_at": datetime.now(UTC).isoformat(),
            }
        )

    INVENTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with INVENTORY_FILE.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "measurement_id",
                "target",
                "query_argument",
                "description",
                "atlas_status",
                "fetch_status",
                "result_count",
                "expected_probe_count",
                "missing_count",
                "missing_probe_ids",
                "raw_file",
                "error",
                "fetched_at",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(inventory_rows)

    print()
    print(f"Wrote {INVENTORY_FILE}")

    print()
    print("Missing probe frequency:")
    if not missing_probe_counter:
        print("No missing probes.")
    else:
        for probe_id, count in missing_probe_counter.most_common():
            print(f"probe_id={probe_id} missing_in={count} measurements")


if __name__ == "__main__":
    main()
