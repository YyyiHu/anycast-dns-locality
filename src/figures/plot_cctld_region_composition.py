import matplotlib.pyplot as plt
import pandas as pd
from common import REGION_COLORS, REGION_ORDER, save_figure

REGION_COLUMNS = {
    "EU": "eu",
    "UK": "uk",
    "CH": "ch",
    "Other non-EU": "other_non_eu",
}


def plot_cctld_region_composition(target_df: pd.DataFrame) -> None:
    df = target_df.copy()

    grouped = (
        df.groupby("cctld", as_index=False)
        .agg(
            targets=("nameserver", "count"),
            main_classifiable=("main_classifiable", "sum"),
            eu=("eu", "sum"),
            uk=("uk", "sum"),
            ch=("ch", "sum"),
            other_non_eu=("other_non_eu", "sum"),
        )
        .rename(columns={value: label for label, value in REGION_COLUMNS.items()})
    )

    grouped["eu_share"] = grouped["EU"] / grouped["main_classifiable"] * 100
    grouped = grouped.sort_values("eu_share", ascending=True).reset_index(drop=True)

    total_row = pd.DataFrame(
        [
            {
                "cctld": "Total",
                "targets": int(grouped["targets"].sum()),
                "main_classifiable": int(grouped["main_classifiable"].sum()),
                "EU": int(grouped["EU"].sum()),
                "UK": int(grouped["UK"].sum()),
                "CH": int(grouped["CH"].sum()),
                "Other non-EU": int(grouped["Other non-EU"].sum()),
            }
        ]
    )
    total_row["eu_share"] = total_row["EU"] / total_row["main_classifiable"] * 100

    plot_df = pd.concat([total_row, grouped], ignore_index=True)

    for region in REGION_ORDER:
        plot_df[f"{region}_share"] = plot_df[region] / plot_df["main_classifiable"] * 100

    labels = []
    for _, row in plot_df.iterrows():
        if row["cctld"] == "Total":
            labels.append(f"Total ({int(row['targets'])} targets)")
        else:
            labels.append(f"{row['cctld']} ({int(row['targets'])} targets)")

    fig, ax = plt.subplots(figsize=(3.35, 2.9))

    y_positions = range(len(plot_df))
    left = [0.0] * len(plot_df)

    for region in REGION_ORDER:
        values = plot_df[f"{region}_share"].tolist()

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
            if value >= 8:
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

    for y, eu_share in zip(y_positions, plot_df["eu_share"]):
        ax.text(
            101.3,
            y,
            f"EU {eu_share:.1f}%",
            ha="left",
            va="center",
            fontsize=7,
        )

    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Share of classifiable observations (%)")
    ax.set_xlim(0, 116)

    ax.xaxis.grid(True, linestyle=":", linewidth=0.6, alpha=0.65)
    ax.set_axisbelow(True)

    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=4,
        frameon=False,
        handlelength=1.1,
    )

    save_figure("cctld_region_composition", fig)
