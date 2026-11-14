"""Save the dashboard's main charts as PNG files in outputs/figures/.

Uses the same chart functions as the Streamlit app (src/plots.py), so the
saved images match what the dashboard shows in its default view.
Run from the project folder with: python -m src.save_figures
"""
from pathlib import Path

from src import load_data, metrics, plots

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "outputs" / "figures"


def save_figure(fig, file_name):
    """Write one Plotly figure to outputs/figures/ as a PNG."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.write_image(FIGURES / file_name, width=1000, height=550, scale=2)
    print(f"Saved outputs/figures/{file_name}")


def build_headline_figure(category_inflation):
    """Headline YoY inflation since 2019."""
    headline = metrics.filter_categories(
        category_inflation,
        ["All Items"],
        category_inflation["date"].min(),
        category_inflation["date"].max(),
    )
    return plots.create_category_trend_chart(
        headline, "yoy_pct", "Singapore Headline Year-on-Year Inflation (%)"
    )


def build_surge_figure(contributions):
    """Stacked monthly contributions during the 2022-23 surge."""
    surge = metrics.filter_date_range(contributions, "2022-01-01", "2023-12-01")
    return plots.create_stacked_contribution_chart(surge)


def build_cumulative_figure(category_inflation):
    """Cumulative price change by category since January 2019."""
    cumulative = metrics.calculate_cumulative_change(category_inflation)
    return plots.create_cumulative_change_chart(
        metrics.get_latest_month_rows(cumulative)
    )


def main():
    """Build and save every figure used in the README."""
    category_inflation = load_data.load_category_inflation()
    contributions = load_data.load_contributions()
    income_gaps = load_data.load_income_group_gaps()

    save_figure(build_headline_figure(category_inflation), "headline_inflation.png")
    save_figure(build_surge_figure(contributions), "contributions_2022_2023.png")
    save_figure(build_cumulative_figure(category_inflation), "cumulative_change_since_2019.png")
    save_figure(
        plots.create_income_group_line_chart(
            income_gaps, ["Lowest 20%", "Middle 60%", "Highest 20%"]
        ),
        "income_group_inflation.png",
    )
    save_figure(plots.create_income_gap_bar_chart(income_gaps), "income_gap_low_minus_high.png")
    save_figure(
        plots.create_transport_coe_chart(load_data.load_transport_vs_coe()),
        "private_transport_vs_coe.png",
    )


if __name__ == "__main__":
    main()
