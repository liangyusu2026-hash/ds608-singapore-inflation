import pandas as pd
import plotly.express as px
import streamlit as st

# Load the processed data
df = pd.read_csv("outputs/tables/inflation_by_category.csv")

#____________________________________________________________
# Dashboard Section: Category Explorer

# Convert the "date" column to datetime format for proper plotting
df["date"] = pd.to_datetime(df["date"])

# Retrieve Singapore's headline CPI observations
headline = df[df["series"] == "All Items"]

# Find the latest available headline CPI observation
latest_headline = headline.sort_values("date").iloc[-1]

# Extract the latest inflation rate and CPI index
latest_inflation = latest_headline["yoy_pct"]
latest_cpi = latest_headline["cpi"]
latest_month = latest_headline["date"].strftime("%B %Y")

# Define a dictionary to map measure names to more
#  reader-friendly labels
measure_labels = {
    "cpi": "CPI Index (2024 = 100)",
    "yoy_pct": "Year-on-Year Inflation (%)"
}

# Display a dashboard title
st.title("Singapore CPI Dashboard")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview & Category Explorer",
    "What Drove Inflation?",
    "Cumulative Price Changes",
    "Rich vs Poor",
    "Behind the Numbers"
])
with tab1:

    # Provide context for the latest headline inflation figures
    st.info(
    "Headline year-on-year inflation was 2.35% in August 2026, "
    "with Transport, Food, and Housing & Utilities "
    "the top contributing categories."
    )

# Display the latest headline inflation figures
    st.subheader(f"Latest Headline Inflation — {latest_month}")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Year-on-Year Inflation",
            f"{latest_inflation:.2f}%"
        )

    with col2:
        st.metric(
            "CPI Index (2024 = 100)",
            f"{latest_cpi:.2f}"
        )


    # Load monthly expenditure-category contributions
    overview_contributions = pd.read_csv(
        "outputs/tables/contributions_monthly.csv"
    )

    # Convert the date column to datetime
    overview_contributions["date"] = pd.to_datetime(
        overview_contributions["date"]
    )

    # Find the latest available contribution month
    latest_contribution_month = overview_contributions["date"].max()

    # Keep only the latest month's observations
    latest_month_data = overview_contributions[
        overview_contributions["date"] == latest_contribution_month
    ]

    # Find the three largest contributors
    latest_top_three = latest_month_data.nlargest(
        3, "contribution_pp"
    )

    # Display the results
    st.markdown(
        f"#### Top Three Inflation Contributors — "
        f"{latest_contribution_month:%B %Y}"
    )

    for _, row in latest_top_three.iterrows():
        st.write(
            f"**{row['series']}**: "
            f"{row['contribution_pp']:.2f} percentage points"
        )

    # Let users choose how to explore the CPI data
    view = st.radio(
        "Choose a dashboard view",
        ["Overall trend", "Compare categories"]
    )

    # Let the user select between viewing the overall trend
    #  or comparing specific categories
    if view == "Overall trend":
        categories = ["All Items"]

    else:
        categories = st.multiselect(
            "Choose CPI categories",
            df["series"].unique(),
            default=["Food", "Transport"]
        )

    # Let the user select which measure to display
    measure = st.selectbox(
        "Choose a measure",
        ["cpi", "yoy_pct"],
        format_func=lambda x: measure_labels[x]
    )

    # Let the user choose a starting date
    start_date = st.date_input(
        "Start date",
        value=df["date"].min().date()
    )

    # Let the user choose an ending date
    end_date = st.date_input(
        "End date",
        value=df["date"].max().date()
    )

    # Validate that the starting date is not later than the
    # ending date with a boolean variable
    valid_dates = start_date <= end_date

    # Filter the DataFrame based on the selected categories,
    # measure, and date range
    selected_category = df[
        (df["series"].isin(categories))
        & (df["date"] >= pd.Timestamp(start_date))
        & (df["date"] <= pd.Timestamp(end_date))
    ]
    # Set the chart title based on the selected view
    if view == "Overall trend":
        chart_title = f"Singapore Overall {measure_labels[measure]}"
    else:
        chart_title = f"Singapore {measure_labels[measure]} by Category"

    # Create the graph for the selected category
    fig = px.line(
        data_frame=selected_category,
        x="date",
        y=measure,
        color="series",
        title=chart_title,
        labels={
            "date": "Date",
            "series": "Expenditure Category",
            "cpi": measure_labels["cpi"],
            "yoy_pct": measure_labels["yoy_pct"]
        }
    )

    # Add a zero-inflation reference line
    if measure == "yoy_pct":
        fig.add_hline(
            y=0,
            line_dash="dash",
            line_color="gray"
        )

    # Display the graph only if categories are selected
    if not valid_dates:
        st.error("Starting date cannot be later than ending date.")

    elif len(categories) == 0:
        st.warning("Please select at least one CPI category.")

    else:
        st.plotly_chart(fig, use_container_width=True)

