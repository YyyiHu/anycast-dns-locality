import matplotlib.pyplot as plt
import numpy as np
from common import REGION_COLORS, save_figure


def plot_cctld_region_composition(target_df) -> None:
    grouped = target_df.groupby("cctld", as_index=False).agg(
        targets=("nameserver", "count"),
        main_classifiable=("main_classifiable", "sum"),
        eu=("eu", "sum"),
        uk=("uk", "sum"),
        ch=("ch", "sum"),
        other_non_eu=("other_non_eu", "sum"),
    )

    grouped["eu_percent"] = grouped["eu"] / grouped["main_classifiable"] * 100
    grouped = grouped.sort_values("eu_percent", ascending=False).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    y = np.arange(len(grouped))
    left = np.zeros(len(grouped))

    columns = {
        "EU": "eu",
        "UK": "uk",
        "CH": "ch",
        "Other non-EU": "other_non_eu",
    }

    for region, column in columns.items():
        values = grouped[column] / grouped["main_classifiable"] * 100

        ax.barh(
            y,
            values,
            left=left,
            color=REGION_COLORS[region],
            label=region,
            edgecolor="white",
            linewidth=0.5,
        )

        for i, value in enumerate(values):
            if value >= 8:
                ax.text(
                    left[i] + value / 2,
                    i,
                    f"{value:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if region != "EU" else "black",
                )

        left += values

    labels = [f"{row['cctld']}  ({int(row['targets'])} targets)" for _, row in grouped.iterrows()]

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 110)
    ax.set_xlabel("Share of classifiable observations (%)")
    ax.invert_yaxis()

    for i, row in grouped.iterrows():
        ax.text(
            101.2,
            i,
            f"EU {row['eu_percent']:.1f}%",
            va="center",
            fontsize=7,
        )

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.13),
        ncol=4,
        frameon=False,
    )

    fig.subplots_adjust(left=0.20, right=0.88, top=0.82, bottom=0.17)
    save_figure("cctld_region_composition", fig)
