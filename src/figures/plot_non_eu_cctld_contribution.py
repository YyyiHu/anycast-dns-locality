import matplotlib.pyplot as plt
import pandas as pd
from common import REGION_COLORS, save_figure

REGION_COLUMNS = {
    "UK": "uk",
    "CH": "ch",
    "Other non-EU": "other_non_eu",
}


def plot_non_eu_cctld_contribution(target_df: pd.DataFrame) -> None:
    df = target_df.copy()

    grouped = (
        df.groupby("cctld", as_index=False)[list(REGION_COLUMNS.values())]
        .sum()
        .rename(columns={value: label for label, value in REGION_COLUMNS.items()})
    )

    grouped["non_eu_total"] = grouped[list(REGION_COLUMNS.keys())].sum(axis=1)
    total_non_eu = int(grouped["non_eu_total"].sum())

    if total_non_eu == 0:
        return

    for region in REGION_COLUMNS:
        grouped[f"{region}_share"] = grouped[region] / total_non_eu * 100

    grouped["total_share"] = grouped["non_eu_total"] / total_non_eu * 100
    grouped = grouped.sort_values("total_share", ascending=True).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(3.35, 2.55))

    y_positions = range(len(grouped))
    left = [0.0] * len(grouped)

    for region in REGION_COLUMNS:
        values = grouped[f"{region}_share"].tolist()

        ax.barh(
            y_positions,
            values,
            left=left,
            label=region,
            color=REGION_COLORS[region],
            edgecolor="white",
            linewidth=0.6,
        )

        for y, value, start, count in zip(
            y_positions,
            values,
            left,
            grouped[region],
        ):
            if value >= 4:
                ax.text(
                    start + value / 2,
                    y,
                    str(int(count)),
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white",
                )

        left = [start + value for start, value in zip(left, values)]

    for y, share, count in zip(
        y_positions,
        grouped["total_share"],
        grouped["non_eu_total"],
    ):
        ax.text(
            share + 0.7,
            y,
            f"{share:.1f}% ({int(count)})",
            ha="left",
            va="center",
            fontsize=7,
        )

    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(grouped["cctld"])
    ax.set_xlabel("Share of all non-EU observations (%)")
    ax.set_xlim(0, max(grouped["total_share"]) + 8)

    ax.xaxis.grid(True, linestyle=":", linewidth=0.6, alpha=0.65)
    ax.set_axisbelow(True)

    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=3,
        frameon=False,
        handlelength=1.2,
    )

    save_figure("non_eu_cctld_contribution", fig)
