"""Streamlit dashboard: Who Feels Inflation Most?

This file only lays out the page. Data loading is in src/load_data.py,
calculations are in src/metrics.py and charts are in src/plots.py.
Run with: streamlit run app.py
"""
import pandas as pd
import streamlit as st

from src import load_data, metrics, plots

INCOME_GROUPS = ["Lowest 20%", "Middle 60%", "Highest 20%"]


def show_top_contributors(top_rows):
    """Write each top contributor and its contribution in pp."""
    for _, row in top_rows.iterrows():
        st.write(
            f"**{row['series']}**: "
            f"{row['contribution_pp']:.2f} percentage points"
        )


def render_headline_metrics(category_inflation):
    """Show the latest headline YoY inflation and CPI index."""
    latest = metrics.get_latest_headline(category_inflation)
    st.subheader(f"Latest Headline Inflation — {latest['date']:%B %Y}")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Year-on-Year Inflation", f"{latest['yoy_pct']:.2f}%")
    with col2:
        st.metric(plots.MEASURE_LABELS["cpi"], f"{latest['cpi']:.2f}")


def render_latest_top_contributors(contributions):
    """Show the three largest contributors in the latest month."""
    latest_month = contributions["date"].max()
    month_data = metrics.get_month_contributions(contributions, latest_month)
    st.markdown(
        f"#### Top Three Inflation Contributors — {latest_month:%B %Y}"
    )
    show_top_contributors(metrics.get_top_contributors(month_data))


def render_category_explorer(category_inflation):
    """Let users pick categories, a measure and dates, then draw the trend."""
    view = st.radio(
        "Choose a dashboard view",
        ["Overall trend", "Compare categories"],
    )
    if view == "Overall trend":
        categories = ["All Items"]
    else:
        categories = st.multiselect(
            "Choose CPI categories",
            category_inflation["series"].unique(),
            default=["Food", "Transport"],
        )

    measure = st.selectbox(
        "Choose a measure",
        ["cpi", "yoy_pct"],
        format_func=lambda x: plots.MEASURE_LABELS[x],
    )
    start_date = st.date_input(
        "Start date", value=category_inflation["date"].min().date()
    )
    end_date = st.date_input(
        "End date", value=category_inflation["date"].max().date()
    )

    if start_date > end_date:
        st.error("Starting date cannot be later than ending date.")
        return
    if len(categories) == 0:
        st.warning("Please select at least one CPI category.")
        return

    if view == "Overall trend":
        title = f"Singapore Overall {plots.MEASURE_LABELS[measure]}"
    else:
        title = f"Singapore {plots.MEASURE_LABELS[measure]} by Category"
    selected = metrics.filter_categories(
        category_inflation, categories, start_date, end_date
    )
    fig = plots.create_category_trend_chart(selected, measure, title)
    st.plotly_chart(fig, use_container_width=True)


def render_overview_tab(category_inflation, contributions):
    """Tab 1: headline numbers, latest top contributors, category explorer."""
    st.info(
        "Headline year-on-year inflation was 2.35% in August 2026, "
        "with Transport, Food, and Housing & Utilities "
        "the top contributing categories."
    )
    render_headline_metrics(category_inflation)
    render_latest_top_contributors(contributions)
    render_category_explorer(category_inflation)


def render_single_month_contributions(contributions):
    """Let users pick a month and show that month's contributions."""
    months = sorted(contributions["date"].unique())
    selected_month = st.selectbox(
        "Choose a month to examine",
        months,
        index=months.index(pd.Timestamp("2022-09-01")),
        format_func=lambda x: pd.Timestamp(x).strftime("%B %Y"),
    )
    selected_month = pd.Timestamp(selected_month)
    if selected_month.year == 2024:
        st.warning(
            "2024 contribution estimates use approximate transitional weights. "
            "Interpret these results with additional caution."
        )

    month_data = metrics.get_month_contributions(contributions, selected_month)
    st.markdown("#### Top Three Inflation Contributors")
    show_top_contributors(metrics.get_top_contributors(month_data))

    fig = plots.create_contribution_bar_chart(
        month_data, selected_month.strftime("%B %Y")
    )
    st.plotly_chart(fig, use_container_width=True)


