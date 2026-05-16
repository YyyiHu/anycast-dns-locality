#!/usr/bin/env bash
set -u

zones=(
  be nl de fr cz
  fi se dk pl it es at ie pt gr
  ro hu sk si
  ee lv lt
  eu
)

raw_dir="data/raw/local_screens"
processed_dir="data/processed/local_screens"
summary_file="$processed_dir/cctld_identity_summary.tsv"

dig_timeout=3
dig_tries=1

mkdir -p "$raw_dir" "$processed_dir"

printf "zone\tns_name\tipv4\tsoa_status\tsoa_aa\tnsid\thostname_bind\tid_server\tsoa_query_ms\n" > "$summary_file"

extract_status() {
  printf "%s\n" "$1" | sed -n 's/.*status: \([^,]*\),.*/\1/p' | head -n 1
}

extract_flags() {
  printf "%s\n" "$1" | sed -n 's/.*flags: \([^;]*\);.*/\1/p' | head -n 1
}

extract_nsid() {
  local value

  value=$(printf "%s\n" "$1" | sed -n 's/.*NSID: .*("\([^"]*\)").*/\1/p' | head -n 1)

  if [ -z "$value" ]; then
    value=$(printf "%s\n" "$1" | sed -n 's/.*NSID: \(.*\)/\1/p' | head -n 1)
  fi

  printf "%s" "$value"
}

extract_txt() {
  printf "%s\n" "$1" | sed -n 's/.*TXT[[:space:]]*"\(.*\)".*/\1/p' | head -n 1
}

extract_query_time() {
  printf "%s\n" "$1" | sed -n 's/.*Query time: \([0-9]*\).*/\1/p' | head -n 1
}

has_authoritative_answer_flag() {
  local flags="$1"

  if [[ " $flags " == *" aa "* ]]; then
    printf "yes"
  else
    printf "no"
  fi
}

for zone in "${zones[@]}"; do
  raw_file="$raw_dir/${zone}_identity_screen.txt"

  {
    echo "Screening .$zone authoritative IPv4 targets"
    echo "Started at $(date)"

    ns_names=$(dig +short NS "$zone." | sort -u)

    if [ -z "$ns_names" ]; then
      echo
      echo "==== .$zone no-nameservers-found ===="
      echo
      echo "Finished at $(date)"
      continue
    fi

    for ns in $ns_names; do
      ips=$(dig +short A "$ns" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | sort -u)

      if [ -z "$ips" ]; then
        echo
        echo "==== .$zone $ns no-ipv4-found ===="
        continue
      fi

      for ip in $ips; do
        echo
        echo "==== .$zone $ns $ip ===="

        echo "[SOA with NSID]"
        soa_output=$(
          dig @"$ip" "$zone." SOA \
            +norecurse \
            +nsid \
            +"time=$dig_timeout" \
            +"tries=$dig_tries" \
            +noall \
            +comments \
            +answer \
            +stats
        )
        printf "%s\n" "$soa_output"

        echo "[hostname.bind]"
        hostname_output=$(
          dig @"$ip" hostname.bind TXT CH \
            +norecurse \
            +"time=$dig_timeout" \
            +"tries=$dig_tries" \
            +noall \
            +comments \
            +answer \
            +stats
        )
        printf "%s\n" "$hostname_output"

        echo "[id.server]"
        id_output=$(
          dig @"$ip" id.server TXT CH \
            +norecurse \
            +"time=$dig_timeout" \
            +"tries=$dig_tries" \
            +noall \
            +comments \
            +answer \
            +stats
        )
        printf "%s\n" "$id_output"

        soa_status=$(extract_status "$soa_output")
        soa_flags=$(extract_flags "$soa_output")
        nsid=$(extract_nsid "$soa_output")
        hostname_bind=$(extract_txt "$hostname_output")
        id_server=$(extract_txt "$id_output")
        soa_query_ms=$(extract_query_time "$soa_output")
        soa_aa=$(has_authoritative_answer_flag "$soa_flags")

        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
          "$zone" \
          "$ns" \
          "$ip" \
          "$soa_status" \
          "$soa_aa" \
          "$nsid" \
          "$hostname_bind" \
          "$id_server" \
          "$soa_query_ms" \
          >> "$summary_file"
      done
    done

    echo
    echo "Finished at $(date)"
  } | tee "$raw_file"
done

echo
echo "Summary written to $summary_file"