#_____________________________________________________________
# Dashboard Section: Inflation Contributions

with tab2:
    # Display a subheader for the inflation contributions section
    st.subheader("What Drove Inflation?")

    # Provide context for the inflation contributions
    st.info(
        "Transport, Food, and Housing & Utilities ranked highest "
        "in the 2022–23 surge, while Housing & Utilities, Food, "
        "and Transport ranked highest in the 2024–26 cooling."
    )

    # Load monthly inflation contributions
    contributions = pd.read_csv(
        "outputs/tables/contributions_monthly.csv"
    )

    # Allow users to select a month
    months = sorted(contributions["date"].unique())

    selected_month = st.selectbox(
        "Choose a month to examine",
        months,
        index=months.index("2022-09-01"),
        format_func=lambda x: pd.to_datetime(x).strftime("%B %Y")
    )


    # Warn users when selecting a month in 2024
    if pd.to_datetime(selected_month).year == 2024:
        st.warning(
            "2024 contribution estimates use approximate transitional weights. "
            "Interpret these results with additional caution."
        )


    # Filter and rank expenditure categories
    monthly_data = contributions[
        contributions["date"] == selected_month
    ]

    monthly_data = monthly_data.sort_values(
        "contribution_pp",
        ascending=True
    )

        # Identify the three largest positive contributors
    top_three = monthly_data.nlargest(
        3, "contribution_pp"
    )

    st.markdown("#### Top Three Inflation Contributors")

    for _, row in top_three.iterrows():
        st.write(
            f"**{row['series']}**: "
            f"{row['contribution_pp']:.2f} percentage points"
        )

    # Format the selected month for display in the chart title
    formatted_month = pd.to_datetime(
        selected_month
    ).strftime("%B %Y")

    # Draw the contribution chart
    fig_contributions = px.bar(
        monthly_data,
        x="contribution_pp",
        y="series",
        orientation="h",
        title=f"Inflation Contributions — {formatted_month}",
        labels={
            "contribution_pp": "Contribution (percentage points)",
            "series": "Expenditure Category"
        }
    )

    st.plotly_chart(fig_contributions, use_container_width=True)

    # --------------------------------------------
    # Stacked contributions over time
    # --------------------------------------------

    st.subheader("Inflation Contributions Over Time")

    # Create a copy so the existing monthly chart is unaffected
    contributions_time = contributions.copy()

    # Convert dates to datetime format
    contributions_time["date"] = pd.to_datetime(
        contributions_time["date"]
    )

    # Get the months available in our dataset
    available_months = sorted(
        contributions_time["date"].dt.date.unique()
    )

    # Allow users to choose a start and end month
    range_start, range_end = st.select_slider(
        "Choose a date range",
        options=available_months,
        value=(
            pd.Timestamp("2022-01-01").date(),
            pd.Timestamp("2023-12-01").date()
        ),
        format_func=lambda d: d.strftime("%b %Y")
    )

    # Warn users whenever the selected range includes 2024
    if range_start.year <= 2024 <= range_end.year:
        st.warning(
            "The selected period includes 2024, when approximate "
            "transitional CPI expenditure weights were used. "
            "Interpret contribution estimates with additional caution."
        )

    # Filter the data to the selected period
    filtered_contributions = contributions_time[
        (contributions_time["date"] >= pd.Timestamp(range_start))
        & (contributions_time["date"] <= pd.Timestamp(range_end))
    ]

    # Build a stacked bar chart
    fig_stacked = px.bar(
        filtered_contributions,
        x="date",
        y="contribution_pp",
        color="series",
        barmode="relative",
        title="Monthly Inflation Contributions by Category",
        labels={
            "date": "Month",
            "contribution_pp": "Contribution (percentage points)",
            "series": "Expenditure Category"
        }
    )

    # Improve the chart appearance
    fig_stacked.update_layout(
        height=550,
        xaxis_tickformat="%b %Y",
        legend_title_text="Expenditure Category"
    )

    fig_stacked.add_hline(
        y=0,
        line_color="gray",
        line_width=1
    )

    st.plotly_chart(fig_stacked, use_container_width=True)

    st.caption(
        "Positive contributions increase headline inflation, "
        "while negative contributions offset it. "
        "The expenditure-weight regime changes around 2024; "
        "contributions across regimes require caution."
    )


    # Explain the CPI expenditure-weight methodology
    st.caption(
        "Inflation contributions are estimated using CPI expenditure weights. "
        "The expenditure basket was updated around 2024, so contribution "
        "magnitudes across different weighting periods are not directly comparable."
    )
