import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common import save_figure


def plot_non_eu_concentration(target_df) -> None:
    df = target_df.sort_values("non_eu", ascending=False).reset_index(drop=True)
    df["target_label"] = df["nameserver"] + " (" + df["cctld"] + ")"

    total_non_eu = int(df["non_eu"].sum())
    top_five_total = int(df.head(5)["non_eu"].sum())
    top_five_percent = top_five_total / total_non_eu * 100

    top_n = 10
    top_df = df.head(top_n).copy()
    remaining = df.iloc[top_n:].copy()

    if not remaining.empty:
        remaining_row = pd.DataFrame(
            [
                {
                    "target_label": f"Other {len(remaining)} targets combined",
                    "non_eu": remaining["non_eu"].sum(),
                }
            ]
        )
        plot_df = pd.concat(
            [top_df[["target_label", "non_eu"]], remaining_row],
            ignore_index=True,
        )
    else:
        plot_df = top_df[["target_label", "non_eu"]].copy()

    fig, ax = plt.subplots(figsize=(7.4, 4.1))

    y = np.arange(len(plot_df))
    colors = []

    for i, row in plot_df.iterrows():
        if i < 5:
            colors.append("#D95F02")
        elif str(row["target_label"]).startswith("Other"):
            colors.append("#DDDDDD")
        else:
            colors.append("#B9B9B9")

    ax.barh(
        y,
        plot_df["non_eu"],
        color=colors,
        edgecolor="white",
        linewidth=0.5,
    )

    ax.set_yticks(y)
    ax.set_yticklabels(plot_df["target_label"])
    ax.set_xlabel("Non-EU observations")
    ax.invert_yaxis()
    ax.grid(axis="x", linestyle=":", linewidth=0.6, alpha=0.5)

    for i, value in enumerate(plot_df["non_eu"]):
        ax.text(
            value + 0.7,
            i,
            f"{int(value)}",
            va="center",
            fontsize=7,
        )

    callout = (
        f"Top 5 targets: {top_five_total} of {total_non_eu} "
        f"non-EU observations ({top_five_percent:.1f}%)"
    )

    ax.text(
        0.98,
        0.08,
        callout,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        bbox={
            "boxstyle": "round,pad=0.35",
            "facecolor": "white",
            "edgecolor": "#C7C7C7",
        },
    )

    fig.subplots_adjust(left=0.28, right=0.96, top=0.98, bottom=0.14)
    save_figure("non_eu_concentration", fig)