def render_contributions_over_time(contributions):
    """Let users pick a date range and show stacked monthly contributions."""
    st.subheader("Inflation Contributions Over Time")
    available_months = sorted(contributions["date"].dt.date.unique())
    range_start, range_end = st.select_slider(
        "Choose a date range",
        options=available_months,
        value=(
            pd.Timestamp("2022-01-01").date(),
            pd.Timestamp("2023-12-01").date(),
        ),
        format_func=lambda d: d.strftime("%b %Y"),
    )
    if range_start.year <= 2024 <= range_end.year:
        st.warning(
            "The selected period includes 2024, when approximate "
            "transitional CPI expenditure weights were used. "
            "Interpret contribution estimates with additional caution."
        )

    in_range = metrics.filter_date_range(contributions, range_start, range_end)
    fig = plots.create_stacked_contribution_chart(in_range)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Positive contributions increase headline inflation, "
        "while negative contributions offset it. "
        "The expenditure-weight regime changes around 2024; "
        "contributions across regimes require caution."
    )
    st.caption(
        "Inflation contributions are estimated using CPI expenditure weights. "
        "The expenditure basket was updated around 2024, so contribution "
        "magnitudes across different weighting periods are not directly comparable."
    )


def render_contributions_tab(contributions):
    """Tab 2: what drove inflation, for one month and over time."""
    st.subheader("What Drove Inflation?")
    st.info(
        "Transport, Food, and Housing & Utilities ranked highest "
        "in the 2022–23 surge, while Housing & Utilities, Food, "
        "and Transport ranked highest in the 2024–26 cooling."
    )
    render_single_month_contributions(contributions)
    render_contributions_over_time(contributions)


def render_cumulative_tab(category_inflation):
    """Tab 3: cumulative price change of each category since January 2019."""
    st.info(
        "Since January 2019, Transport (51.7%), Food (23.1%), "
        "and Housing & Utilities (18.2%) had the largest category "
        "CPI increases through August 2026."
    )
    st.subheader("How Much Have Prices Increased Since 2019?")
    cumulative = metrics.calculate_cumulative_change(category_inflation)
    latest = metrics.get_latest_month_rows(cumulative)
    st.plotly_chart(
        plots.create_cumulative_change_chart(latest), use_container_width=True
    )
    st.caption(
        f"Percentage changes from January 2019 to "
        f"{latest['date'].max():%B %Y}, "
        "calculated using CPI indices (2024 = 100)."
    )


def render_income_group_rates(income_gaps):
    """Let users pick income groups and show their inflation rates."""
    income_groups = st.multiselect(
        "Select household income groups",
        INCOME_GROUPS,
        default=INCOME_GROUPS,
    )
    if not income_groups:
        st.warning("Please select at least one income group.")
        return
    fig = plots.create_income_group_line_chart(income_gaps, income_groups)
    st.plotly_chart(fig, use_container_width=True)


def render_income_gap(income_gaps):
    """Show the lowest-minus-highest income inflation gap."""
    st.subheader("Inflation Gap Between Income Groups")
    st.plotly_chart(
        plots.create_income_gap_bar_chart(income_gaps), use_container_width=True
    )


def render_category_gaps(drivers):
    """Let users pick a half-year and show category inflation gaps."""
    st.subheader("Which Categories Show the Largest Income-Group Differences?")
    periods = drivers["period"].unique().tolist()
    selected_period = st.selectbox(
        "Choose a half-year period",
        periods,
        index=periods.index("2022 2H"),
    )
    period_drivers = metrics.get_period_gap_drivers(drivers, selected_period)
    fig = plots.create_category_gap_bar_chart(period_drivers, selected_period)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Bars show differences in category inflation rates, "
        "not contributions to the overall household inflation gap."
    )


def render_income_tab(income_gaps, drivers):
    """Tab 4: inflation by household income group."""
    st.subheader("Rich vs Poor: Inflation by Income Group")
    st.info(
        "In 2026 1H, the lowest-minus-highest income inflation gap "
        "was -0.43 pp. Education and Health had the largest negative "
        "category gaps, while Transport had the largest positive gap."
    )
    render_income_group_rates(income_gaps)
    render_income_gap(income_gaps)
    render_category_gaps(drivers)


def render_comparison_chart(fig, label, series_names):
    """Let users choose which lines of a comparison chart to show."""
    options = list(series_names.values())
    selected = st.multiselect(label, options, default=options)
    plots.show_selected_traces(fig, selected)
    st.plotly_chart(fig, use_container_width=True)