#_____________________________________________________________
# Dashboard Section: Income Group Inflation Comparison

with tab4:
    # Display a subheader for the income group inflation
    st.subheader("Rich vs Poor: Inflation by Income Group")

    # Provide context for the income group comparison
    st.info(
    "In 2026 1H, the lowest-minus-highest income inflation gap "
    "was -0.43 pp. Education and Health had the largest negative "
    "category gaps, while Transport had the largest positive gap."
    )

    # Load processed income-group data
    income = pd.read_csv(
        "outputs/tables/income_group_inflation_gaps.csv"
    )


    # Let users choose which household income groups to compare
    income_groups = st.multiselect(
        "Select household income groups",
        ["Lowest 20%", "Middle 60%", "Highest 20%"],
        default=["Lowest 20%", "Middle 60%", "Highest 20%"]
    )

    # Plot only the selected income groups
    if income_groups:
        fig_income = px.line(
            income,
            x="period",
            y=income_groups,
            markers=True,
            title="Inflation Rates by Household Income Group",
            labels={
                "period": "Half-Year Period",
                "value": "Inflation Rate (%)",
                "variable": "Income Group"
            }
        )

        st.plotly_chart(fig_income, use_container_width=True)
    else:
        st.warning("Please select at least one income group.")


    # Create a bar chart to visualize the inflation gap between the
    # lowest and highest income groups
    st.subheader("Inflation Gap Between Income Groups")

    fig_gap = px.bar(
        income,
        x="period",
        y="gap_low_minus_high_pp",
        title="Inflation Gap: Lowest 20% Minus Highest 20%",
        labels={
            "period": "Half-Year Period",
            "gap_low_minus_high_pp": "Inflation Gap (percentage points)"
        }
    )

    # Add a zero reference line
    fig_gap.add_hline(
        y=0,
        line_dash="dash",
        line_color="gray"
    )

    st.plotly_chart(fig_gap, use_container_width=True)

    #_____________________________________________________________
    # Dashboard Section: Category Inflation Differences
    st.subheader("Which Categories Show the Largest Income-Group Differences?")

    # Load category-level inflation differences
    drivers = pd.read_csv(
        "outputs/tables/income_gap_drivers.csv"
    )

    # Create a list of available half-year periods
    periods = drivers["period"].unique().tolist()

    # Let the user choose a period
    selected_period = st.selectbox(
        "Choose a half-year period",
        periods,
        index=periods.index("2022 2H")
    )

    # Keep only observations for the selected period
    selected_drivers = drivers[
        drivers["period"] == selected_period
    ]

    # Sort category differences
    selected_drivers = selected_drivers.sort_values(
        "rate_gap_low_minus_high_pp",
        ascending=True
    )

    # Create a horizontal bar chart
    fig_drivers = px.bar(
        selected_drivers,
        x="rate_gap_low_minus_high_pp",
        y="series",
        orientation="h",
        title=f"Category Inflation Differences — {selected_period}",
        labels={
            "rate_gap_low_minus_high_pp": "Lowest 20% minus Highest 20% (pp)",
            "series": "Expenditure Category"
        }
    )

    # Zero means equal category inflation rates
    fig_drivers.add_vline(
        x=0,
        line_dash="dash",
        line_color="gray"
    )

    st.plotly_chart(fig_drivers, use_container_width=True)

    st.caption(
        "Bars show differences in category inflation rates, "
        "not contributions to the overall household inflation gap."
    )

#_____________________________________________________________

with tab3:

    st.info(
    "Since January 2019, Transport (51.7%), Food (23.1%), "
    "and Housing & Utilities (18.2%) had the largest category "
    "CPI increases through August 2026."
    )

    # Dashboard Section: Cumulative Price Changes Since 2019
    st.subheader("How Much Have Prices Increased Since 2019?")

    # Select CPI observations from January 2019
    baseline = df[
        df["date"] == "2019-01-01"
    ][["series", "cpi"]]

    # Rename the baseline CPI column
    baseline = baseline.rename(
        columns={"cpi": "cpi_2019"}
    )

    # Attach the January 2019 CPI to every observation
    cumulative = df.merge(
        baseline,
        on="series",
        how="left"
    )

    # Calculate cumulative percentage change since January 2019
    cumulative["cumulative_pct"] = (
        (cumulative["cpi"] / cumulative["cpi_2019"] - 1) * 100
    )

    # Find the latest observation for each category
    latest_date = cumulative["date"].max()

    latest_cumulative = cumulative[
        cumulative["date"] == latest_date
    ]

    # Sort categories by cumulative price increase
    latest_cumulative = latest_cumulative.sort_values(
        "cumulative_pct",
        ascending=True
    )

    # Create a horizontal bar chart
    fig_cumulative = px.bar(
        latest_cumulative,
        x="cumulative_pct",
        y="series",
        orientation="h",
        title="Cumulative Price Changes Since January 2019",
        labels={
            "cumulative_pct": "Cumulative Price Change (%)",
            "series": "Expenditure Category"
        }
    )

    st.plotly_chart(fig_cumulative, use_container_width=True)

    st.caption(
        f"Percentage changes from January 2019 to "
        f"{latest_date.strftime('%B %Y')}, "
        "calculated using CPI indices (2024 = 100)."
    )

