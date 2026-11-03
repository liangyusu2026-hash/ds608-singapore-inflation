import pandas as pd
import plotly.express as px
import streamlit as st

# Load the processed data
df = pd.read_csv("outputs/tables/inflation_by_category.csv")

#____________________________________________________________
# Dashboard Section: Category Explorer

# Convert the "date" column to datetime format for proper plotting
df["date"] = pd.to_datetime(df["date"])

# Define a dictionary to map measure names to more
#  reader-friendly labels
measure_labels = {
    "cpi": "CPI Index (2024 = 100)",
    "yoy_pct": "Year-on-Year Inflation (%)"
}

# Display a dashboard title
st.title("Singapore CPI Dashboard")

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


# If no categories are selected, display a warning message
if len(categories) == 0:
    st.warning("Please select at least one CPI category")
    st.stop()


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
# ending date
if start_date > end_date:
    st.error("Starting date cannot be later than ending date.")
    st.stop()

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

# Display the graph inside Streamlit
st.plotly_chart(fig, use_container_width=True)

#_____________________________________________________________
# Dashboard Section: Inflation Contributions

# Display a subheader for the inflation contributions section
st.subheader("What Drove Inflation?")

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


# Filter and rank expenditure categories
monthly_data = contributions[
    contributions["date"] == selected_month
]

monthly_data = monthly_data.sort_values(
    "contribution_pp",
    ascending=True
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

#_____________________________________________________________
# Dashboard Section: Income Group Inflation Comparison


# Display a subheader for the income group inflation
st.subheader("Rich vs Poor: Inflation by Income Group")

# Load processed income-group data
income = pd.read_csv(
    "outputs/tables/income_group_inflation_gaps.csv"
)

# Create a line graph comparing income groups
fig_income = px.line(
    income,
    x="period",
    y=["Lowest 20%", "Middle 60%", "Highest 20%"],
    markers=True,
    title="Inflation Rates by Household Income Group",
    labels={
        "period": "Half-Year Period",
        "value": "Inflation Rate (%)",
        "variable": "Income Group"
    }
)

st.plotly_chart(fig_income, use_container_width=True)
