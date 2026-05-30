import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common import (
    MAP_BINS,
    MAP_COLORS,
    MAP_FILE,
    MAP_LABELS,
    main_classifiable_observations,
    save_figure,
)
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch, Rectangle
from shapely.geometry import box


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


def color_for_map_value(value: float) -> str:
    if pd.isna(value):
        return "#E6E6E6"

    for lower, upper, color in zip(MAP_BINS[:-1], MAP_BINS[1:], MAP_COLORS):
        if lower <= value < upper:
            return color

    return MAP_COLORS[-1]


def read_europe_boundaries(country_codes: list[str]) -> gpd.GeoDataFrame:
    if not MAP_FILE.exists():
        raise FileNotFoundError(f"Missing shapefile: {MAP_FILE}")

    world = gpd.read_file(MAP_FILE)
    iso_col = "ISO_A2_EH" if "ISO_A2_EH" in world.columns else "ISO_A2"

    world = world[world[iso_col].isin(country_codes)].copy()
    world["country"] = world[iso_col]

    europe_bbox = gpd.GeoDataFrame(
        geometry=[box(-25, 33, 35, 72)],
        crs="EPSG:4326",
    )

    clipped = gpd.clip(world, europe_bbox)
    clipped = clipped.to_crs("EPSG:3035")

    return clipped


def draw_island_boxes(ax: plt.Axes, stats: pd.DataFrame) -> None:
    island_codes = ["CY", "MT"]
    x0 = 0.775
    y0 = 0.08
    width = 0.055
    height = 0.045
    gap = 0.018

    stat_lookup = stats.set_index("country")["outside_eu_percent"].to_dict()

    for idx, code in enumerate(island_codes):
        value = stat_lookup.get(code, np.nan)
        color = color_for_map_value(value)
        y = y0 + (len(island_codes) - 1 - idx) * (height + gap)

        rect = Rectangle(
            (x0, y),
            width,
            height,
            transform=ax.transAxes,
            facecolor=color,
            edgecolor="#555555",
            linewidth=0.5,
        )
        ax.add_patch(rect)

        label = f"{code} {value:.1f}%" if not pd.isna(value) else code
        ax.text(
            x0 + width + 0.012,
            y + height / 2,
            label,
            transform=ax.transAxes,
            fontsize=6.5,
            va="center",
        )


def plot_probe_country_non_eu_map(obs_df: pd.DataFrame, probe_df: pd.DataFrame) -> None:
    stats = country_non_eu_stats(obs_df)
    country_codes = sorted(probe_df["country"].dropna().unique().tolist())

    europe = read_europe_boundaries(country_codes)
    europe = europe.merge(stats, on="country", how="left")

    main_map = europe[~europe["country"].isin(["MT", "CY"])].copy()

    cmap = ListedColormap(MAP_COLORS)
    norm = BoundaryNorm(MAP_BINS, cmap.N)

    fig, ax = plt.subplots(figsize=(7.3, 5.3))

    main_map.plot(
        column="outside_eu_percent",
        cmap=cmap,
        norm=norm,
        ax=ax,
        linewidth=0.55,
        edgecolor="white",
        missing_kwds={"color": "#E6E6E6", "edgecolor": "white"},
    )

    main_map.boundary.plot(ax=ax, linewidth=0.25, color="#666666")

    top_labels = set(stats.head(5)["country"].tolist())
    low_labels = set(stats.tail(3)["country"].tolist())

    label_countries = top_labels.union(low_labels)

    # PT and ES are already shown in the summary callout, and their map labels
    # would sit near the lower crop edge.
    label_countries = label_countries.difference({"PT", "ES"})

    for _, row in main_map.iterrows():
        if row.geometry.is_empty or row["country"] not in label_countries:
            continue

        point = row.geometry.representative_point()
        value = row["outside_eu_percent"]

        ax.text(
            point.x,
            point.y,
            f"{row['country']}\n{value:.0f}%",
            ha="center",
            va="center",
            fontsize=6.3,
            color="black",
            bbox={
                "boxstyle": "round,pad=0.14",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.78,
            },
        )

    ax.set_axis_off()

    minx, miny, maxx, maxy = main_map.total_bounds
    ax.set_xlim(minx - 220000, maxx + 180000)
    ax.set_ylim(miny - 520000, maxy + 180000)

    legend_handles = [
        Patch(facecolor=color, edgecolor="white", label=label)
        for color, label in zip(MAP_COLORS, MAP_LABELS)
    ]

    ax.legend(
        handles=legend_handles,
        title="Outside-EU answer share",
        loc="lower left",
        frameon=True,
        framealpha=1,
        borderpad=0.6,
    )

    draw_island_boxes(ax, stats)

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
            "boxstyle": "round,pad=0.35",
            "facecolor": "white",
            "edgecolor": "#C7C7C7",
        },
    )

    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    save_figure("probe_country_non_eu_map", fig)
