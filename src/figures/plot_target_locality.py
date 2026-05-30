import matplotlib.pyplot as plt
import numpy as np
from common import LOCALITY_COLORS, REGION_COLORS, locality_tier, save_figure


def plot_target_eu_locality_ranked(target_df) -> None:
    df = target_df.sort_values("eu_percent", ascending=False).reset_index(drop=True)
    df["tier"] = df["eu_percent"].apply(locality_tier)

    fig, ax = plt.subplots(figsize=(7.4, 5.4))

    ax.axvspan(0, 70, color="#F8F1EA", zorder=0)
    ax.axvspan(70, 90, color="#FFF6E3", zorder=0)
    ax.axvspan(90, 100, color="#EEF5FB", zorder=0)

    y = np.arange(len(df))

    ax.hlines(
        y=y,
        xmin=0,
        xmax=df["eu_percent"],
        color="#C8C8C8",
        linewidth=1.0,
        zorder=1,
    )

    for tier in ["High EU locality", "Mixed locality", "Low EU locality"]:
        tier_df = df[df["tier"] == tier]
        ax.scatter(
            tier_df["eu_percent"],
            tier_df.index,
            s=38,
            color=LOCALITY_COLORS[tier],
            label=tier,
            zorder=3,
        )

    ax.axvline(70, color="#777777", linestyle=":", linewidth=0.8)
    ax.axvline(90, color="#777777", linestyle=":", linewidth=0.8)

    ax.set_yticks(y)
    ax.set_yticklabels(df["target_label"])
    ax.set_xlim(0, 104)
    ax.set_xlabel("EU locality share among classifiable observations (%)")
    ax.invert_yaxis()

    for pos, row in df.iterrows():
        ax.text(
            row["eu_percent"] + 0.9,
            pos,
            f"{row['eu_percent']:.1f}%",
            va="center",
            fontsize=7,
        )

    ax.text(35, -0.65, "low", ha="center", va="bottom", fontsize=7, color="#555555")
    ax.text(80, -0.65, "mixed", ha="center", va="bottom", fontsize=7, color="#555555")
    ax.text(95, -0.65, "high", ha="center", va="bottom", fontsize=7, color="#555555")

    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.45)

    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=3,
        frameon=False,
    )

    fig.subplots_adjust(left=0.26, right=0.96, top=0.98, bottom=0.14)
    save_figure("target_eu_locality_ranked", fig)


def plot_target_region_composition(target_df) -> None:
    df = target_df.sort_values("eu_percent", ascending=False).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(7.8, 5.9))
    y = np.arange(len(df))
    left = np.zeros(len(df))

    columns = {
        "EU": "eu",
        "UK": "uk",
        "CH": "ch",
        "Other non-EU": "other_non_eu",
    }

    for region, column in columns.items():
        values = df[column] / df["main_classifiable"] * 100

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
            if value >= 10:
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

    ax.set_yticks(y)
    ax.set_yticklabels(df["target_label"])
    ax.set_xlim(0, 110)
    ax.set_xlabel("Share of classifiable observations (%)")
    ax.invert_yaxis()

    for i, row in df.iterrows():
        ax.text(
            101.2,
            i,
            f"EU {row['eu_percent']:.1f}%",
            va="center",
            fontsize=7,
        )

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.045),
        ncol=4,
        frameon=False,
    )

    fig.subplots_adjust(left=0.25, right=0.91, top=0.90, bottom=0.10)
    save_figure("target_region_composition", fig)
