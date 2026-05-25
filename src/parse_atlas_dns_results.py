#!/usr/bin/env python3

import base64
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import dns.message
import dns.rcode

CREATED_FILE = Path("results/atlas/created_measurements.json")
RAW_RESULTS_DIR = Path("data/raw/atlas/results")

OBSERVATIONS_FILE = Path("data/processed/atlas_dns_observations.tsv")
NSID_VALUES_FILE = Path("data/processed/nsid_values_observed.tsv")
SUMMARY_FILE = Path("data/processed/atlas_dns_parse_summary.tsv")

NSID_OPTION_CODE = 3


def load_measurement_metadata() -> dict[int, dict[str, Any]]:
    if not CREATED_FILE.exists():
        raise FileNotFoundError(f"Created measurements file not found: {CREATED_FILE}")

    data = json.loads(CREATED_FILE.read_text())
    measurements = data.get("created_measurements")

    if not isinstance(measurements, list) or not measurements:
        raise ValueError("created_measurements.json does not contain created_measurements.")

    return {int(measurement["measurement_id"]): measurement for measurement in measurements}


def decode_base64_wire(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.b64decode(encoded + padding)


def extract_nsid_from_abuf(abuf: str) -> tuple[str, str, str]:
    try:
        wire = decode_base64_wire(abuf)
        message = dns.message.from_wire(wire)

        rcode_text = dns.rcode.to_text(message.rcode())

        for option in message.options:
            if int(option.otype) != NSID_OPTION_CODE:
                continue

            nsid_bytes = getattr(option, "nsid", None)

            if nsid_bytes is None:
                nsid_bytes = getattr(option, "data", None)

            if nsid_bytes is None:
                generic_option = option.to_generic()
                nsid_bytes = getattr(generic_option, "data", b"")

            if not nsid_bytes:
                return rcode_text, "", ""

            nsid_text = nsid_bytes.decode("utf-8", errors="replace")
            nsid_hex = nsid_bytes.hex()

            return rcode_text, nsid_text, nsid_hex

        return rcode_text, "", ""

    except Exception as exception:
        return "decode_error", "", f"{type(exception).__name__}: {exception}"


def get_answer_type(result_data: dict[str, Any]) -> str:
    answers = result_data.get("answers")

    if not isinstance(answers, list) or not answers:
        return ""

    answer_types = sorted(
        str(answer.get("TYPE", "")) for answer in answers if isinstance(answer, dict)
    )

    return ",".join(answer_type for answer_type in answer_types if answer_type)


def get_invalid_reason(
    atlas_result: dict[str, Any],
    result_data: dict[str, Any] | None,
    rcode: str,
    nsid_raw: str,
    answer_type: str,
) -> str:
    if "error" in atlas_result:
        return f"atlas_error:{atlas_result['error']}"

    if result_data is None:
        return "missing_result"

    if rcode == "missing_abuf":
        return "missing_abuf"

    if rcode == "decode_error":
        return "abuf_decode_error"

    if rcode != "NOERROR":
        return f"rcode_{rcode}"

    if "SOA" not in answer_type.split(","):
        return "missing_soa_answer"

    if not nsid_raw:
        return "missing_nsid"

    return ""


def parse_result_file(
    path: Path,
    measurement_metadata: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_results = json.loads(path.read_text())

    if not isinstance(raw_results, list):
        raise ValueError(f"Expected list in raw result file: {path}")

    rows = []

    for atlas_result in raw_results:
        measurement_id = int(atlas_result["msm_id"])
        metadata = measurement_metadata.get(measurement_id)

        if metadata is None:
            raise ValueError(f"No metadata found for measurement {measurement_id}")

        result_data = atlas_result.get("result")

        if not isinstance(result_data, dict):
            result_data = None

        abuf = ""
        rtt_ms = ""
        answer_type = ""
        answer_count = ""
        additional_count = ""
        response_size = ""
        rcode = ""
        nsid_raw = ""
        nsid_hex = ""

        if result_data is not None:
            abuf = str(result_data.get("abuf", ""))
            rtt_ms = result_data.get("rt", "")
            answer_type = get_answer_type(result_data)
            answer_count = result_data.get("ANCOUNT", "")
            additional_count = result_data.get("ARCOUNT", "")
            response_size = result_data.get("size", "")

            if abuf:
                rcode, nsid_raw, nsid_hex = extract_nsid_from_abuf(abuf)
            else:
                rcode = "missing_abuf"

        invalid_reason = get_invalid_reason(
            atlas_result=atlas_result,
            result_data=result_data,
            rcode=rcode,
            nsid_raw=nsid_raw,
            answer_type=answer_type,
        )

        rows.append(
            {
                "measurement_id": measurement_id,
                "probe_id": atlas_result.get("prb_id", ""),
                "target": metadata["target"],
                "dst_addr": atlas_result.get("dst_addr", ""),
                "query_argument": metadata["query_argument"],
                "query_type": metadata["query_type"],
                "description": metadata["description"],
                "atlas_type": atlas_result.get("type", ""),
                "protocol": atlas_result.get("proto", ""),
                "from_addr": atlas_result.get("from", ""),
                "src_addr": atlas_result.get("src_addr", ""),
                "timestamp": atlas_result.get("timestamp", ""),
                "stored_timestamp": atlas_result.get("stored_timestamp", ""),
                "rtt_ms": rtt_ms,
                "rcode": rcode,
                "answer_type": answer_type,
                "answer_count": answer_count,
                "additional_count": additional_count,
                "response_size": response_size,
                "nsid_raw": nsid_raw,
                "nsid_hex": nsid_hex,
                "has_abuf": bool(abuf),
                "is_valid_dns_observation": invalid_reason == "",
                "invalid_reason": invalid_reason,
            }
        )

    return rows


def write_observations(rows: list[dict[str, Any]]) -> None:
    OBSERVATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "measurement_id",
        "probe_id",
        "target",
        "dst_addr",
        "query_argument",
        "query_type",
        "description",
        "atlas_type",
        "protocol",
        "from_addr",
        "src_addr",
        "timestamp",
        "stored_timestamp",
        "rtt_ms",
        "rcode",
        "answer_type",
        "answer_count",
        "additional_count",
        "response_size",
        "nsid_raw",
        "nsid_hex",
        "has_abuf",
        "is_valid_dns_observation",
        "invalid_reason",
    ]

    with OBSERVATIONS_FILE.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_nsid_values(rows: list[dict[str, Any]]) -> None:
    counts: dict[tuple[int, str, str, str], Counter[str]] = defaultdict(Counter)

    for row in rows:
        nsid_raw = str(row["nsid_raw"])

        if not nsid_raw:
            continue

        key = (
            int(row["measurement_id"]),
            str(row["target"]),
            str(row["query_argument"]),
            nsid_raw,
        )

        validity = "valid" if row["is_valid_dns_observation"] else "invalid"
        counts[key][validity] += 1

    NSID_VALUES_FILE.parent.mkdir(parents=True, exist_ok=True)

    with NSID_VALUES_FILE.open("w", newline="") as file:
        fieldnames = [
            "measurement_id",
            "target",
            "query_argument",
            "nsid_raw",
            "valid_count",
            "invalid_count",
            "total_count",
        ]

        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()

        for key, counter in sorted(counts.items()):
            measurement_id, target, query_argument, nsid_raw = key
            valid_count = counter["valid"]
            invalid_count = counter["invalid"]

            writer.writerow(
                {
                    "measurement_id": measurement_id,
                    "target": target,
                    "query_argument": query_argument,
                    "nsid_raw": nsid_raw,
                    "valid_count": valid_count,
                    "invalid_count": invalid_count,
                    "total_count": valid_count + invalid_count,
                }
            )


def write_summary(rows: list[dict[str, Any]]) -> None:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        grouped[int(row["measurement_id"])].append(row)

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with SUMMARY_FILE.open("w", newline="") as file:
        fieldnames = [
            "measurement_id",
            "target",
            "query_argument",
            "total_rows",
            "valid_rows",
            "invalid_rows",
            "unique_valid_nsids",
            "invalid_reasons",
        ]

        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()

        for measurement_id, group_rows in sorted(grouped.items()):
            valid_rows = [row for row in group_rows if row["is_valid_dns_observation"]]

            invalid_rows = [row for row in group_rows if not row["is_valid_dns_observation"]]

            unique_valid_nsids = sorted(
                {str(row["nsid_raw"]) for row in valid_rows if row["nsid_raw"]}
            )

            invalid_reason_counter = Counter(
                str(row["invalid_reason"]) for row in invalid_rows if row["invalid_reason"]
            )

            writer.writerow(
                {
                    "measurement_id": measurement_id,
                    "target": group_rows[0]["target"],
                    "query_argument": group_rows[0]["query_argument"],
                    "total_rows": len(group_rows),
                    "valid_rows": len(valid_rows),
                    "invalid_rows": len(invalid_rows),
                    "unique_valid_nsids": len(unique_valid_nsids),
                    "invalid_reasons": "; ".join(
                        f"{reason}={count}"
                        for reason, count in invalid_reason_counter.most_common()
                    ),
                }
            )


def main() -> None:
    measurement_metadata = load_measurement_metadata()
    raw_files = sorted(RAW_RESULTS_DIR.glob("*.json"))

    if not raw_files:
        raise FileNotFoundError(f"No raw result files found in {RAW_RESULTS_DIR}")

    rows = []

    for path in raw_files:
        rows.extend(parse_result_file(path, measurement_metadata))

    write_observations(rows)
    write_nsid_values(rows)
    write_summary(rows)

    valid_count = sum(1 for row in rows if row["is_valid_dns_observation"])
    invalid_count = len(rows) - valid_count

    print(f"Parsed result files: {len(raw_files)}")
    print(f"Parsed rows: {len(rows)}")
    print(f"Valid DNS observations: {valid_count}")
    print(f"Invalid observations: {invalid_count}")
    print(f"Wrote {OBSERVATIONS_FILE}")
    print(f"Wrote {NSID_VALUES_FILE}")
    print(f"Wrote {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
