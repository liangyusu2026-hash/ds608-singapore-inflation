"""Build the dashboard's Plotly charts.

Each create_* function draws one chart from a DataFrame and returns the
figure. The functions do not filter data or call Streamlit, so the same
charts can be shown in the app or saved to outputs/figures/.
"""
import plotly.express as px

MEASURE_LABELS = {
    "cpi": "CPI Index (2024 = 100)",
    "yoy_pct": "Year-on-Year Inflation (%)",
}

TRANSPORT_SERIES_NAMES = {
    "transport_cpi_index": "Private Transport CPI",
    "coe_premium_index": "COE Premiums (Categories A & B)",
}

RENT_SERIES_NAMES = {
    "accommodation_cpi_index": "Accommodation CPI",
    "hdb_rent_index": "HDB Median Rents",
}


def create_category_trend_chart(category_data, measure, title):
    """Line chart of a CPI measure over time, one line per category."""
    fig = px.line(
        data_frame=category_data,
        x="date",
        y=measure,
        color="series",
        title=title,
        labels={
            "date": "Date",
            "series": "Expenditure Category",
            "cpi": MEASURE_LABELS["cpi"],
            "yoy_pct": MEASURE_LABELS["yoy_pct"],
        },
    )
    if measure == "yoy_pct":
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
    return fig


def create_contribution_bar_chart(month_contributions, month_label):
    """Horizontal bar chart of each division's contribution in one month."""
    return px.bar(
        month_contributions,
        x="contribution_pp",
        y="series",
        orientation="h",
        title=f"Inflation Contributions — {month_label}",
        labels={
            "contribution_pp": "Contribution (percentage points)",
            "series": "Expenditure Category",
        },
    )


def create_stacked_contribution_chart(contributions):
    """Stacked bar chart of monthly contributions by division over time."""
    fig = px.bar(
        contributions,
        x="date",
        y="contribution_pp",
        color="series",
        barmode="relative",
        title="Monthly Inflation Contributions by Category",
        labels={
            "date": "Month",
            "contribution_pp": "Contribution (percentage points)",
            "series": "Expenditure Category",
        },
    )
    fig.update_layout(
        height=550,
        xaxis_tickformat="%b %Y",
        legend_title_text="Expenditure Category",
    )
    fig.add_hline(y=0, line_color="gray", line_width=1)
    return fig


def create_income_group_line_chart(income_gaps, income_groups):
    """Line chart of half-yearly inflation for the chosen income groups."""
    return px.line(
        income_gaps,
        x="period",
        y=income_groups,
        markers=True,
        title="Inflation Rates by Household Income Group",
        labels={
            "period": "Half-Year Period",
            "value": "Inflation Rate (%)",
            "variable": "Income Group",
        },
    )


def create_income_gap_bar_chart(income_gaps):
    """Bar chart of the lowest-minus-highest income inflation gap."""
    fig = px.bar(
        income_gaps,
        x="period",
        y="gap_low_minus_high_pp",
        title="Inflation Gap: Lowest 20% Minus Highest 20%",
        labels={
            "period": "Half-Year Period",
            "gap_low_minus_high_pp": "Inflation Gap (percentage points)",
        },
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    return fig


def create_category_gap_bar_chart(period_drivers, period):
    """Horizontal bar chart of category inflation gaps in one half-year."""
    fig = px.bar(
        period_drivers,
        x="rate_gap_low_minus_high_pp",
        y="series",
        orientation="h",
        title=f"Category Inflation Differences — {period}",
        labels={
            "rate_gap_low_minus_high_pp": "Lowest 20% minus Highest 20% (pp)",
            "series": "Expenditure Category",
        },
    )
    fig.add_vline(x=0, line_dash="dash", line_color="gray")
    return fig


def create_cumulative_change_chart(latest_cumulative):
    """Horizontal bar chart of each category's cumulative price change."""
    return px.bar(
        latest_cumulative.sort_values("cumulative_pct", ascending=True),
        x="cumulative_pct",
        y="series",
        orientation="h",
        title="Cumulative Price Changes Since January 2019",
        labels={
            "cumulative_pct": "Cumulative Price Change (%)",
            "series": "Expenditure Category",
        },
    )


def create_indexed_comparison_chart(table, columns, series_names, title):
    """Line chart of indexed series (Feb 2021 = 100) with readable names."""
    fig = px.line(
        table,
        x="date",
        y=columns,
        title=title,
        labels={
            "date": "Date",
            "value": "Index (February 2021 = 100)",
            "variable": "Series",
        },
    )
    fig.for_each_trace(
        lambda trace: trace.update(name=series_names.get(trace.name, trace.name))
    )
    return fig


def create_transport_coe_chart(transport_coe):
    """Line chart of Private Transport CPI against COE premiums."""
    return create_indexed_comparison_chart(
        transport_coe,
        list(TRANSPORT_SERIES_NAMES),
        TRANSPORT_SERIES_NAMES,
        "Private Transport CPI vs COE Premiums",
    )


def create_accommodation_rent_chart(accommodation_rent):
    """Line chart of Accommodation CPI against HDB median rents."""
    return create_indexed_comparison_chart(
        accommodation_rent,
        list(RENT_SERIES_NAMES),
        RENT_SERIES_NAMES,
        "Accommodation CPI vs HDB Rents",
    )


def show_selected_traces(fig, selected_names):
    """Hide every line in the figure whose name is not in selected_names."""
    fig.for_each_trace(
        lambda trace: trace.update(visible=trace.name in selected_names)
    )
    return fig
