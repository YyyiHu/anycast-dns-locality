import re
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common import REGION_COLORS, REGION_ORDER, load_data, save_figure, setup_style
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D

REGION_COLUMNS = {
    "EU": "eu",
    "UK": "uk",
    "CH": "ch",
    "Other non-EU": "other_non_eu",
}

REQUIRED_COLUMNS = {
    "cctld",
    "nameserver",
    "main_classifiable",
    "eu",
    "uk",
    "ch",
    "other_non_eu",
}

NAMESERVER_LIGHTEN_AMOUNT = 0.45
CCTLD_BAR_HEIGHT = 0.36
NAMESERVER_BAR_HEIGHT = 0.14


def validate_columns(df: pd.DataFrame) -> None:
    missing_columns = REQUIRED_COLUMNS - set(df.columns)

    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")


def lighten_color(
    color: str, amount: float = NAMESERVER_LIGHTEN_AMOUNT
) -> tuple[float, float, float]:
    r, g, b = to_rgb(color)

    return (
        r + (1.0 - r) * amount,
        g + (1.0 - g) * amount,
        b + (1.0 - b) * amount,
    )


def get_text_color(background_color: str | tuple[float, float, float]) -> str:
    r, g, b = to_rgb(background_color)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b

    return "black" if luminance > 0.55 else "white"


def add_region_shares(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for region, column in REGION_COLUMNS.items():
        df[region] = df[column]
        df[f"{region}_share"] = df[column] / df["main_classifiable"] * 100

    df["eu_share"] = df["eu"] / df["main_classifiable"] * 100

    return df


def clean_target_label(row: pd.Series) -> str:
    if "nameserver" in row and pd.notna(row["nameserver"]):
        return str(row["nameserver"])

    label = str(row["target_label"])

    return re.sub(r"\s+\([^)]*\)$", "", label)


def build_cctld_rows(target_df: pd.DataFrame) -> pd.DataFrame:
    cctld_df = target_df.groupby("cctld", as_index=False).agg(
        targets=("nameserver", "count"),
        main_classifiable=("main_classifiable", "sum"),
        eu=("eu", "sum"),
        uk=("uk", "sum"),
        ch=("ch", "sum"),
        other_non_eu=("other_non_eu", "sum"),
    )

    cctld_df = add_region_shares(cctld_df)
    cctld_df = cctld_df.sort_values("eu_share", ascending=True).reset_index(drop=True)

    return cctld_df


def build_plot_rows(
    target_df: pd.DataFrame,
    cctld_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[float], list[dict[str, Any]]]:
    rows = []
    y_positions = []
    group_spans = []

    y = 0.0

    for _, cctld_row in cctld_df.iterrows():
        cctld = cctld_row["cctld"]

        group_start = y - 0.30
        nameserver_start_y = y + 0.52

        aggregate_row = {
            "row_type": "cctld",
            "label": f"{cctld} ({int(cctld_row['targets'])} targets)",
            "eu_share": cctld_row["eu_share"],
        }

        for region in REGION_ORDER:
            aggregate_row[f"{region}_share"] = cctld_row[f"{region}_share"]

        rows.append(aggregate_row)
        y_positions.append(y)

        y += 0.54

        nameserver_rows = (
            target_df[target_df["cctld"] == cctld]
            .sort_values("eu_share", ascending=True)
            .reset_index(drop=True)
        )

        for _, nameserver_row in nameserver_rows.iterrows():
            row = {
                "row_type": "nameserver",
                "label": f"    {clean_target_label(nameserver_row)}",
                "eu_share": nameserver_row["eu_share"],
            }

            for region in REGION_ORDER:
                row[f"{region}_share"] = nameserver_row[f"{region}_share"]

            rows.append(row)
            y_positions.append(y)

            y += 0.32

        nameserver_end_y = y - 0.32
        group_end = y - 0.08

        group_spans.append(
            {
                "cctld": cctld,
                "start": group_start,
                "end": group_end,
                "nameserver_start_y": nameserver_start_y,
                "nameserver_end_y": nameserver_end_y,
                "eu_share": cctld_row["eu_share"],
            }
        )

        y += 0.36

    return pd.DataFrame(rows), y_positions, group_spans


def add_group_backgrounds(
    ax: plt.Axes,
    group_spans: list[dict[str, Any]],
) -> None:
    for index, group in enumerate(group_spans):
        ax.axhspan(
            group["start"],
            group["end"],
            facecolor="0.965" if index % 2 == 0 else "1.0",
            edgecolor="none",
            zorder=0,
        )

        ax.axhline(
            group["end"] + 0.10,
            color="0.88",
            linewidth=0.45,
            zorder=0,
        )


def plot_cctld_aggregate_rows(
    ax: plt.Axes,
    cctld_rows: pd.DataFrame,
    cctld_y: np.ndarray,
) -> None:
    left = np.zeros(len(cctld_rows))

    for region in REGION_ORDER:
        values = cctld_rows[f"{region}_share"].to_numpy()

        ax.barh(
            cctld_y,
            values,
            left=left,
            height=CCTLD_BAR_HEIGHT,
            label=region,
            color=REGION_COLORS[region],
            edgecolor="white",
            linewidth=0.55,
            zorder=4,
        )

        for y, value, start in zip(cctld_y, values, left):
            if region != "EU" and value >= 14:
                ax.text(
                    start + value / 2,
                    y,
                    f"{value:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color=get_text_color(REGION_COLORS[region]),
                    zorder=5,
                )

        left += values


def plot_nameserver_rows(
    ax: plt.Axes,
    nameserver_rows: pd.DataFrame,
    nameserver_y: np.ndarray,
) -> None:
    nameserver_colors = {region: lighten_color(REGION_COLORS[region]) for region in REGION_ORDER}

    left = np.zeros(len(nameserver_rows))

    for region in REGION_ORDER:
        values = nameserver_rows[f"{region}_share"].to_numpy()

        ax.barh(
            nameserver_y,
            values,
            left=left,
            height=NAMESERVER_BAR_HEIGHT,
            color=nameserver_colors[region],
            edgecolor="white",
            linewidth=0.25,
            zorder=2,
        )

        left += values


def add_cctld_average_markers(
    ax: plt.Axes,
    group_spans: list[dict[str, Any]],
) -> None:
    for group in group_spans:
        ax.vlines(
            group["eu_share"],
            group["nameserver_start_y"] - 0.11,
            group["nameserver_end_y"] + 0.11,
            color="0.25",
            linewidth=0.75,
            alpha=0.80,
            zorder=6,
        )


def add_eu_share_column(
    ax: plt.Axes,
    plot_df: pd.DataFrame,
    y_positions: list[float],
) -> None:
    for y, eu_share, row_type in zip(
        y_positions,
        plot_df["eu_share"],
        plot_df["row_type"],
    ):
        ax.text(
            102.0,
            y,
            f"{eu_share:.1f}%",
            ha="left",
            va="center",
            fontsize=7,
            color="black" if row_type == "cctld" else "0.30",
            fontweight="bold" if row_type == "cctld" else "normal",
        )

    ax.text(
        102.0,
        min(y_positions) - 0.46,
        "EU share",
        ha="left",
        va="bottom",
        fontsize=7,
        fontweight="bold",
    )


def style_axes(
    ax: plt.Axes,
    plot_df: pd.DataFrame,
    y_positions: list[float],
) -> None:
    ax.set_yticks(y_positions)
    ax.set_yticklabels(plot_df["label"])

    for tick_label, row_type in zip(ax.get_yticklabels(), plot_df["row_type"]):
        if row_type == "cctld":
            tick_label.set_fontweight("bold")
            tick_label.set_fontsize(8)
            tick_label.set_color("black")
        else:
            tick_label.set_fontsize(7)
            tick_label.set_color("0.25")

    ax.set_xlabel("Share of classifiable observations (%)")
    ax.set_xlim(0, 113)
    ax.set_xticks([0, 20, 40, 60, 80, 100])

    ax.xaxis.grid(True, linestyle=":", linewidth=0.55, alpha=0.50)
    ax.set_axisbelow(True)

    ax.invert_yaxis()

    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=7)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)