#_____________________________________________________________
# Dashboard Section: Behind the Numbers

with tab5:
    st.subheader("Behind the Numbers: COE Premiums and HDB Rents")
    # Provide context for the COE and HDB comparisons
    st.info(
    "Since February 2021, the Private Transport CPI and COE "
    "premium indexes both rose, reaching 150.0 and 292.0, "
    "respectively, in August 2026."
    )

    # Load the processed comparison datasets
    transport_coe = pd.read_csv(
        "outputs/tables/transport_vs_coe.csv"
    )

    accommodation_rent = pd.read_csv(
        "outputs/tables/accommodation_vs_hdb_rent.csv"
    )

    # Convert the date columns to datetime
    transport_coe["date"] = pd.to_datetime(transport_coe["date"])
    accommodation_rent["date"] = pd.to_datetime(accommodation_rent["date"])

    # Chart 1: Transport CPI versus COE premiums
    fig_coe = px.line(
        transport_coe,
        x="date",
        y=["transport_cpi_index", "coe_premium_index"],
        title="Private Transport CPI vs COE Premiums",
        labels={
            "date": "Date",
            "value": "Index (February 2021 = 100)",
            "variable": "Series"
        }
    )

    fig_coe.for_each_trace(
        lambda trace: trace.update(
            name={
                "transport_cpi_index": "Private Transport CPI",
                "coe_premium_index": "COE Premiums (Categories A & B)"
            }.get(trace.name, trace.name)
        )
    )


    # Let users choose which Transport comparison lines appear
    transport_series = st.multiselect(
        "Choose Transport comparison series",
        ["Private Transport CPI", "COE Premiums (Categories A & B)"],
        default=["Private Transport CPI", "COE Premiums (Categories A & B)"]
    )

    # Show only the selected lines
    fig_coe.for_each_trace(
        lambda trace: trace.update(
            visible=trace.name in transport_series
        )
    )


    st.plotly_chart(fig_coe, use_container_width=True)

    # Chart 2: Accommodation CPI versus HDB rents
    fig_rent = px.line(
        accommodation_rent,
        x="date",
        y=["accommodation_cpi_index", "hdb_rent_index"],
        title="Accommodation CPI vs HDB Rents",
        labels={
            "date": "Date",
            "value": "Index (February 2021 = 100)",
            "variable": "Series"
        }
    )

    fig_rent.for_each_trace(
        lambda trace: trace.update(
            name={
                "accommodation_cpi_index": "Accommodation CPI",
                "hdb_rent_index": "HDB Median Rents"
            }.get(trace.name, trace.name)
        )
    )


    # Let users choose which housing comparison lines appear
    rent_series = st.multiselect(
        "Choose Housing comparison series",
        ["Accommodation CPI", "HDB Median Rents"],
        default=["Accommodation CPI", "HDB Median Rents"]
    )

    # Show only the selected lines
    fig_rent.for_each_trace(
        lambda trace: trace.update(
            visible=trace.name in rent_series
        )
    )


    st.plotly_chart(fig_rent, use_container_width=True)

    st.caption(
        "All series are rebased to February 2021 = 100. "
        "These comparisons are descriptive and do not establish causation."
    )

# Dashboard methodology and data sources
with st.expander("Data Sources and Methodology"):

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
        # Explain the CPI linking methodology
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

    # Load the residual-check table
    residuals = pd.read_csv(
        "outputs/tables/contribution_residual_check.csv"
    )

    residuals["date"] = pd.to_datetime(residuals["date"])

    # Calculate absolute residuals
    residuals["abs_residual"] = residuals["residual_pp"].abs()

    # Calculate how often the residual is below 0.3 pp
    pct_below = (
        (residuals["abs_residual"] < 0.3).mean() * 100
    )

    # Find the largest absolute residual
    largest_row = residuals.loc[
        residuals["abs_residual"].idxmax()
    ]

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Months with |Residual| < 0.3 pp",
            f"{pct_below:.1f}%"
        )

    with col2:
        st.metric(
            "Largest Absolute Residual",
            f"{largest_row['abs_residual']:.2f} pp"
        )

    st.caption(
            "Largest residual occurred in "
            f"{largest_row['date']:%B %Y}. "
            "Residuals measure the accuracy of the approximate "
            "contribution decomposition, not errors in CPI linking."
        )