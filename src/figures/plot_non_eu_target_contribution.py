import matplotlib.pyplot as plt
import pandas as pd
from common import save_figure

TOP_COLOR = "#D95F02"
REST_COLOR = "#B0B0B0"
OTHER_COLOR = "#D9D9D9"


def plot_non_eu_target_contribution(target_df: pd.DataFrame) -> None:
    df = target_df.copy()

    total_non_eu = int(df["non_eu"].sum())
    if total_non_eu == 0:
        return

    df = df.sort_values("non_eu", ascending=False).reset_index(drop=True)

    shown_targets = 10
    shown_df = df.head(shown_targets).copy()
    remaining_df = df.iloc[shown_targets:].copy()

    shown_df["share_percent"] = shown_df["non_eu"] / total_non_eu * 100

    rows = shown_df[["target_label", "non_eu", "share_percent"]].copy()

    if not remaining_df.empty:
        other_count = int(remaining_df["non_eu"].sum())
        other_share = other_count / total_non_eu * 100

        rows = pd.concat(
            [
                rows,
                pd.DataFrame(
                    [
                        {
                            "target_label": (f"Other {len(remaining_df)} targets combined"),
                            "non_eu": other_count,
                            "share_percent": other_share,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    colors = []
    for idx, label in enumerate(rows["target_label"]):
        if label.startswith("Other "):
            colors.append(OTHER_COLOR)
        elif idx < 5:
            colors.append(TOP_COLOR)
        else:
            colors.append(REST_COLOR)

    rows = rows.iloc[::-1].reset_index(drop=True)
    colors = list(reversed(colors))

    fig, ax = plt.subplots(figsize=(3.35, 3.55))

    bars = ax.barh(
        rows["target_label"],
        rows["share_percent"],
        color=colors,
        edgecolor="none",
    )

    for bar, share, count in zip(bars, rows["share_percent"], rows["non_eu"]):
        ax.text(
            bar.get_width() + 0.35,
            bar.get_y() + bar.get_height() / 2,
            f"{share:.1f}% ({int(count)})",
            va="center",
            ha="left",
            fontsize=7,
        )

    top_5_count = int(df.head(5)["non_eu"].sum())
    top_5_share = top_5_count / total_non_eu * 100

    ax.text(
        0.98,
        0.05,
        f"Top 5: {top_5_share:.1f}% ({top_5_count}/{total_non_eu})",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
        bbox=dict(boxstyle="round,pad=0.28", facecolor="white", edgecolor="#BBBBBB"),
    )

    ax.set_xlabel("Share of all non-EU observations (%)")
    ax.set_xlim(0, max(rows["share_percent"]) * 1.32)

    ax.xaxis.grid(True, linestyle=":", linewidth=0.6, alpha=0.65)
    ax.set_axisbelow(True)

    save_figure("non_eu_target_contribution", fig)