def add_legend(ax: plt.Axes) -> None:
    handles, labels = ax.get_legend_handles_labels()

    average_marker = Line2D(
        [0],
        [0],
        color="0.25",
        linewidth=0.75,
        label="ccTLD EU avg.",
    )

    handles.append(average_marker)
    labels.append("ccTLD EU avg.")

    ax.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=5,
        frameon=False,
        handlelength=1.25,
        columnspacing=1.20,
        fontsize=7,
    )


def plot_cctld_target_region_composition(target_df: pd.DataFrame) -> None:
    validate_columns(target_df)

    target_df = target_df.copy()

    if "target_label" not in target_df.columns:
        target_df["target_label"] = target_df["nameserver"]

    target_df = add_region_shares(target_df)
    cctld_df = build_cctld_rows(target_df)

    plot_df, y_positions, group_spans = build_plot_rows(target_df, cctld_df)

    y_array = np.array(y_positions)

    cctld_mask = plot_df["row_type"] == "cctld"
    nameserver_mask = plot_df["row_type"] == "nameserver"

    cctld_rows = plot_df[cctld_mask]
    nameserver_rows = plot_df[nameserver_mask]

    cctld_y = y_array[cctld_mask.to_numpy()]
    nameserver_y = y_array[nameserver_mask.to_numpy()]

    fig_height = max(5.8, 0.22 * len(plot_df) + 1.7)
    fig, ax = plt.subplots(figsize=(7.8, fig_height))

    add_group_backgrounds(ax, group_spans)
    plot_cctld_aggregate_rows(ax, cctld_rows, cctld_y)
    plot_nameserver_rows(ax, nameserver_rows, nameserver_y)
    add_cctld_average_markers(ax, group_spans)
    add_eu_share_column(ax, plot_df, y_positions)
    style_axes(ax, plot_df, y_positions)
    add_legend(ax)

    save_figure("cctld_target_region_composition", fig)


def main() -> None:
    setup_style()

    target_df, _, _ = load_data()

    plot_cctld_target_region_composition(target_df)

    print("Figure written to results/figures")


if __name__ == "__main__":
    main()
