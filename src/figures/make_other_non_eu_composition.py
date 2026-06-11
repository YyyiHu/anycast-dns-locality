from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from common import (
    REGION_ORDER,
    load_nsid_summary,
    main_classifiable_summary,
    save_figure,
    save_table,
    setup_style,
)

COUNTRY_NAMES = {
    "AE": "United Arab Emirates",
    "AU": "Australia",
    "BH": "Bahrain",
    "BR": "Brazil",
    "CA": "Canada",
    "CL": "Chile",
    "CN": "China",
    "ID": "Indonesia",
    "IN": "India",
    "JP": "Japan",
    "MX": "Mexico",
    "RS": "Serbia",
    "SG": "Singapore",
    "US": "United States",
    "ZA": "South Africa",
}

CONTINENTS = {
    "AE": "Asia",
    "AU": "Oceania",
    "BH": "Asia",
    "BR": "South America",
    "CA": "North America",
    "CL": "South America",
    "CN": "Asia",
    "ID": "Asia",
    "IN": "Asia",
    "JP": "Asia",
    "MX": "North America",
    "RS": "Europe, non-EU",
    "SG": "Asia",
    "US": "North America",
    "ZA": "Africa",
}


def add_location_labels(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    result["country_name"] = (
        result["country_code"].map(COUNTRY_NAMES).fillna(result["country_code"])
    )

    result["continent"] = result["country_code"].map(CONTINENTS).fillna("Unknown")

    return result


def build_region_breakdown(main_df: pd.DataFrame) -> pd.DataFrame:
    total = int(main_df["count"].sum())

    region_df = (
        main_df.groupby("region_clean", as_index=False)["count"]
        .sum()
        .set_index("region_clean")
        .reindex(REGION_ORDER, fill_value=0)
        .reset_index()
        .rename(columns={"region_clean": "region"})
    )

    region_df["share_all_classifiable"] = (region_df["count"] / total * 100).round(1)

    return region_df


def build_other_non_eu_by_country(main_df: pd.DataFrame) -> pd.DataFrame:
    other_df = main_df[main_df["region_clean"] == "Other non-EU"].copy()
    other_df = add_location_labels(other_df)

    total_other = int(other_df["count"].sum())
    total_classifiable = int(main_df["count"].sum())

    country_df = (
        other_df.groupby(["country_code", "country_name"], as_index=False)["count"]
        .sum()
        .sort_values("count", ascending=False)
    )

    country_df["share_other_non_eu"] = (country_df["count"] / total_other * 100).round(1)

    country_df["share_all_classifiable"] = (country_df["count"] / total_classifiable * 100).round(1)

    return country_df


def build_other_non_eu_by_continent(main_df: pd.DataFrame) -> pd.DataFrame:
    other_df = main_df[main_df["region_clean"] == "Other non-EU"].copy()
    other_df = add_location_labels(other_df)

    total_other = int(other_df["count"].sum())
    total_classifiable = int(main_df["count"].sum())

    continent_df = (
        other_df.groupby("continent", as_index=False)["count"]
        .sum()
        .sort_values("count", ascending=False)
    )

    continent_df["share_other_non_eu"] = (continent_df["count"] / total_other * 100).round(1)

    continent_df["share_all_classifiable"] = (
        continent_df["count"] / total_classifiable * 100
    ).round(1)

    return continent_df


def build_other_non_eu_by_cctld_country(main_df: pd.DataFrame) -> pd.DataFrame:
    other_df = main_df[main_df["region_clean"] == "Other non-EU"].copy()

    cctld_country_df = other_df.pivot_table(
        index="cctld",
        columns="country_code",
        values="count",
        aggfunc="sum",
        fill_value=0,
    )

    cctld_country_df["other_non_eu_total"] = cctld_country_df.sum(axis=1)

    return cctld_country_df.sort_values("other_non_eu_total", ascending=False).reset_index()


def build_other_non_eu_by_target(main_df: pd.DataFrame) -> pd.DataFrame:
    target_df = main_df.pivot_table(
        index=["cctld", "nameserver"],
        columns="region_clean",
        values="count",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    for region in REGION_ORDER:
        if region not in target_df.columns:
            target_df[region] = 0

    target_df["total_classifiable"] = target_df[REGION_ORDER].sum(axis=1)
    target_df["non_eu_total"] = target_df[["UK", "CH", "Other non-EU"]].sum(axis=1)

    target_df["non_eu_share"] = (
        target_df["non_eu_total"] / target_df["total_classifiable"] * 100
    ).round(1)

    target_df["other_non_eu_share"] = (
        target_df["Other non-EU"] / target_df["total_classifiable"] * 100
    ).round(1)

    return target_df.sort_values(
        ["Other non-EU", "non_eu_total"],
        ascending=False,
    )


def plot_other_non_eu_country_composition(country_df: pd.DataFrame) -> None:
    top_n = 10
    plot_df = country_df.copy().sort_values("count", ascending=False)

    if len(plot_df) > top_n:
        top_df = plot_df.head(top_n).copy()
        rest_count = int(plot_df.iloc[top_n:]["count"].sum())

        if rest_count > 0:
            rest_df = pd.DataFrame(
                {
                    "country_code": ["OTHER"],
                    "country_name": ["Other countries"],
                    "count": [rest_count],
                }
            )
            plot_df = pd.concat([top_df, rest_df], ignore_index=True)
        else:
            plot_df = top_df

    total_other = int(plot_df["count"].sum())

    plot_df["share_other_non_eu"] = (plot_df["count"] / total_other * 100).round(1)

    plot_df["label"] = plot_df.apply(
        lambda row: f"{row['country_name']} ({int(row['count'])})",
        axis=1,
    )

    plot_df = plot_df.sort_values("share_other_non_eu", ascending=True)

    fig, ax = plt.subplots(figsize=(7.1, 4.1))

    bars = ax.barh(
        plot_df["label"],
        plot_df["share_other_non_eu"],
        color="#7D8790",
        height=0.68,
    )

    ax.set_xlabel("Share of Other non-EU observations (%)")
    ax.set_ylabel("")
    ax.set_title("Composition of Other non-EU replica classifications", pad=8)

    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.55)
    ax.set_axisbelow(True)

    max_value = float(plot_df["share_other_non_eu"].max())
    ax.set_xlim(0, max_value + 7)

    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + 0.7,
            bar.get_y() + bar.get_height() / 2,
            f"{width:.1f}%",
            va="center",
            fontsize=7,
        )

    save_figure("other_non_eu_country_composition", fig, save_png=True)


