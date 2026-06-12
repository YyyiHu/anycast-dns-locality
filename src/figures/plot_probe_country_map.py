from __future__ import annotations

import math

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from common import (
    MAP_BINS,
    MAP_COLORS,
    MAP_FILE,
    MAP_LABELS,
    load_data,
    main_classifiable_observations,
    save_figure,
    setup_style,
)
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path
from shapely.geometry import box

COUNTRY_CODE_COLUMN_CANDIDATES = ["ISO_A2_EH", "ISO_A2"]

REQUIRED_CASE_STUDY_COUNTRIES = ["PT", "ES", "DK", "LV", "BE", "IE", "IT", "FR"]
MAX_CASE_STUDY_COUNTRIES = 8

COUNTRY_NAMES = {
    "AT": "Austria",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "HR": "Croatia",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DK": "Denmark",
    "EE": "Estonia",
    "FI": "Finland",
    "FR": "France",
    "DE": "Germany",
    "GR": "Greece",
    "HU": "Hungary",
    "IE": "Ireland",
    "IT": "Italy",
    "LV": "Latvia",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "MT": "Malta",
    "NL": "Netherlands",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "SK": "Slovakia",
    "SI": "Slovenia",
    "ES": "Spain",
    "SE": "Sweden",
    "GB": "United Kingdom",
    "CH": "Switzerland",
    "US": "United States",
    "ZA": "South Africa",
    "SG": "Singapore",
    "CA": "Canada",
    "IN": "India",
    "ID": "Indonesia",
    "AU": "Australia",
    "JP": "Japan",
    "BH": "Bahrain",
    "CN": "China",
    "RU": "Russia",
    "AE": "United Arab Emirates",
    "BR": "Brazil",
    "CL": "Chile",
    "MX": "Mexico",
}

DESTINATION_LABELS = {
    "GB": "United Kingdom",
    "CH": "Switzerland",
    "US": "United States",
    "ZA": "South Africa",
    "SG": "Singapore",
    "CA": "Canada",
    "IN": "India",
    "ID": "Indonesia",
    "AU": "Australia",
    "JP": "Japan",
    "BH": "Bahrain",
    "CN": "China",
    "RU": "Russia",
    "AE": "United Arab Emirates",
    "BR": "Brazil",
    "CL": "Chile",
    "MX": "Mexico",
}

DESTINATION_COLORS = {
    "United Kingdom": "#4E79A7",
    "Switzerland": "#F28E2B",
    "United States": "#59A14F",
    "South Africa": "#B07AA1",
    "Singapore": "#E15759",
    "Canada": "#76B7B2",
    "India": "#EDC948",
    "Indonesia": "#FF9DA7",
    "Australia": "#9C755F",
    "Japan": "#7F7F7F",
    "Bahrain": "#1A312C",
    "China": "#17BECF",
    "Russia": "#8C6D31",
    "United Arab Emirates": "#6B6ECF",
    "Brazil": "#D37295",
    "Chile": "#BCBD22",
    "Mexico": "#A6761D",
}

FALLBACK_DESTINATION_COLORS = [
    "#4E79A7",
    "#F28E2B",
    "#59A14F",
    "#B07AA1",
    "#E15759",
    "#76B7B2",
    "#EDC948",
    "#9C755F",
    "#AF7AA1",
    "#17BECF",
]

LABEL_OFFSETS = {
    "PT": (-125_000, -60_000),
    "ES": (-70_000, -125_000),
    "FR": (-35_000, -95_000),
    "IE": (-60_000, 30_000),
    "DK": (65_000, 75_000),
    "BE": (-90_000, 80_000),
    "NL": (60_000, 100_000),
    "LU": (130_000, -45_000),
    "DE": (25_000, 10_000),
    "CZ": (-105_000, 85_000),
    "SK": (-165_000, 150_000),
    "HU": (235_000, -165_000),
    "AT": (-115_000, -45_000),
    "SI": (-130_000, -110_000),
    "HR": (135_000, -145_000),
    "IT": (145_000, -165_000),
    "PL": (75_000, 60_000),
    "LT": (115_000, 70_000),
    "LV": (120_000, 90_000),
    "EE": (105_000, 85_000),
    "FI": (120_000, 90_000),
    "SE": (105_000, 70_000),
    "RO": (210_000, 75_000),
    "BG": (120_000, -35_000),
    "GR": (-215_000, -315_000),
    "CY": (585_000, -135_000),
    "MT": (525_000, -245_000),
}


