from common import load_data, setup_style
from plot_cctld_region_composition import plot_cctld_region_composition
from plot_non_eu_cctld_contribution import plot_non_eu_cctld_contribution
from plot_non_eu_target_contribution import plot_non_eu_target_contribution
from plot_probe_country_map import plot_probe_country_non_eu_map
from plot_target_region_composition import plot_target_region_composition


def main() -> None:
    setup_style()

    target_df, obs_df, probe_df = load_data()

    plot_target_region_composition(target_df)
    plot_cctld_region_composition(target_df)
    plot_non_eu_target_contribution(target_df)
    plot_non_eu_cctld_contribution(target_df)
    plot_probe_country_non_eu_map(obs_df, probe_df)

    print("Figures written to results/figures")


if __name__ == "__main__":
    main()
