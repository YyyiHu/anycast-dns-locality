# Home Away

Scripts and data for the thesis:

**Home or Away? Measuring Anycast Replica Locality in EU ccTLD Authoritative DNS**

This project measures whether DNS queries from EU RIPE Atlas probes to selected EU ccTLD authoritative nameserver IPv4 targets are answered by replicas inside or outside the EU.

## Structure

```text
data/input
  Fixed campaign inputs:
  active measurement targets, generated EU probe panel, and NSID mapping rules.

data/raw
  Raw collected data, including local screening logs and RIPE Atlas result JSON files.

data/processed/atlas_dns_results
  Parsed RIPE Atlas DNS results before locality classification.

data/processed/atlas_locality
  Final locality classification outputs.

data/processed/laces
  LACeS prefix and PoP context for active measurement targets.

data/processed/local_screens
  Local DNS feasibility screening summaries.

results/atlas
  Generated RIPE Atlas measurement payloads and creation metadata.
  JSON files in this folder are ignored by Git because they are run specific and can be regenerated.

results/figures
  Thesis figures generated from processed results.

src
  Python scripts for measurement planning, fetching, parsing, classification, and result generation.

tools
  Helper scripts for local checks.
```

## Pipeline

1. Run local feasibility screening with `tools/screen_cctlds.sh`.
   - Queries authoritative IPv4 targets.
   - Checks SOA responses with NSID.
   - Checks `hostname.bind` and `id.server`.
   - Writes raw logs to `data/raw/local_screens`.
   - Writes summaries to `data/processed/local_screens`.

2. Prepare active measurement targets and NSID mapping rules in `data/input`.

3. Fetch LACeS prefix and PoP context with `src/fetch_laces_pops_for_active_targets.py`.

4. Build the fixed EU probe panel and dry run Atlas DNS payload with `src/build_atlas_dns_dry_run.py`.

5. Create RIPE Atlas DNS measurements with `src/create_atlas_measurements.py`.

6. Fetch raw RIPE Atlas results with `src/fetch_atlas_results.py`.

7. Parse raw Atlas DNS results with `src/parse_atlas_dns_results.py`.

8. Classify SOA NSID values with `src/classify_nsid_locations.py`.
   - Output classes: `EU`, `UK`, `CH`, and `Other non-EU`.

9. Generate thesis figures from the processed result files.

## Main scripts

```text
tools/screen_cctlds.sh
  Screens candidate ccTLD authoritative IPv4 targets using SOA NSID and CHAOS TXT queries.

src/fetch_laces_pops_for_active_targets.py
  Fetches LACeS prefix and PoP context for active targets.

src/build_atlas_dns_dry_run.py
  Selects EU RIPE Atlas probes and builds the dry run measurement payload.

src/create_atlas_measurements.py
  Creates RIPE Atlas DNS measurements.

src/fetch_atlas_results.py
  Downloads Atlas result JSON files and writes the fetch inventory.

src/parse_atlas_dns_results.py
  Parses raw Atlas DNS results and extracts DNS observations and NSID values.

src/classify_nsid_locations.py
  Applies NSID mapping rules and produces locality classification outputs.
```

## Main outputs

```text
data/processed/local_screens/cctld_identity_summary.tsv

data/processed/laces/active_measurement_laces_pops.tsv

data/input/eu_probe_panel.tsv

data/processed/atlas_dns_results/atlas_fetch_inventory.tsv
data/processed/atlas_dns_results/atlas_dns_observations.tsv
data/processed/atlas_dns_results/atlas_dns_parse_summary.tsv
data/processed/atlas_dns_results/nsid_values_observed.tsv

data/processed/atlas_locality/dns_observations_classified.tsv
data/processed/atlas_locality/target_locality_summary.tsv
data/processed/atlas_locality/overall_classification_summary.tsv
data/processed/atlas_locality/nsid_classification_summary.tsv
data/processed/atlas_locality/nsid_unclassified_values.tsv
```

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

bash tools/screen_cctlds.sh
python src/fetch_laces_pops_for_active_targets.py
python src/build_atlas_dns_dry_run.py
python src/create_atlas_measurements.py
python src/fetch_atlas_results.py
python src/parse_atlas_dns_results.py
python src/classify_nsid_locations.py
```
