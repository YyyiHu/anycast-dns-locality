import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

PLAN_FILE = Path("results/atlas/measurement_plan.json")
OUTPUT_FILE = Path("results/atlas/created_measurements.json")
CREATE_URL = "https://atlas.ripe.net/api/v2/measurements/"
TIMEOUT_SECONDS = 30

EXPECTED_DEFINITION_COUNT = 20
EXPECTED_PROBE_COUNT = 81


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create RIPE Atlas DNS measurements from a prepared plan."
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually create measurements in RIPE Atlas.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting the created measurements output file.",
    )

    parser.add_argument(
        "--allow-start-time",
        action="store_true",
        help="Allow a start_time field in the measurement plan.",
    )

    return parser.parse_args()


def load_api_key() -> str:
    load_dotenv()

    api_key = os.getenv("ATLAS_API_KEY")

    if not api_key:
        raise RuntimeError("Missing ATLAS_API_KEY. Add it to .env.")

    return api_key


def load_plan() -> dict[str, Any]:
    if not PLAN_FILE.exists():
        raise FileNotFoundError(f"Measurement plan not found: {PLAN_FILE}")

    with PLAN_FILE.open() as file:
        return json.load(file)


def count_probe_ids(probe_value: str) -> int:
    return len([probe_id for probe_id in probe_value.split(",") if probe_id.strip()])


def build_payload(plan: dict[str, Any]) -> dict[str, Any]:
    payload = dict(plan)

    # RIPE Atlas rejects root-level is_public in measurement creation requests.
    # Public visibility is handled by Atlas defaults, so we omit it here.
    payload.pop("is_public", None)

    return payload


def validate_plan(plan: dict[str, Any], allow_start_time: bool) -> None:
    definitions = plan.get("definitions")
    probes = plan.get("probes")

    if not isinstance(definitions, list) or not definitions:
        raise ValueError("Plan must contain a non-empty definitions list.")

    if not isinstance(probes, list) or not probes:
        raise ValueError("Plan must contain a non-empty probes list.")

    if plan.get("is_oneoff") is not True:
        raise ValueError("Plan must set is_oneoff to true.")

    if "start_time" in plan and not allow_start_time:
        raise ValueError("Plan contains start_time. Remove it, or rerun with --allow-start-time.")

    if len(definitions) != EXPECTED_DEFINITION_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_DEFINITION_COUNT} definitions, found {len(definitions)}."
        )

    if len(probes) != 1:
        raise ValueError(f"Expected 1 probe selection, found {len(probes)}.")

    probe_selection = probes[0]

    if probe_selection.get("type") != "probes":
        raise ValueError("Probe selection must use type=probes.")

    requested = probe_selection.get("requested")
    value = probe_selection.get("value")

    if requested != EXPECTED_PROBE_COUNT:
        raise ValueError(f"Expected requested={EXPECTED_PROBE_COUNT}, found requested={requested}.")

    if not isinstance(value, str) or not value:
        raise ValueError("Probe selection must contain comma-separated probe IDs.")

    actual_probe_count = count_probe_ids(value)

    if actual_probe_count != EXPECTED_PROBE_COUNT:
        raise ValueError(f"Expected {EXPECTED_PROBE_COUNT} probe IDs, found {actual_probe_count}.")

    seen_targets = set()

    for index, definition in enumerate(definitions, start=1):
        prefix = f"Definition {index}"

        expected_values = {
            "type": "dns",
            "af": 4,
            "query_type": "SOA",
            "query_class": "IN",
            "set_nsid_bit": True,
            "set_rd_bit": False,
            "use_probe_resolver": False,
            "resolve_on_probe": False,
            "include_abuf": True,
        }

        for field, expected_value in expected_values.items():
            actual_value = definition.get(field)

            if actual_value != expected_value:
                raise ValueError(
                    f"{prefix}: expected {field}={expected_value}, got {actual_value}."
                )

        target = definition.get("target")
        query_argument = definition.get("query_argument")
        description = definition.get("description")

        if not target:
            raise ValueError(f"{prefix}: missing target.")

        if target in seen_targets:
            raise ValueError(f"{prefix}: duplicate target {target}.")

        seen_targets.add(target)

        if not query_argument or not str(query_argument).endswith("."):
            raise ValueError(f"{prefix}: query_argument should be a DNS zone with final dot.")

        if not description:
            raise ValueError(f"{prefix}: missing description.")


def print_summary(plan: dict[str, Any]) -> None:
    definitions = plan["definitions"]
    probes = plan["probes"][0]

    print("Atlas measurement creation summary")
    print(f"Definitions: {len(definitions)}")
    print(f"Probe selection type: {probes['type']}")
    print(f"Requested probes: {probes['requested']}")
    print(f"Actual probe IDs: {count_probe_ids(probes['value'])}")
    print(f"One off: {plan['is_oneoff']}")
    print("Public: omitted from creation payload")
    print()

    for index, definition in enumerate(definitions, start=1):
        print(
            f"{index:02d}. "
            f"{definition['query_argument']} "
            f"{definition['query_type']} "
            f"target={definition['target']} "
            f"description={definition['description']}"
        )


def create_measurements(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    response = requests.post(
        CREATE_URL,
        headers={
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )

    try:
        response_body = response.json()
    except ValueError:
        response_body = {"raw_response": response.text}

    if response.status_code not in {200, 201, 202}:
        raise RuntimeError(
            f"RIPE Atlas creation failed with HTTP {response.status_code}:\n"
            f"{json.dumps(response_body, indent=2, sort_keys=True)}"
        )

    if not isinstance(response_body, dict):
        raise RuntimeError(f"Unexpected Atlas response:\n{response_body}")

    measurement_ids = response_body.get("measurements")

    if not isinstance(measurement_ids, list) or len(measurement_ids) != len(payload["definitions"]):
        raise RuntimeError(
            "Atlas response did not contain the expected measurement IDs:\n"
            f"{json.dumps(response_body, indent=2, sort_keys=True)}"
        )

    created_measurements = []

    for definition, measurement_id in zip(payload["definitions"], measurement_ids, strict=True):
        created_measurements.append(
            {
                "measurement_id": measurement_id,
                "description": definition["description"],
                "target": definition["target"],
                "query_argument": definition["query_argument"],
                "query_type": definition["query_type"],
                "tags": definition.get("tags", []),
            }
        )

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "http_status": response.status_code,
        "definition_count": len(payload["definitions"]),
        "requested_probes": payload["probes"][0]["requested"],
        "actual_probe_ids": count_probe_ids(payload["probes"][0]["value"]),
        "created_measurements": created_measurements,
        "atlas_response": response_body,
    }


def main() -> None:
    args = parse_args()

    plan = load_plan()
    validate_plan(plan, allow_start_time=args.allow_start_time)

    payload = build_payload(plan)
    print_summary(payload)

    if not args.execute:
        print()
        print("Validation only. No measurements were created.")
        print("Run with --execute to create the measurements.")
        return

    if OUTPUT_FILE.exists() and not args.force:
        raise RuntimeError(
            f"{OUTPUT_FILE} already exists. "
            "This prevents accidentally creating duplicate measurements. "
            "Use --force only if you intentionally want to overwrite the local record."
        )

    api_key = load_api_key()
    result = create_measurements(payload, api_key)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, indent=2, sort_keys=True))

    print()
    print("Created measurements successfully.")
    print(f"Wrote {OUTPUT_FILE}")

    print()
    print("Measurement IDs:")
    for measurement in result["created_measurements"]:
        print(f"{measurement['measurement_id']} {measurement['description']}")


if __name__ == "__main__":
    main()
