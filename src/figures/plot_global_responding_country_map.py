from __future__ import annotations

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from common import (
    MAP_FILE,
    load_nsid_summary,
    main_classifiable_summary,
    save_figure,
    save_table,
    setup_style,
)

COUNTRY_NAMES = {
    "AE": "United Arab Emirates",
    "AT": "Austria",
    "AU": "Australia",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BR": "Brazil",
    "CA": "Canada",
    "CH": "Switzerland",
    "CL": "Chile",
    "CN": "China",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IN": "India",
    "IT": "Italy",
    "JP": "Japan",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "MT": "Malta",
    "MX": "Mexico",
    "NL": "Netherlands",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RS": "Serbia",
    "SE": "Sweden",
    "SG": "Singapore",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "UK": "United Kingdom",
    "US": "United States",
    "ZA": "South Africa",
}

MAP_COUNTRY_ALIASES = {
    "UK": "GB",
}

COUNTRY_CODE_COLUMN_CANDIDATES = [
    "ISO_A2_EH",
    "ISO_A2",
    "iso_a2",
    "ADM0_A2",
]

EUROPEAN_MAP_COUNTRY_CODES = {
    "AT",
    "BE",
    "BG",
    "CH",
    "CY",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "GR",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "RS",
    "SE",
    "SI",
    "SK",
}

EUROPE_LON_MIN = -25
EUROPE_LON_MAX = 45
EUROPE_LAT_MIN = 34
EUROPE_LAT_MAX = 72

SHARE_BINS = [0, 1, 2.5, 5, 10, 20, float("inf")]

SHARE_LABELS = [
    ">0 to 1%",
    "1 to 2.5%",
    "2.5 to 5%",
    "5 to 10%",
    "10 to 20%",
    "20%+",
]

SHARE_COLORS = {
    ">0 to 1%": "#CFECF3",
    "1 to 2.5%": "#8CC0EB",
    "2.5 to 5%": "#1591DC",
    "5 to 10%": "#2F578A",
    "10 to 20%": "#6A3D9A",
    "20%+": "#3F007D",
}

MISSING_COLOR = "#F5F5F5"
BORDER_COLOR = "#A8A8A8"

PROJECTION = "+proj=robin +lon_0=0 +datum=WGS84 +units=m +no_defs"


def country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code, code)


def map_country_code(code: str) -> str:
    return MAP_COUNTRY_ALIASES.get(code, code)


def find_country_code_column(world_df: gpd.GeoDataFrame) -> str:
    for column in COUNTRY_CODE_COLUMN_CANDIDATES:
        if column in world_df.columns:
            return column

    raise ValueError(
        "Could not find an ISO A2 country code column in the map file. "
        f"Tried: {COUNTRY_CODE_COLUMN_CANDIDATES}"
    )


