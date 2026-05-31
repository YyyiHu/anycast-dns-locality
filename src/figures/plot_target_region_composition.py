import matplotlib.pyplot as plt
import pandas as pd
from common import REGION_COLORS, REGION_ORDER, save_figure

REGION_COLUMNS = {
    "EU": "eu",
    "UK": "uk",
    "CH": "ch",
    "Other non-EU": "other_non_eu",
}


def plot_target_region_composition(target_df: pd.DataFrame) -> None:
    df = target_df.copy()

    for region, column in REGION_COLUMNS.items():
        df[f"{region}_share"] = df[column] / df["main_classifiable"] * 100

    df["eu_share"] = df["eu"] / df["main_classifiable"] * 100
    df = df.sort_values("eu_share", ascending=True).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(6.8, 5.1))

    y_positions = range(len(df))
    left = [0.0] * len(df)

    for region in REGION_ORDER:
        values = df[f"{region}_share"].tolist()

        ax.barh(
            y_positions,
            values,
            left=left,
            label=region,
            color=REGION_COLORS[region],
            edgecolor="white",
            linewidth=0.6,
        )

        for y, value, start in zip(y_positions, values, left):
            if value >= 16:
                text_color = "black" if region == "EU" else "white"
                ax.text(
                    start + value / 2,
                    y,
                    f"{value:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color=text_color,
                )

        left = [start + value for start, value in zip(left, values)]

    for y, eu_share in zip(y_positions, df["eu_share"]):
        ax.text(
            101.0,
            y,
            f"EU {eu_share:.1f}%",
            ha="left",
            va="center",
            fontsize=7,
        )

    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(df["target_label"])
    ax.set_xlabel("Share of classifiable observations (%)")
    ax.set_xlim(0, 116)

    ax.xaxis.grid(True, linestyle=":", linewidth=0.6, alpha=0.65)
    ax.set_axisbelow(True)

    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=4,
        frameon=False,
        handlelength=1.3,
    )

    save_figure("target_region_composition", fig)