def print_summary(
    region_df: pd.DataFrame,
    country_df: pd.DataFrame,
    continent_df: pd.DataFrame,
    cctld_country_df: pd.DataFrame,
    target_df: pd.DataFrame,
) -> None:
    print("\nOverall region breakdown")
    print(region_df.to_string(index=False))

    print("\nOther non-EU by country")
    print(country_df.to_string(index=False))

    print("\nOther non-EU by continent")
    print(continent_df.to_string(index=False))

    print("\nOther non-EU by ccTLD and country")
    print(cctld_country_df.to_string(index=False))

    print("\nTop targets by Other non-EU count")
    print(
        target_df[
            [
                "cctld",
                "nameserver",
                "EU",
                "UK",
                "CH",
                "Other non-EU",
                "total_classifiable",
                "non_eu_share",
                "other_non_eu_share",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    values = {
        row["region"]: {
            "count": int(row["count"]),
            "share": float(row["share_all_classifiable"]),
        }
        for _, row in region_df.iterrows()
    }

    print("\nAbstract sentence")
    print(
        f"Overall, {values['EU']['share']:.1f}\\% of classifiable observations "
        "reached EU replicas. The remaining observations reached UK replicas "
        f"in {values['UK']['share']:.1f}\\% of cases, Swiss replicas in "
        f"{values['CH']['share']:.1f}\\% of cases, and other non-EU replicas "
        f"in {values['Other non-EU']['share']:.1f}\\% of cases."
    )


def main() -> None:
    setup_style()

    summary_df = load_nsid_summary()
    main_df = main_classifiable_summary(summary_df)

    total_classifiable = int(main_df["count"].sum())

    if total_classifiable == 0:
        raise ValueError("No high or medium confidence classified observations found.")

    region_df = build_region_breakdown(main_df)
    country_df = build_other_non_eu_by_country(main_df)
    continent_df = build_other_non_eu_by_continent(main_df)
    cctld_country_df = build_other_non_eu_by_cctld_country(main_df)
    target_df = build_other_non_eu_by_target(main_df)

    save_table(region_df, "non_eu_region_breakdown")
    save_table(country_df, "other_non_eu_by_country")
    save_table(continent_df, "other_non_eu_by_continent")
    save_table(cctld_country_df, "other_non_eu_by_cctld_country")
    save_table(target_df, "other_non_eu_by_target")

    plot_other_non_eu_country_composition(country_df)

    print_summary(region_df, country_df, continent_df, cctld_country_df, target_df)

    print("\nGenerated files")
    print("Figure:")
    print("  results/figures/other_non_eu_country_composition.pdf")
    print("  results/figures/other_non_eu_country_composition.png")
    print("Tables:")
    print("  results/tables/non_eu_region_breakdown.tsv")
    print("  results/tables/other_non_eu_by_country.tsv")
    print("  results/tables/other_non_eu_by_continent.tsv")
    print("  results/tables/other_non_eu_by_cctld_country.tsv")
    print("  results/tables/other_non_eu_by_target.tsv")


if __name__ == "__main__":
    main()
