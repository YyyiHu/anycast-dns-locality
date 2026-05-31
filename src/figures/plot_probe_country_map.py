import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from common import (
    MAP_BINS,
    MAP_COLORS,
    MAP_FILE,
    MAP_LABELS,
    main_classifiable_observations,
    save_figure,
)
from shapely.geometry import box

COUNTRY_CODE_COLUMN_CANDIDATES = ["ISO_A2_EH", "ISO_A2"]

LABEL_COUNTRIES = {
    "IE",
    "DK",
    "CZ",
    "SK",
    "BG",
    "IT",
}

LABEL_OFFSETS = {
    "IE": (-40_000, 20_000),
    "DK": (45_000, 35_000),
    "CZ": (25_000, 0),
    "SK": (60_000, -20_000),
    "BG": (55_000, -10_000),
    "IT": (120_000, -150_000),
}


def country_non_eu_stats(obs_df: pd.DataFrame) -> pd.DataFrame:
    df = main_classifiable_observations(obs_df)
    df = df.dropna(subset=["country"]).copy()
    df["outside_eu"] = df["region_clean"] != "EU"

    grouped = df.groupby("country", as_index=False).agg(
        classifiable=("probe_id", "size"),
        outside_eu=("outside_eu", "sum"),
    )

    grouped["outside_eu_percent"] = grouped["outside_eu"] / grouped["classifiable"] * 100

    return grouped.sort_values("outside_eu_percent", ascending=False)


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


def add_small_island_boxes(ax: plt.Axes, stats: pd.DataFrame) -> None:
    stat_lookup = stats.set_index("country")["outside_eu_percent"].to_dict()

    island_specs = [
        ("CY", 0.77, 0.145),
        ("MT", 0.77, 0.070),
    ]

    for code, x, y in island_specs:
        value = stat_lookup.get(code)

        rect = mpatches.Rectangle(
            (x, y),
            0.055,
            0.045,
            transform=ax.transAxes,
            facecolor=color_for_map_value(value),
            edgecolor="#555555",
            linewidth=0.45,
        )
        ax.add_patch(rect)

        label = f"{code} {value:.1f}%" if value is not None else code
        ax.text(
            x + 0.065,
            y + 0.0225,
            label,
            transform=ax.transAxes,
            fontsize=6.5,
            va="center",
            ha="left",
        )


def add_country_labels(ax: plt.Axes, europe: gpd.GeoDataFrame, stats: pd.DataFrame) -> None:
    top_countries = set(stats.head(5)["country"].tolist())
    low_countries = set(stats.tail(3)["country"].tolist())

    label_countries = LABEL_COUNTRIES.union(top_countries).union(low_countries)

    # These are already listed in the callout and usually sit too close to the crop edge.
    label_countries = label_countries.difference({"PT", "ES", "MT", "CY"})

    for _, row in europe.iterrows():
        country = row["country"]
        value = row["outside_eu_percent"]

        if country not in label_countries or pd.isna(value) or row.geometry.is_empty:
            continue

        point = row.geometry.representative_point()
        dx, dy = LABEL_OFFSETS.get(country, (0, 0))

        ax.text(
            point.x + dx,
            point.y + dy,
            f"{country}\n{value:.0f}%",
            ha="center",
            va="center",
            fontsize=6.4,
            color="black",
            bbox={
                "boxstyle": "round,pad=0.12",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.78,
            },
        )


def add_top_country_callout(ax: plt.Axes, stats: pd.DataFrame) -> None:
    top_three = stats.head(3)

    top_text = "\n".join(
        f"{row.country}: {row.outside_eu_percent:.1f}%" for row in top_three.itertuples()
    )

    ax.text(
        0.02,
        0.98,
        "Highest outside-EU shares\n" + top_text,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=7,
        bbox={
            "boxstyle": "round,pad=0.28",
            "facecolor": "white",
            "edgecolor": "#C7C7C7",
        },
    )


def add_map_legend(ax: plt.Axes) -> None:
    legend_handles = [
        mpatches.Patch(facecolor=color, edgecolor="white", label=label)
        for color, label in zip(MAP_COLORS, MAP_LABELS)
    ]

    ax.legend(
        handles=legend_handles,
        title="Outside-EU answer share",
        loc="lower left",
        frameon=True,
        framealpha=1,
        borderpad=0.55,
        fontsize=6.7,
        title_fontsize=6.7,
    )


def plot_probe_country_non_eu_map(
    obs_df: pd.DataFrame,
    probe_df: pd.DataFrame,
) -> None:
    stats = country_non_eu_stats(obs_df)
    country_codes = sorted(probe_df["country"].dropna().unique().tolist())

    europe = read_europe_boundaries(country_codes)
    europe = europe.merge(stats, on="country", how="left")

    main_map = europe[~europe["country"].isin(["MT", "CY"])].copy()
    main_map["plot_color"] = main_map["outside_eu_percent"].apply(color_for_map_value)

    fig, ax = plt.subplots(figsize=(3.35, 3.35))

    main_map.plot(
        ax=ax,
        color=main_map["plot_color"],
        edgecolor="#FFFFFF",
        linewidth=0.45,
        missing_kwds={"color": "#E6E6E6", "edgecolor": "#FFFFFF"},
    )

    main_map.boundary.plot(ax=ax, linewidth=0.25, color="#666666")

    ax.set_axis_off()

    minx, miny, maxx, maxy = main_map.total_bounds
    ax.set_xlim(minx - 180_000, maxx + 160_000)
    ax.set_ylim(miny - 430_000, maxy + 170_000)

    add_country_labels(ax, main_map, stats)
    add_small_island_boxes(ax, stats)
    add_top_country_callout(ax, stats)
    add_map_legend(ax)

    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    save_figure("probe_country_non_eu_map", fig)