def country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code, code)


def destination_color(destination: str) -> str:
    if destination in DESTINATION_COLORS:
        return DESTINATION_COLORS[destination]

    index = sum(ord(character) for character in destination) % len(FALLBACK_DESTINATION_COLORS)

    return FALLBACK_DESTINATION_COLORS[index]


def normalize_region_value(value: object) -> str:
    if pd.isna(value):
        return "Unknown"

    text = str(value).strip()

    if text == "Other non EU":
        return "Other non-EU"

    return text


def add_probe_country(
    df: pd.DataFrame,
    probe_df: pd.DataFrame,
) -> pd.DataFrame:
    df = df.copy()

    if "probe_country" in df.columns:
        return df

    if "country" in df.columns:
        df["probe_country"] = df["country"]
        return df

    if "country" not in probe_df.columns:
        raise ValueError("Expected country column in either observations or probe metadata.")

    probe_country_df = probe_df[["probe_id", "country"]].drop_duplicates(
        subset=["probe_id"],
    )

    row_count_before = len(df)

    df = df.merge(
        probe_country_df,
        on="probe_id",
        how="left",
        validate="many_to_one",
    )

    if len(df) != row_count_before:
        raise ValueError("Probe country merge changed the number of observation rows.")

    return df.rename(columns={"country": "probe_country"})


def classified_observations_with_probe_country(
    obs_df: pd.DataFrame,
    probe_df: pd.DataFrame,
) -> pd.DataFrame:
    df = main_classifiable_observations(obs_df).copy()

    if "region_clean" not in df.columns:
        if "region_class" not in df.columns:
            raise ValueError("Expected either region_clean or region_class in observations.")

        df["region_clean"] = df["region_class"].apply(normalize_region_value)
    else:
        df["region_clean"] = df["region_clean"].apply(normalize_region_value)

    return add_probe_country(df, probe_df)


def country_non_eu_stats(
    obs_df: pd.DataFrame,
    probe_df: pd.DataFrame,
) -> pd.DataFrame:
    df = classified_observations_with_probe_country(obs_df, probe_df)
    df = df.dropna(subset=["probe_country"]).copy()
    df["outside_eu"] = df["region_clean"] != "EU"

    grouped = df.groupby("probe_country", as_index=False).agg(
        classifiable=("probe_id", "size"),
        outside_eu=("outside_eu", "sum"),
    )

    grouped["outside_eu_percent"] = grouped["outside_eu"] / grouped["classifiable"] * 100

    return (
        grouped.rename(columns={"probe_country": "country"})
        .sort_values(["outside_eu_percent", "outside_eu"], ascending=[False, False])
        .reset_index(drop=True)
    )


def country_stats_lookup(stats: pd.DataFrame) -> dict[str, dict[str, float]]:
    return {
        row.country: {
            "classifiable": int(row.classifiable),
            "outside_eu": int(row.outside_eu),
            "outside_eu_percent": float(row.outside_eu_percent),
        }
        for row in stats.itertuples(index=False)
    }


def map_bin_index(value: object) -> int | None:
    if pd.isna(value):
        return None

    number = float(value)

    for index, (lower, upper) in enumerate(zip(MAP_BINS[:-1], MAP_BINS[1:])):
        if lower <= number < upper:
            return index

    if number == 100:
        return len(MAP_BINS) - 2

    return None


def color_for_map_value(value: object) -> str:
    index = map_bin_index(value)

    if index is None:
        return "#E6E6E6"

    return MAP_COLORS[index]


def read_europe_boundaries(country_codes: list[str]) -> gpd.GeoDataFrame:
    if not MAP_FILE.exists():
        raise FileNotFoundError(f"Missing shapefile: {MAP_FILE}")

    world = gpd.read_file(MAP_FILE)

    country_column = next(
        column for column in COUNTRY_CODE_COLUMN_CANDIDATES if column in world.columns
    )

    countries = world[world[country_column].isin(country_codes)].copy()
    countries["country"] = countries[country_column]

    europe_bbox = gpd.GeoDataFrame(
        geometry=[box(-25, 33, 35, 72)],
        crs="EPSG:4326",
    )

    clipped = gpd.clip(countries, europe_bbox)

    return clipped.to_crs("EPSG:3035")


