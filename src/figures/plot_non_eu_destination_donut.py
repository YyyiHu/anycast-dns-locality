from __future__ import annotations

import math

import matplotlib.patches as mpatches
import matplotlib.patheffects as path_effects
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
    "CH": "Switzerland",
    "CL": "Chile",
    "CN": "China",
    "ID": "Indonesia",
    "IN": "India",
    "JP": "Japan",
    "MX": "Mexico",
    "RS": "Serbia",
    "SG": "Singapore",
    "UK": "United Kingdom",
    "US": "United States",
    "ZA": "South Africa",
}

DESTINATION_COLORS = {
    "UK": "#4E79A7",
    "US": "#59A14F",
    "ZA": "#B07AA1",
    "SG": "#FF9A86",
    "CA": "#76B7B2",
    "CH": "#F28E2B",
    "IN": "#EDC948",
    "AU": "#9C755F",
    "ID": "#FF9DA7",
    "BH": "#7B2525",
    "JP": "#7F7F7F",
    "CN": "#17BECF",
    "MX": "#A6761D",
    "BR": "#41431B",
    "CL": "#BCBD22",
    "AE": "#792CA2",
    "RS": "#FF0000",
}

MIN_INSIDE_LABEL_SHARE = 1.9


def country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code, code)


def destination_color(code: str) -> str:
    if code not in DESTINATION_COLORS:
        raise ValueError(f"Missing color for destination code: {code}")

    return DESTINATION_COLORS[code]


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


def destination_from_row(row: pd.Series) -> tuple[str, str]:
    region = row["region_clean"]
    country_code = str(row["country_code"])

    if region == "UK":
        return "UK", "United Kingdom"

    if region == "CH":
        return "CH", "Switzerland"

    return country_code, country_name(country_code)


def build_non_eu_destination_composition(main_df: pd.DataFrame) -> pd.DataFrame:
    non_eu_df = main_df[main_df["region_clean"] != "EU"].copy()

    if non_eu_df.empty:
        raise ValueError("No non-EU observations found.")

    destinations = non_eu_df.apply(destination_from_row, axis=1, result_type="expand")
    non_eu_df["destination_code"] = destinations[0]
    non_eu_df["destination_name"] = destinations[1]

    total_non_eu = int(non_eu_df["count"].sum())
    total_classifiable = int(main_df["count"].sum())

    destination_df = (
        non_eu_df.groupby(["destination_code", "destination_name"], as_index=False)["count"]
        .sum()
        .sort_values(["count", "destination_name"], ascending=[False, True])
        .reset_index(drop=True)
    )

    destination_df["share_non_eu"] = (destination_df["count"] / total_non_eu * 100).round(1)

    destination_df["share_all_classifiable"] = (
        destination_df["count"] / total_classifiable * 100
    ).round(1)

    return destination_df


def legend_label(row: pd.Series) -> str:
    return (
        f"{row['destination_code']} {row['destination_name']}: "
        f"{row['share_non_eu']:.1f}% ({int(row['count'])})"
    )


def add_inside_slice_labels(
    ax: plt.Axes,
    wedges: list[mpatches.Wedge],
    plot_df: pd.DataFrame,
) -> None:
    for wedge, row in zip(wedges, plot_df.itertuples(index=False)):
        share = float(row.share_non_eu)

        if share < MIN_INSIDE_LABEL_SHARE:
            continue

        angle = (wedge.theta1 + wedge.theta2) / 2
        angle_radians = math.radians(angle)

        if share >= 20:
            fontsize = 7.5
        elif share >= 8:
            fontsize = 6.8
        elif share >= 4:
            fontsize = 6.2
        else:
            fontsize = 5.6

        text_radius = 0.97
        x_text = text_radius * math.cos(angle_radians)
        y_text = text_radius * math.sin(angle_radians)

        ax.text(
            x_text,
            y_text,
            f"{row.destination_code}",
            ha="center",
            va="center",
            fontsize=fontsize,
            fontweight="semibold",
            color="white",
            path_effects=[
                path_effects.Stroke(linewidth=0.45, foreground="0.25"),
                path_effects.Normal(),
            ],
            zorder=5,
        )


def plot_non_eu_destination_donut(destination_df: pd.DataFrame) -> None:
    plot_df = destination_df.copy()
    total_non_eu = int(plot_df["count"].sum())

    colors = [destination_color(code) for code in plot_df["destination_code"]]

    fig = plt.figure(figsize=(5.4, 3.05))
    grid = fig.add_gridspec(
        1,
        2,
        width_ratios=[1.25, 0.85],
        wspace=0.00,
    )

    ax = fig.add_subplot(grid[0, 0])
    legend_ax = fig.add_subplot(grid[0, 1])
    legend_ax.set_axis_off()

    wedges, _ = ax.pie(
        plot_df["count"],
        colors=colors,
        startangle=90,
        counterclock=False,
        radius=1.18,
        wedgeprops={
            "width": 0.42,
            "edgecolor": "white",
            "linewidth": 0.2,
        },
    )

    add_inside_slice_labels(ax, wedges, plot_df)

    ax.text(
        0,
        0.10,
        "Non-EU answers",
        ha="center",
        va="center",
        fontsize=10.5,
        fontweight="bold",
    )

    ax.text(
        0,
        -0.12,
        f"{total_non_eu} observations",
        ha="center",
        va="center",
        fontsize=8.2,
        color="0.30",
    )

    ax.set_aspect("equal")
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)
    ax.set_axis_off()

    legend_ax.text(
        0.00,
        0.965,
        "Non-EU responding countries",
        ha="left",
        va="top",
        fontsize=7.7,
        fontweight="bold",
    )

    y = 0.905
    line_height = 0.0525

    for _, row in plot_df.iterrows():
        color = destination_color(row["destination_code"])

        legend_ax.add_patch(
            mpatches.Rectangle(
                (0.000, y - 0.014),
                0.026,
                0.026,
                transform=legend_ax.transAxes,
                facecolor=color,
                edgecolor="none",
                clip_on=False,
            )
        )

        legend_ax.text(
            0.040,
            y,
            legend_label(row),
            ha="left",
            va="center",
            fontsize=5.45,
            color="black",
            clip_on=False,
        )

        y -= line_height

    fig.subplots_adjust(left=0.005, right=0.995, top=0.99, bottom=0.01)

    save_figure("non_eu_destination_composition", fig)


def print_summary(
    region_df: pd.DataFrame,
    destination_df: pd.DataFrame,
) -> None:
    print("\nOverall region breakdown")
    print(region_df.to_string(index=False))

    print("\nAll non-EU destinations")
    print(destination_df.to_string(index=False))


def main() -> None:
    setup_style()

    summary_df = load_nsid_summary()
    main_df = main_classifiable_summary(summary_df)

    total_classifiable = int(main_df["count"].sum())

    if total_classifiable == 0:
        raise ValueError("No high or medium confidence classified observations found.")

    region_df = build_region_breakdown(main_df)
    destination_df = build_non_eu_destination_composition(main_df)

    save_table(region_df, "non_eu_region_breakdown")
    save_table(destination_df, "non_eu_destination_composition")

    plot_non_eu_destination_donut(destination_df)

    print_summary(
        region_df,
        destination_df,
    )

    print("\nGenerated files")
    print("Figure:")
    print("  results/figures/non_eu_destination_composition.pdf")
    print("Tables:")
    print("  results/tables/non_eu_region_breakdown.tsv")
    print("  results/tables/non_eu_destination_composition.tsv")


if __name__ == "__main__":
    main()
