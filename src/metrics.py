"""Small calculations the dashboard shows as numbers or uses to filter charts.

Each function takes a DataFrame from load_data.py and returns one result.
None of them read files or draw anything.
"""
import pandas as pd


def get_latest_headline(category_inflation):
    """Return the latest All Items row (date, cpi, yoy_pct)."""
    headline = category_inflation[category_inflation["series"] == "All Items"]
    return headline.sort_values("date").iloc[-1]


def get_month_contributions(contributions, month):
    """Return one month's division contributions, smallest to largest."""
    month_data = contributions[contributions["date"] == month]
    return month_data.sort_values("contribution_pp", ascending=True)


def get_top_contributors(month_contributions, n=3):
    """Return the n largest contributions from one month's rows."""
    return month_contributions.nlargest(n, "contribution_pp")


def filter_date_range(table, start, end):
    """Keep rows whose date falls between start and end (inclusive)."""
    in_range = (table["date"] >= pd.Timestamp(start)) & (
        table["date"] <= pd.Timestamp(end)
    )
    return table[in_range]


def filter_categories(category_inflation, categories, start, end):
    """Keep the chosen CPI categories within a date range."""
    in_range = filter_date_range(category_inflation, start, end)
    return in_range[in_range["series"].isin(categories)]


def calculate_cumulative_change(category_inflation, base_date="2019-01-01"):
    """Add cumulative_pct: % change in each series' CPI since base_date."""
    baseline = category_inflation[category_inflation["date"] == base_date][
        ["series", "cpi"]
    ].rename(columns={"cpi": "cpi_base"})
    cumulative = category_inflation.merge(baseline, on="series", how="left")
    cumulative["cumulative_pct"] = (
        cumulative["cpi"] / cumulative["cpi_base"] - 1
    ) * 100
    return cumulative


def get_latest_month_rows(table):
    """Return only the rows from the latest date in the table."""
    return table[table["date"] == table["date"].max()]


def get_period_gap_drivers(drivers, period):
    """Return one half-year's category gaps, smallest to largest."""
    period_rows = drivers[drivers["period"] == period]
    return period_rows.sort_values("rate_gap_low_minus_high_pp", ascending=True)


def share_of_small_residuals(residuals, threshold=0.3):
    """Return the % of months whose absolute residual is below threshold."""
    return (residuals["residual_pp"].abs() < threshold).mean() * 100


def get_largest_residual(residuals):
    """Return the row with the largest absolute residual."""
    return residuals.loc[residuals["residual_pp"].abs().idxmax()]