def map_label_text(country: str, value: float) -> str:
    return f"{country}\n{value:.1f}%"


def add_all_country_labels(ax: plt.Axes, europe: gpd.GeoDataFrame) -> None:
    for _, row in europe.iterrows():
        country = row["country"]
        value = row["outside_eu_percent"]

        if pd.isna(value) or row.geometry.is_empty:
            continue

        point = row.geometry.representative_point()
        dx, dy = LABEL_OFFSETS.get(country, (0, 0))
        label_x = point.x + dx
        label_y = point.y + dy

        if dx != 0 or dy != 0:
            ax.plot(
                [point.x, label_x],
                [point.y, label_y],
                color="0.48",
                linewidth=0.23,
                zorder=5,
                clip_on=False,
            )

        ax.text(
            label_x,
            label_y,
            map_label_text(country, value),
            ha="center",
            va="center",
            fontsize=4.25,
            color="black",
            bbox={
                "boxstyle": "round,pad=0.075",
                "facecolor": "white",
                "edgecolor": "0.82",
                "linewidth": 0.18,
                "alpha": 0.91,
            },
            zorder=6,
            clip_on=False,
        )


def add_map_legend(ax: plt.Axes) -> None:
    legend_handles = [
        mpatches.Patch(facecolor=color, edgecolor="white", label=label)
        for color, label in zip(MAP_COLORS, MAP_LABELS)
    ]

    ax.legend(
        handles=legend_handles,
        title="Outside EU answer share",
        loc="upper left",
        bbox_to_anchor=(0.015, 0.985),
        frameon=True,
        framealpha=1,
        borderpad=0.50,
        fontsize=6.0,
        title_fontsize=6.0,
    )


def plot_probe_country_non_eu_map(
    obs_df: pd.DataFrame,
    probe_df: pd.DataFrame,
) -> None:
    stats = country_non_eu_stats(obs_df, probe_df)
    country_codes = sorted(stats["country"].dropna().unique().tolist())

    europe = read_europe_boundaries(country_codes)
    europe = europe.merge(stats, on="country", how="left")
    europe["plot_color"] = europe["outside_eu_percent"].apply(color_for_map_value)

    fig, ax = plt.subplots(figsize=(4.05, 4.05))

    europe.plot(
        ax=ax,
        color=europe["plot_color"],
        edgecolor="#FFFFFF",
        linewidth=0.45,
        missing_kwds={"color": "#E6E6E6", "edgecolor": "#FFFFFF"},
        zorder=1,
    )

    europe.boundary.plot(
        ax=ax,
        linewidth=0.24,
        color="#666666",
        zorder=2,
    )

    ax.set_axis_off()

    minx, miny, maxx, maxy = europe.total_bounds
    ax.set_xlim(minx - 245_000, maxx + 650_000)
    ax.set_ylim(miny - 760_000, maxy + 190_000)

    add_all_country_labels(ax, europe)
    add_map_legend(ax)

    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    save_figure("probe_country_non_eu_map", fig)


def destination_label(row: pd.Series) -> str | None:
    country_code = row.get("country_code")
    region = row.get("region_clean")

    if pd.isna(country_code):
        return None

    country_code = str(country_code)

    if region == "UK":
        return "United Kingdom"

    if region == "CH":
        return "Switzerland"

    return DESTINATION_LABELS.get(country_code, country_code)


def non_eu_observations(
    obs_df: pd.DataFrame,
    probe_df: pd.DataFrame,
) -> pd.DataFrame:
    df = classified_observations_with_probe_country(obs_df, probe_df)
    df = df.dropna(subset=["probe_country", "country_code", "region_clean"]).copy()

    df = df[df["region_clean"] != "EU"].copy()
    df["destination_country"] = df.apply(destination_label, axis=1)

    return df.dropna(subset=["destination_country"])


def add_selection_reason(
    selected: dict[str, list[str]],
    country: str,
    reason: str,
) -> None:
    if country not in selected:
        selected[country] = []

    if reason not in selected[country]:
        selected[country].append(reason)