def keep_core_geometries_for_european_countries(
    world_df: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    exploded_df = world_df.explode(index_parts=False).copy()
    representative_points = exploded_df.geometry.representative_point()

    in_europe_window = representative_points.x.between(
        EUROPE_LON_MIN,
        EUROPE_LON_MAX,
    ) & representative_points.y.between(
        EUROPE_LAT_MIN,
        EUROPE_LAT_MAX,
    )

    is_european_country = exploded_df["map_country_code"].isin(EUROPEAN_MAP_COUNTRY_CODES)

    keep_geometry = ~(is_european_country & ~in_europe_window)

    return exploded_df.loc[keep_geometry].reset_index(drop=True)


def responding_country_from_row(row: pd.Series) -> tuple[str, str]:
    region = row["region_clean"]
    country_code = str(row["country_code"])

    if region == "UK":
        return "UK", "United Kingdom"

    if region == "CH":
        return "CH", "Switzerland"

    return country_code, country_name(country_code)


def build_responding_country_summary(main_df: pd.DataFrame) -> pd.DataFrame:
    total_classifiable = int(main_df["count"].sum())

    if total_classifiable == 0:
        raise ValueError("No high or medium confidence classified observations found.")

    responding_df = main_df.copy()

    responding_countries = responding_df.apply(
        responding_country_from_row,
        axis=1,
        result_type="expand",
    )

    responding_df["country_code"] = responding_countries[0]
    responding_df["country_name"] = responding_countries[1]

    country_df = (
        responding_df.groupby(["country_code", "country_name"], as_index=False)["count"]
        .sum()
        .sort_values(["count", "country_name"], ascending=[False, True])
        .reset_index(drop=True)
    )

    country_df["map_country_code"] = country_df["country_code"].map(map_country_code)
    country_df["share_classifiable"] = (country_df["count"] / total_classifiable * 100).round(1)

    return country_df[
        [
            "country_code",
            "country_name",
            "map_country_code",
            "count",
            "share_classifiable",
        ]
    ]


def read_world_boundaries() -> gpd.GeoDataFrame:
    world_df = gpd.read_file(MAP_FILE)
    country_code_column = find_country_code_column(world_df)

    world_df = world_df[world_df.geometry.notna()].copy()
    world_df = world_df.rename(columns={country_code_column: "map_country_code"})
    world_df["map_country_code"] = world_df["map_country_code"].astype(str)

    if "ADMIN" in world_df.columns:
        world_df = world_df[world_df["ADMIN"] != "Antarctica"].copy()
    elif "NAME" in world_df.columns:
        world_df = world_df[world_df["NAME"] != "Antarctica"].copy()

    if world_df.crs is None:
        world_df = world_df.set_crs("EPSG:4326")
    else:
        world_df = world_df.to_crs("EPSG:4326")

    world_df = keep_core_geometries_for_european_countries(world_df)

    return world_df.to_crs(PROJECTION)


def prepare_plot_df(
    world_df: gpd.GeoDataFrame,
    country_df: pd.DataFrame,
) -> gpd.GeoDataFrame:
    plot_df = world_df.merge(
        country_df,
        on="map_country_code",
        how="left",
    )

    plot_df["count"] = plot_df["count"].fillna(0).astype(int)
    plot_df["share_classifiable"] = plot_df["share_classifiable"].fillna(0.0)

    plot_df["share_bin"] = pd.cut(
        plot_df["share_classifiable"],
        bins=SHARE_BINS,
        labels=SHARE_LABELS,
        include_lowest=True,
        right=False,
    )

    plot_df["plot_color"] = plot_df["share_bin"].map(SHARE_COLORS).astype(object)
    plot_df.loc[plot_df["count"] == 0, "plot_color"] = MISSING_COLOR

    return plot_df


def add_legend(ax: plt.Axes) -> None:
    handles = [
        mpatches.Patch(
            facecolor=SHARE_COLORS[label],
            edgecolor="none",
            label=label,
        )
        for label in SHARE_LABELS
    ]

    handles.append(
        mpatches.Patch(
            facecolor=MISSING_COLOR,
            edgecolor=BORDER_COLOR,
            label="Not observed",
        )
    )

    ax.legend(
        handles=handles,
        title="Share of classifiable observations",
        loc="lower left",
        bbox_to_anchor=(0.012, 0.035),
        frameon=True,
        framealpha=0.97,
        fontsize=5.9,
        title_fontsize=6.4,
        borderpad=0.55,
        labelspacing=0.35,
        handlelength=1.25,
        handleheight=0.75,
    )


def plot_global_responding_country_map(country_df: pd.DataFrame) -> None:
    world_df = read_world_boundaries()
    plot_df = prepare_plot_df(world_df, country_df)

    fig, ax = plt.subplots(figsize=(6.7, 3.45))

    plot_df.plot(
        ax=ax,
        color=plot_df["plot_color"],
        edgecolor=BORDER_COLOR,
        linewidth=0.30,
    )

    add_legend(ax)

    ax.set_axis_off()

    ax.set_title(
        "Responding replica countries",
        fontsize=8.8,
        fontweight="bold",
        pad=1,
    )

    fig.subplots_adjust(left=0.01, right=0.995, top=0.965, bottom=0.02)

    save_figure("global_responding_country_map", fig)


def print_summary(country_df: pd.DataFrame) -> None:
    print("\nResponding country summary")
    print(country_df.to_string(index=False))


def main() -> None:
    setup_style()

    summary_df = load_nsid_summary()
    main_df = main_classifiable_summary(summary_df)

    country_df = build_responding_country_summary(main_df)

    save_table(country_df, "global_responding_country_summary")
    plot_global_responding_country_map(country_df)

    print_summary(country_df)

    print("\nGenerated files")
    print("Figure:")
    print("  results/figures/global_responding_country_map.pdf")
    print("Table:")
    print("  results/tables/global_responding_country_summary.tsv")


if __name__ == "__main__":
    main()