def render_behind_numbers_tab(transport_coe, accommodation_rent):
    """Tab 5: CPI groups compared with COE premiums and HDB rents."""
    st.subheader("Behind the Numbers: COE Premiums and HDB Rents")
    st.info(
        "Since February 2021, the Private Transport CPI and COE "
        "premium indexes both rose, reaching 150.0 and 292.0, "
        "respectively, in August 2026."
    )
    render_comparison_chart(
        plots.create_transport_coe_chart(transport_coe),
        "Choose Transport comparison series",
        plots.TRANSPORT_SERIES_NAMES,
    )
    render_comparison_chart(
        plots.create_accommodation_rent_chart(accommodation_rent),
        "Choose Housing comparison series",
        plots.RENT_SERIES_NAMES,
    )
    st.caption(
        "All series are rebased to February 2021 = 100. "
        "These comparisons are descriptive and do not establish causation."
    )


def render_methodology_text():
    """Write the data sources, definitions, limitations and linking notes."""
    st.markdown("""
    ### Data Sources
    - Singapore Department of Statistics (SingStat):
      Consumer Price Index and household income-group CPI.
    - COE premium and HDB rental series:
      Processed from the project team's compiled datasets.

    ### Important Definitions
    - **CPI Index:** Official index with 2024 = 100.
    - **Year-on-Year Inflation:** Percentage change compared
      with the corresponding month one year earlier.
    - **Inflation Contributions:** Estimated percentage-point
      contributions of expenditure categories to headline inflation.
    - **Cumulative Price Change:** Percentage change relative
      to January 2019.
    - **Household Income Inflation:** Calculated using
      semi-annual observations.
    - **COE and HDB Comparisons:** Series rebased to
      February 2021 = 100 for visual comparison.

    ### Limitations
    - CPI expenditure weights changed around 2024.
      Contribution magnitudes across different weight regimes
      are not directly comparable.
    - The 2024 contribution estimates use approximate
      transitional weights.
    - Category-specific inflation gaps do not directly measure
      contributions to overall household inflation differences.
    - COE premiums and HDB rents are descriptive comparisons;
      their co-movement does not establish causation.
    """)
    st.markdown("""
    ### CPI Series Linking

    The official CPI series obtained through data.gov.sg
    already contains historically linked observations.
    Therefore, our team did not perform additional
    base-year linking.

    ### Contribution Residual Check

    The residual measures the difference between headline
    year-on-year inflation and the sum of estimated
    expenditure-category contributions.

    **Residual = Headline inflation - Sum of contributions**
    """)


def render_residual_summary(residuals):
    """Show how close the summed contributions are to headline inflation."""
    largest = metrics.get_largest_residual(residuals)
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Months with |Residual| < 0.3 pp",
            f"{metrics.share_of_small_residuals(residuals):.1f}%",
        )
    with col2:
        st.metric(
            "Largest Absolute Residual",
            f"{abs(largest['residual_pp']):.2f} pp",
        )
    st.caption(
        "Largest residual occurred in "
        f"{largest['date']:%B %Y}. "
        "Residuals measure the accuracy of the approximate "
        "contribution decomposition, not errors in CPI linking."
    )


def render_methodology_section(residuals):
    """Expander with methodology notes and the residual check."""
    with st.expander("Data Sources and Methodology"):
        render_methodology_text()
        render_residual_summary(residuals)


def main():
    """Load the tables and lay out the five dashboard tabs."""
    category_inflation = load_data.load_category_inflation()
    contributions = load_data.load_contributions()

    st.title("Singapore CPI Dashboard")
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview & Category Explorer",
        "What Drove Inflation?",
        "Cumulative Price Changes",
        "Rich vs Poor",
        "Behind the Numbers",
    ])
    with tab1:
        render_overview_tab(category_inflation, contributions)
    with tab2:
        render_contributions_tab(contributions)
    with tab3:
        render_cumulative_tab(category_inflation)
    with tab4:
        render_income_tab(
            load_data.load_income_group_gaps(),
            load_data.load_income_gap_drivers(),
        )
    with tab5:
        render_behind_numbers_tab(
            load_data.load_transport_vs_coe(),
            load_data.load_accommodation_vs_rent(),
        )
    render_methodology_section(load_data.load_residual_check())


main()