def select_case_study_countries(
    stats: pd.DataFrame,
    non_eu_df: pd.DataFrame,
) -> dict[str, list[str]]:
    selected: dict[str, list[str]] = {}
    countries_with_non_eu = set(non_eu_df["probe_country"])

    for country in REQUIRED_CASE_STUDY_COUNTRIES:
        if country in countries_with_non_eu:
            add_selection_reason(selected, country, "selected case study country")

    return dict(list(selected.items())[:MAX_CASE_STUDY_COUNTRIES])


def group_destinations_for_country(
    non_eu_df: pd.DataFrame,
    probe_country: str,
) -> pd.DataFrame:
    flows = (
        non_eu_df[non_eu_df["probe_country"] == probe_country]
        .groupby("destination_country", as_index=False)
        .agg(value=("probe_id", "size"))
        .sort_values(["value", "destination_country"], ascending=[False, True])
        .reset_index(drop=True)
    )

    total = flows["value"].sum()
    flows["share"] = flows["value"] / total

    return flows


def label_positions_for_destinations(
    destination_count: int,
    low: float,
    high: float,
) -> list[float]:
    if destination_count <= 0:
        return []

    if destination_count == 1:
        return [(low + high) / 2]

    step = (high - low) / (destination_count - 1)

    return [high - index * step for index in range(destination_count)]


def add_sankey_flow(
    ax: plt.Axes,
    x0: float,
    x1: float,
    source_y0: float,
    source_y1: float,
    target_y0: float,
    target_y1: float,
    color: str,
) -> None:
    control_dx = (x1 - x0) * 0.54

    vertices = [
        (x0, source_y1),
        (x0 + control_dx, source_y1),
        (x1 - control_dx, target_y1),
        (x1, target_y1),
        (x1, target_y0),
        (x1 - control_dx, target_y0),
        (x0 + control_dx, source_y0),
        (x0, source_y0),
        (x0, source_y1),
    ]

    codes = [
        Path.MOVETO,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.LINETO,
        Path.CURVE4,
        Path.CURVE4,
        Path.CURVE4,
        Path.CLOSEPOLY,
    ]

    ax.add_patch(
        PathPatch(
            Path(vertices, codes),
            facecolor=color,
            edgecolor="white",
            linewidth=0.28,
            alpha=0.50,
            zorder=1,
        )
    )


def plot_single_country_sankey(
    ax: plt.Axes,
    flows: pd.DataFrame,
    probe_country: str,
    stats_lookup: dict[str, dict[str, float]],
) -> None:
    total = int(flows["value"].sum())

    if total == 0:
        ax.set_axis_off()
        return

    outside_eu_from_stats = int(stats_lookup[probe_country]["outside_eu"])
    outside_percent = float(stats_lookup[probe_country]["outside_eu_percent"])

    if total != outside_eu_from_stats:
        raise ValueError(
            f"Sankey total mismatch for {probe_country}: "
            f"{total} flow rows versus {outside_eu_from_stats} country stats."
        )

    destination_count = len(flows)

    x_left = 0.150
    x_right = 0.575
    label_x = 0.705
    node_width = 0.030

    y_bottom = 0.105
    y_top = 0.885

    target_gap = 0.018 if destination_count <= 5 else 0.010
    label_fontsize = 5.75 if destination_count <= 5 else 5.05

    available_height = y_top - y_bottom
    scale = (available_height - target_gap * max(0, destination_count - 1)) / total

    source_height = total * scale
    source_y0 = y_bottom + (available_height - source_height) / 2
    source_y1 = source_y0 + source_height

    target_positions = {}
    target_cursor = y_top

    for row in flows.itertuples(index=False):
        height = row.value * scale
        target_positions[row.destination_country] = {
            "y0": target_cursor - height,
            "y1": target_cursor,
            "height": height,
            "value": int(row.value),
        }
        target_cursor -= height + target_gap

    label_positions = label_positions_for_destinations(
        destination_count,
        low=0.075,
        high=0.915,
    )

    ax.add_patch(
        Rectangle(
            (x_left, source_y0),
            node_width,
            source_height,
            facecolor="#EFEFEF",
            edgecolor="#666666",
            linewidth=0.42,
            zorder=3,
        )
    )

    source_cursor = source_y1

    for row in flows.itertuples(index=False):
        height = row.value * scale
        flow_y1 = source_cursor
        flow_y0 = flow_y1 - height
        source_cursor = flow_y0

        target = target_positions[row.destination_country]
        color = destination_color(row.destination_country)

        add_sankey_flow(
            ax,
            x_left + node_width,
            x_right,
            flow_y0,
            flow_y1,
            target["y0"],
            target["y1"],
            color,
        )

    for (destination, position), label_y in zip(
        target_positions.items(),
        label_positions,
    ):
        color = destination_color(destination)
        center_y = (position["y0"] + position["y1"]) / 2
        share = position["value"] / total * 100

        ax.add_patch(
            Rectangle(
                (x_right, position["y0"]),
                node_width,
                position["height"],
                facecolor=color,
                edgecolor="0.45",
                linewidth=0.38,
                zorder=3,
            )
        )

        ax.plot(
            [x_right + node_width, label_x - 0.018],
            [center_y, label_y],
            color="0.58",
            linewidth=0.34,
            zorder=2,
        )

        ax.text(
            label_x,
            label_y,
            f"{destination}\n{share:.0f}% ({position['value']})",
            ha="left",
            va="center",
            fontsize=label_fontsize,
            linespacing=0.95,
            bbox={
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.88,
                "pad": 0.13,
            },
            zorder=4,
        )

    source_name = country_name(probe_country)
    source_label_y = (source_y0 + source_y1) / 2

    ax.text(
        x_left - 0.040,
        source_label_y + 0.045,
        f"{source_name} ({probe_country})",
        ha="right",
        va="center",
        fontsize=6.05,
        fontweight="bold",
    )

    ax.text(
        x_left - 0.040,
        source_label_y - 0.018,
        f"{total} outside EU",
        ha="right",
        va="center",
        fontsize=5.50,
        color="0.25",
    )

    ax.text(
        x_left - 0.040,
        source_label_y - 0.073,
        f"{outside_percent:.1f}% of classifiable obs.",
        ha="right",
        va="center",
        fontsize=5.15,
        color="0.25",
    )

    ax.set_xlim(0.00, 1.05)
    ax.set_ylim(0.035, 0.945)
    ax.set_axis_off()


