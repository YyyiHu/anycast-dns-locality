#!/usr/bin/env python3

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

OBSERVATIONS_FILE = Path("data/processed/atlas_dns_results/atlas_dns_observations.tsv")
TARGETS_FILE = Path("data/input/active_measurement_targets.tsv")
RULES_FILE = Path("data/input/nsid_mapping_rules.tsv")

OUTPUT_DIR = Path("data/processed/atlas_locality")

CLASSIFIED_FILE = OUTPUT_DIR / "dns_observations_classified.tsv"
NSID_CLASSIFICATION_SUMMARY_FILE = OUTPUT_DIR / "nsid_classification_summary.tsv"
NSID_UNCLASSIFIED_FILE = OUTPUT_DIR / "nsid_unclassified_values.tsv"
TARGET_LOCALITY_SUMMARY_FILE = OUTPUT_DIR / "target_locality_summary.tsv"
OVERALL_SUMMARY_FILE = OUTPUT_DIR / "overall_classification_summary.tsv"

MAIN_CONFIDENCES = {"high", "medium"}


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    with path.open(newline="") as file:
        return list(csv.DictReader(file, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def load_target_metadata() -> dict[str, dict[str, str]]:
    targets = read_tsv(TARGETS_FILE)
    metadata_by_ip = {}

    for target in targets:
        ipv4 = target.get("ipv4", "")
        if not ipv4:
            continue

        metadata_by_ip[ipv4] = {
            "cctld": target.get("ccTLD", target.get("cctld", "")),
            "zone": target.get("zone", ""),
            "nameserver": target.get("nameserver", ""),
            "analysis_role": target.get("analysis_role", ""),
        }

    return metadata_by_ip


def load_rules() -> list[dict[str, str]]:
    rules = read_tsv(RULES_FILE)

    for rule in rules:
        if not rule.get("priority"):
            raise ValueError(f"Rule is missing priority: {rule}")

        if rule.get("match_type") not in {"exact", "contains", "regex"}:
            raise ValueError(f"Unsupported match_type in rule: {rule}")

        if not rule.get("pattern"):
            raise ValueError(f"Rule is missing pattern: {rule}")

        if rule.get("confidence") not in {"high", "medium", "low"}:
            raise ValueError(f"Unsupported confidence in rule: {rule}")

        if rule.get("region_class") not in {"EU", "UK", "CH", "Other non EU"}:
            raise ValueError(f"Unsupported region_class in rule: {rule}")

    return sorted(rules, key=lambda rule: int(rule["priority"]))


def rule_matches(rule: dict[str, str], nsid_raw: str) -> bool:
    match_type = rule["match_type"]
    pattern = rule["pattern"]

    if match_type == "exact":
        return nsid_raw == pattern

    if match_type == "contains":
        return pattern.lower() in nsid_raw.lower()

    if match_type == "regex":
        return re.search(pattern, nsid_raw, flags=re.IGNORECASE) is not None

    raise ValueError(f"Unsupported match_type: {match_type}")


def classify_nsid(nsid_raw: str, rules: list[dict[str, str]]) -> dict[str, str]:
    for rule in rules:
        if not rule_matches(rule, nsid_raw):
            continue

        confidence = rule["confidence"]
        is_main_classifiable = confidence in MAIN_CONFIDENCES

        return {
            "classification_status": "classified" if is_main_classifiable else "low_confidence",
            "is_classified": str(is_main_classifiable),
            "city": rule.get("city", ""),
            "country_code": rule["country_code"],
            "region_class": rule["region_class"],
            "classification_confidence": confidence,
            "classification_method": rule["match_type"],
            "matched_rule_priority": rule["priority"],
            "matched_rule_pattern": rule["pattern"],
            "classification_note": rule.get("note", ""),
        }

    return {
        "classification_status": "unknown",
        "is_classified": "False",
        "city": "",
        "country_code": "",
        "region_class": "Unknown",
        "classification_confidence": "unknown",
        "classification_method": "",
        "matched_rule_priority": "",
        "matched_rule_pattern": "",
        "classification_note": "No defensible NSID mapping rule matched",
    }


def add_target_metadata(
    row: dict[str, str],
    metadata_by_ip: dict[str, dict[str, str]],
) -> dict[str, str]:
    target_ip = row.get("target", "")
    metadata = metadata_by_ip.get(target_ip, {})

    return {
        **row,
        "cctld": metadata.get("cctld", ""),
        "zone": metadata.get("zone", ""),
        "nameserver": metadata.get("nameserver", ""),
        "analysis_role": metadata.get("analysis_role", ""),
    }


def classify_rows(
    observations: list[dict[str, str]],
    rules: list[dict[str, str]],
    metadata_by_ip: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    classified_rows = []

    for original_row in observations:
        row = add_target_metadata(original_row, metadata_by_ip)

        is_valid = row.get("is_valid_dns_observation") == "True"
        nsid_raw = row.get("nsid_raw", "")

        if not is_valid:
            classification = {
                "classification_status": "invalid_dns_observation",
                "is_classified": "False",
                "city": "",
                "country_code": "",
                "region_class": "",
                "classification_confidence": "",
                "classification_method": "",
                "matched_rule_priority": "",
                "matched_rule_pattern": "",
                "classification_note": "Invalid DNS observation, excluded before NSID locality classification",
            }
        elif not nsid_raw:
            classification = {
                "classification_status": "missing_nsid",
                "is_classified": "False",
                "city": "",
                "country_code": "",
                "region_class": "Unknown",
                "classification_confidence": "unknown",
                "classification_method": "",
                "matched_rule_priority": "",
                "matched_rule_pattern": "",
                "classification_note": "Valid DNS response but no NSID value was extracted",
            }
        else:
            classification = classify_nsid(nsid_raw, rules)

        classified_rows.append({**row, **classification})

    return classified_rows


def write_nsid_classification_summary(rows: list[dict[str, object]]) -> None:
    grouped: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)

    for row in rows:
        if row.get("is_valid_dns_observation") != "True":
            continue

        key = (
            str(row["measurement_id"]),
            str(row["target"]),
            str(row["query_argument"]),
            str(row["nsid_raw"]),
        )

        grouped[key].append(row)

    output_rows = []

    for key, group_rows in sorted(grouped.items()):
        measurement_id, target, query_argument, nsid_raw = key
        first = group_rows[0]

        output_rows.append(
            {
                "measurement_id": measurement_id,
                "cctld": first["cctld"],
                "nameserver": first["nameserver"],
                "target": target,
                "query_argument": query_argument,
                "nsid_raw": nsid_raw,
                "count": len(group_rows),
                "classification_status": first["classification_status"],
                "city": first["city"],
                "country_code": first["country_code"],
                "region_class": first["region_class"],
                "classification_confidence": first["classification_confidence"],
                "classification_method": first["classification_method"],
                "matched_rule_priority": first["matched_rule_priority"],
                "matched_rule_pattern": first["matched_rule_pattern"],
                "classification_note": first["classification_note"],
            }
        )

    fieldnames = [
        "measurement_id",
        "cctld",
        "nameserver",
        "target",
        "query_argument",
        "nsid_raw",
        "count",
        "classification_status",
        "city",
        "country_code",
        "region_class",
        "classification_confidence",
        "classification_method",
        "matched_rule_priority",
        "matched_rule_pattern",
        "classification_note",
    ]

    write_tsv(NSID_CLASSIFICATION_SUMMARY_FILE, output_rows, fieldnames)


def write_unclassified_values(rows: list[dict[str, object]]) -> None:
    grouped: dict[tuple[str, str, str, str, str, str], int] = defaultdict(int)

    for row in rows:
        if row.get("is_valid_dns_observation") != "True":
            continue

        status = str(row["classification_status"])

        if status not in {"unknown", "low_confidence"}:
            continue

        key = (
            str(row["measurement_id"]),
            str(row["cctld"]),
            str(row["nameserver"]),
            str(row["target"]),
            str(row["nsid_raw"]),
            status,
        )

        grouped[key] += 1

    output_rows = []

    for key, count in sorted(grouped.items()):
        measurement_id, cctld, nameserver, target, nsid_raw, status = key

        output_rows.append(
            {
                "measurement_id": measurement_id,
                "cctld": cctld,
                "nameserver": nameserver,
                "target": target,
                "nsid_raw": nsid_raw,
                "count": count,
                "classification_status": status,
                "interpretation": "Excluded from main locality denominator",
            }
        )

    fieldnames = [
        "measurement_id",
        "cctld",
        "nameserver",
        "target",
        "nsid_raw",
        "count",
        "classification_status",
        "interpretation",
    ]

    write_tsv(NSID_UNCLASSIFIED_FILE, output_rows, fieldnames)


def write_target_locality_summary(rows: list[dict[str, object]]) -> None:
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)

    for row in rows:
        if row.get("is_valid_dns_observation") != "True":
            continue

        key = (
            str(row["measurement_id"]),
            str(row["target"]),
            str(row["query_argument"]),
        )

        grouped[key].append(row)

    output_rows = []

    for key, group_rows in sorted(grouped.items()):
        measurement_id, target, query_argument = key
        first = group_rows[0]

        confidence_counter = Counter(str(row["classification_confidence"]) for row in group_rows)
        status_counter = Counter(str(row["classification_status"]) for row in group_rows)

        main_rows = [
            row for row in group_rows if row["classification_confidence"] in MAIN_CONFIDENCES
        ]

        region_counter = Counter(str(row["region_class"]) for row in main_rows)

        valid_observations = len(group_rows)
        main_classifiable = len(main_rows)

        eu = region_counter["EU"]
        uk = region_counter["UK"]
        ch = region_counter["CH"]
        other_non_eu = region_counter["Other non EU"]
        non_eu = uk + ch + other_non_eu

        main_classifiable_share = (
            main_classifiable / valid_observations if valid_observations else 0
        )
        eu_fraction = eu / main_classifiable if main_classifiable else 0
        non_eu_fraction = non_eu / main_classifiable if main_classifiable else 0

        output_rows.append(
            {
                "measurement_id": measurement_id,
                "cctld": first["cctld"],
                "zone": first["zone"],
                "nameserver": first["nameserver"],
                "target": target,
                "query_argument": query_argument,
                "analysis_role": first["analysis_role"],
                "valid_observations": valid_observations,
                "main_classifiable": main_classifiable,
                "main_classifiable_share": f"{main_classifiable_share:.4f}",
                "high_confidence": confidence_counter["high"],
                "medium_confidence": confidence_counter["medium"],
                "low_confidence": confidence_counter["low"],
                "unknown": confidence_counter["unknown"],
                "eu": eu,
                "uk": uk,
                "ch": ch,
                "other_non_eu": other_non_eu,
                "non_eu": non_eu,
                "eu_fraction": f"{eu_fraction:.4f}",
                "non_eu_fraction": f"{non_eu_fraction:.4f}",
                "status_counts": "; ".join(
                    f"{status}={count}" for status, count in status_counter.most_common()
                ),
            }
        )

    fieldnames = [
        "measurement_id",
        "cctld",
        "zone",
        "nameserver",
        "target",
        "query_argument",
        "analysis_role",
        "valid_observations",
        "main_classifiable",
        "main_classifiable_share",
        "high_confidence",
        "medium_confidence",
        "low_confidence",
        "unknown",
        "eu",
        "uk",
        "ch",
        "other_non_eu",
        "non_eu",
        "eu_fraction",
        "non_eu_fraction",
        "status_counts",
    ]

    write_tsv(TARGET_LOCALITY_SUMMARY_FILE, output_rows, fieldnames)


def write_overall_summary(rows: list[dict[str, object]]) -> None:
    valid_rows = [row for row in rows if row.get("is_valid_dns_observation") == "True"]

    confidence_counter = Counter(str(row["classification_confidence"]) for row in valid_rows)

    main_rows = [row for row in valid_rows if row["classification_confidence"] in MAIN_CONFIDENCES]

    region_counter = Counter(str(row["region_class"]) for row in main_rows)

    valid_observations = len(valid_rows)
    main_classifiable = len(main_rows)

    eu = region_counter["EU"]
    uk = region_counter["UK"]
    ch = region_counter["CH"]
    other_non_eu = region_counter["Other non EU"]
    non_eu = uk + ch + other_non_eu

    output_rows = [
        {
            "valid_observations": valid_observations,
            "high_confidence": confidence_counter["high"],
            "medium_confidence": confidence_counter["medium"],
            "low_confidence": confidence_counter["low"],
            "unknown": confidence_counter["unknown"],
            "main_classifiable": main_classifiable,
            "main_classifiable_share": (
                f"{main_classifiable / valid_observations:.4f}" if valid_observations else "0.0000"
            ),
            "eu": eu,
            "uk": uk,
            "ch": ch,
            "other_non_eu": other_non_eu,
            "non_eu": non_eu,
            "eu_fraction": (f"{eu / main_classifiable:.4f}" if main_classifiable else "0.0000"),
            "non_eu_fraction": (
                f"{non_eu / main_classifiable:.4f}" if main_classifiable else "0.0000"
            ),
        }
    ]

    fieldnames = [
        "valid_observations",
        "high_confidence",
        "medium_confidence",
        "low_confidence",
        "unknown",
        "main_classifiable",
        "main_classifiable_share",
        "eu",
        "uk",
        "ch",
        "other_non_eu",
        "non_eu",
        "eu_fraction",
        "non_eu_fraction",
    ]

    write_tsv(OVERALL_SUMMARY_FILE, output_rows, fieldnames)


def main() -> None:
    rules = load_rules()
    observations = read_tsv(OBSERVATIONS_FILE)
    metadata_by_ip = load_target_metadata()

    if not observations:
        raise ValueError(f"No observations found in {OBSERVATIONS_FILE}")

    classified_rows = classify_rows(observations, rules, metadata_by_ip)

    fieldnames = list(observations[0].keys()) + [
        "cctld",
        "zone",
        "nameserver",
        "analysis_role",
        "classification_status",
        "is_classified",
        "city",
        "country_code",
        "region_class",
        "classification_confidence",
        "classification_method",
        "matched_rule_priority",
        "matched_rule_pattern",
        "classification_note",
    ]

    write_tsv(CLASSIFIED_FILE, classified_rows, fieldnames)
    write_nsid_classification_summary(classified_rows)
    write_unclassified_values(classified_rows)
    write_target_locality_summary(classified_rows)
    write_overall_summary(classified_rows)

    valid_rows = [row for row in classified_rows if row.get("is_valid_dns_observation") == "True"]

    confidence_counter = Counter(str(row["classification_confidence"]) for row in valid_rows)
    main_classifiable = confidence_counter["high"] + confidence_counter["medium"]
    main_share = main_classifiable / len(valid_rows) if valid_rows else 0

    print(f"Read observations from {OBSERVATIONS_FILE}")
    print(f"Read mapping rules from {RULES_FILE}")
    print(f"Wrote outputs to {OUTPUT_DIR}")
    print()
    print(f"Valid DNS observations: {len(valid_rows)}")
    print(f"High confidence: {confidence_counter['high']}")
    print(f"Medium confidence: {confidence_counter['medium']}")
    print(f"Low confidence: {confidence_counter['low']}")
    print(f"Unknown: {confidence_counter['unknown']}")
    print(f"Main classifiable observations: {main_classifiable}")
    print(f"Main classifiable share: {main_share:.4f}")
    print()
    print(f"Wrote {CLASSIFIED_FILE}")
    print(f"Wrote {NSID_CLASSIFICATION_SUMMARY_FILE}")
    print(f"Wrote {NSID_UNCLASSIFIED_FILE}")
    print(f"Wrote {TARGET_LOCALITY_SUMMARY_FILE}")
    print(f"Wrote {OVERALL_SUMMARY_FILE}")


if __name__ == "__main__":
    main()
