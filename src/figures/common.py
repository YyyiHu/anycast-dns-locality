from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

ATLAS_DIR = ROOT / "data" / "processed" / "atlas_locality"
INPUT_DIR = ROOT / "data" / "input"
OUTPUT_DIR = ROOT / "results" / "figures"

TARGET_SUMMARY_FILE = ATLAS_DIR / "target_locality_summary.tsv"
OBSERVATIONS_FILE = ATLAS_DIR / "dns_observations_classified.tsv"
PROBE_PANEL_FILE = INPUT_DIR / "eu_probe_panel.tsv"

MAP_FILE = INPUT_DIR / "maps" / "ne_50m_admin_0_countries" / "ne_50m_admin_0_countries.shp"

REGION_ORDER = ["EU", "UK", "CH", "Other non-EU"]

REGION_COLORS = {
    "EU": "#2F6DAE",
    "UK": "#F2A35E",
    "CH": "#D96B4C",
    "Other non-EU": "#7D8790",
}

MAP_BINS = [0, 10, 20, 30, 40, 100]
MAP_COLORS = ["#FFF5EB", "#FDD0A2", "#FDAE6B", "#F16913", "#A63603"]
MAP_LABELS = ["0 to 10%", "10 to 20%", "20 to 30%", "30 to 40%", "40%+"]


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "savefig.facecolor": "white",
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif", "Times"],
            "font.size": 8,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def save_figure(name: str, fig=None) -> None:
    if fig is None:
        fig = plt.gcf()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_DIR / f"{name}.pdf", bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


def normalize_region(value: object) -> str:
    if pd.isna(value):
        return "Unknown"

    text = str(value).strip()

    if text == "Other non EU":
        return "Other non-EU"

    return text


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    target_df = pd.read_csv(TARGET_SUMMARY_FILE, sep="\t")
    obs_df = pd.read_csv(OBSERVATIONS_FILE, sep="\t")
    probe_df = pd.read_csv(PROBE_PANEL_FILE, sep="\t")

    if "eu_fraction" not in target_df.columns:
        target_df["eu_fraction"] = target_df["eu"] / target_df["main_classifiable"]

    if "non_eu" not in target_df.columns:
        target_df["non_eu"] = target_df["uk"] + target_df["ch"] + target_df["other_non_eu"]

    target_df["target_label"] = target_df["nameserver"] + " (" + target_df["cctld"] + ")"
    target_df["eu_percent"] = target_df["eu_fraction"] * 100

    obs_df["probe_id"] = obs_df["probe_id"].astype(int)
    probe_df["probe_id"] = probe_df["probe_id"].astype(int)

    obs_df = obs_df.merge(
        probe_df[["probe_id", "country", "asn_v4", "is_anchor"]],
        on="probe_id",
        how="left",
    )

    obs_df["region_clean"] = obs_df["region_class"].apply(normalize_region)

    return target_df, obs_df, probe_df


def main_classifiable_observations(obs_df: pd.DataFrame) -> pd.DataFrame:
    return obs_df[
        (obs_df["classification_status"] == "classified")
        & (obs_df["classification_confidence"].isin(["high", "medium"]))
    ].copy()