def plot_selected_probe_country_sankeys(
    obs_df: pd.DataFrame,
    probe_df: pd.DataFrame,
) -> None:
    stats = country_non_eu_stats(obs_df, probe_df)
    stats_lookup = country_stats_lookup(stats)
    non_eu_df = non_eu_observations(obs_df, probe_df)
    selected = select_case_study_countries(stats, non_eu_df)

    non_eu_counts = non_eu_df.groupby("probe_country").size().sort_values(ascending=False)

    available_countries = [country for country in selected if country in non_eu_counts.index]

    available_countries = sorted(
        available_countries,
        key=lambda country: (-int(non_eu_counts[country]), country),
    )

    if len(available_countries) % 2 == 1:
        available_countries = available_countries[:-1]

    if not available_countries:
        raise ValueError("No non-EU observations found for selected Sankey countries.")

    columns = 2
    rows = math.ceil(len(available_countries) / columns)

    fig, axes = plt.subplots(rows, columns, figsize=(8.15, 2.55 * rows))

    if hasattr(axes, "flatten"):
        axes = axes.flatten().tolist()
    else:
        axes = [axes]

    for ax, country in zip(axes, available_countries):
        flows = group_destinations_for_country(non_eu_df, country)
        plot_single_country_sankey(ax, flows, country, stats_lookup)

    for ax in axes[len(available_countries) :]:
        ax.set_axis_off()

    fig.subplots_adjust(
        left=0.035,
        right=0.985,
        top=0.930,
        bottom=0.080,
        wspace=0.36,
        hspace=0.28,
    )

    save_figure("selected_probe_country_non_eu_sankeys", fig)

    print("Selected Sankey case study countries:")
    for country in available_countries:
        country_stats = stats_lookup[country]
        print(
            f"- {country_name(country)} ({country}): "
            f"{country_stats['outside_eu']} of {country_stats['classifiable']} "
            f"outside EU ({country_stats['outside_eu_percent']:.1f}%)"
        )


def main() -> None:
    setup_style()

    _, obs_df, probe_df = load_data()

    plot_probe_country_non_eu_map(obs_df, probe_df)
    plot_selected_probe_country_sankeys(obs_df, probe_df)

    print("Figures written to results/figures")


if __name__ == "__main__":
    main()
