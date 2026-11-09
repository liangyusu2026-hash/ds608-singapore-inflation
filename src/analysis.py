from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"

ANALYSIS_START = pd.Timestamp("2019-01-01")
COMPARISON_START = pd.Timestamp("2021-02-01")
DIVISION_COUNT = 10


def category_inflation():
    """Save monthly CPI levels and inflation for All Items and the divisions.

    Parameters
    ----------
    None

    Returns
    -------
    pandas.DataFrame
        Monthly CPI and year-on-year inflation by category.
    """
    # 1. Read the monthly CPI file and inspect its contents
    monthly = pd.read_csv(PROCESSED / "cpi_monthly_long.csv")
    monthly["date"] = pd.to_datetime(monthly["date"], format="%Y-%m-%d")
    print(monthly.head())
    monthly.info()

    # 2. Keep All Items and the 10 divisions from January 2019 onward
    selected = monthly[
        ((monthly["series"] == "All Items") | (monthly["level_name"] == "division"))
        & (monthly["date"] >= ANALYSIS_START)
    ].copy()
    result = selected[["date", "series", "cpi", "yoy_pct"]].sort_values(
        ["date", "series"]
    ).reset_index(drop=True)

    # 3. Validate the output before saving it
    assert not result.duplicated(["date", "series"]).any(), "duplicate category-month rows"
    assert (result["date"] >= ANALYSIS_START).all(), "dates before January 2019 found"

    # 4. Store and share the table
    TABLES.mkdir(parents=True, exist_ok=True)
    result.to_csv(TABLES / "inflation_by_category.csv", index=False)
    print(
        f"Saved {len(result):,} rows, {result['date'].min():%b %Y} "
        f"to {result['date'].max():%b %Y}"
    )
    return result


def contributions():
    """Calculate division contributions to monthly headline inflation.

    Parameters
    ----------
    None

    Returns
    -------
    pandas.DataFrame
        Monthly contribution in percentage points for each CPI division.
    """
    # 1. Read CPI and weight inputs, then inspect them
    monthly = pd.read_csv(PROCESSED / "cpi_monthly_long.csv")
    weights = pd.read_csv(PROCESSED / "cpi_weights_2024.csv")
    monthly["date"] = pd.to_datetime(monthly["date"], format="%Y-%m-%d")
    print(monthly.head())
    monthly.info()
    print(weights.head())
    weights.info()

    # 2. Identify the 10 CPI divisions and exclude special aggregates
    division_names = sorted(
        monthly.loc[monthly["level_name"] == "division", "series"].unique()
    )
    division_weights = weights[weights["series"].isin(division_names)].copy()
    assert len(division_names) == DIVISION_COUNT, "expected exactly 10 CPI divisions"
    assert len(division_weights) == DIVISION_COUNT, "division weights are incomplete"
    assert division_weights["weight_2019"].sum() == 10000, (
        "2019 division weights should add up to 10,000"
    )
    assert division_weights["weight_2024"].sum() == 10000, (
        "2024 division weights should add up to 10,000"
    )

    # 3. Sort each series and get its CPI from 12 observations earlier
    monthly = monthly.sort_values(["series", "date"]).copy()
    monthly["cpi_12_months_ago"] = monthly.groupby("series")["cpi"].shift(12)
    # 2019 weights require CPI indices on the matching 2019=100 basis.
    cpi_2019_average = monthly.loc[monthly["date"].dt.year == 2019].groupby(
        "series"
    )["cpi"].mean()
    monthly["cpi_2019base"] = (
        monthly["cpi"] / monthly["series"].map(cpi_2019_average) * 100
    )
    monthly["cpi_2019base_12_months_ago"] = monthly.groupby("series")[
        "cpi_2019base"
    ].shift(12)
    analysis_rows = monthly[monthly["date"] >= ANALYSIS_START].copy()

    # 4. Match each division with All Items CPI from the same month
    division_rows = analysis_rows[
        analysis_rows["series"].isin(division_names)
    ].merge(
        analysis_rows.loc[
            analysis_rows["series"] == "All Items",
            [
                "date",
                "cpi_12_months_ago",
                "cpi_2019base_12_months_ago",
            ],
        ].rename(
            columns={
                "cpi_12_months_ago": "all_items_cpi_12_months_ago",
                "cpi_2019base_12_months_ago": (
                    "all_items_cpi_2019base_12_months_ago"
                ),
            }
        ),
        on="date",
        how="inner",
    )
    division_rows = division_rows.merge(
        division_weights[["series", "weight_2019", "weight_2024"]],
        on="series",
        how="inner",
        validate="many_to_one",
    )

    # 5. Select the weight year and calculate each contribution
    division_rows["weight_used"] = division_rows["weight_2024"]
    use_2019_weights = division_rows["date"] <= pd.Timestamp("2023-12-01")
    division_rows.loc[use_2019_weights, "weight_used"] = division_rows.loc[
        use_2019_weights, "weight_2019"
    ]
    cpi_used = division_rows["cpi"].copy()
    cpi_used.loc[use_2019_weights] = division_rows.loc[
        use_2019_weights, "cpi_2019base"
    ]
    cpi_12_months_ago_used = division_rows["cpi_12_months_ago"].copy()
    cpi_12_months_ago_used.loc[use_2019_weights] = division_rows.loc[
        use_2019_weights, "cpi_2019base_12_months_ago"
    ]
    all_items_cpi_12_months_ago_used = division_rows[
        "all_items_cpi_12_months_ago"
    ].copy()
    all_items_cpi_12_months_ago_used.loc[use_2019_weights] = division_rows.loc[
        use_2019_weights, "all_items_cpi_2019base_12_months_ago"
    ]
    division_rows["weight_note"] = ""
    in_2024 = division_rows["date"].dt.year == 2024
    division_rows.loc[in_2024, "weight_note"] = "approximate (basket change)"
    division_rows["contribution_pp"] = (
        (division_rows["weight_used"] / 10000)
        * (cpi_used - cpi_12_months_ago_used)
        / all_items_cpi_12_months_ago_used
        * 100
    )
    result = division_rows[
        ["date", "series", "weight_used", "contribution_pp", "weight_note"]
    ].sort_values(["date", "series"]).reset_index(drop=True)

    # 6. Validate the result before saving it
    assert not result.duplicated(["date", "series"]).any(), "duplicate contribution rows"
    divisions_per_month = result.groupby("date")["series"].nunique()
    assert divisions_per_month.eq(DIVISION_COUNT).all(), (
        "each month must have exactly 10 division contributions"
    )
    assert result["contribution_pp"].notna().all(), "missing contribution values"

    # 7. Store and share the table
    TABLES.mkdir(parents=True, exist_ok=True)
    result.to_csv(TABLES / "contributions_monthly.csv", index=False)
    print(
        f"Saved {len(result):,} rows, {result['date'].min():%b %Y} "
        f"to {result['date'].max():%b %Y}"
    )
    return result


def surge_vs_cooling():
    """Compare category contribution averages and ranks across two periods.

    Parameters
    ----------
    None

    Returns
    -------
    pandas.DataFrame
        Period averages, ranks, and category weights for the surge and cooling.
    """
    # 1. Read and inspect the saved contribution table
    contributions_table = pd.read_csv(TABLES / "contributions_monthly.csv")
    contributions_table["date"] = pd.to_datetime(
        contributions_table["date"], format="%Y-%m-%d"
    )
    print(contributions_table.head())
    contributions_table.info()

    # 2. Select the surge and cooling periods
    surge_start = pd.Timestamp("2022-01-01")
    surge_end = pd.Timestamp("2023-12-01")
    cooling_start = pd.Timestamp("2024-01-01")
    latest_date = contributions_table["date"].max()
    surge = contributions_table.loc[
        contributions_table["date"].between(surge_start, surge_end)
    ].copy()
    cooling = contributions_table.loc[
        contributions_table["date"].between(cooling_start, latest_date)
    ].copy()
    required_columns = ["date", "series", "weight_used", "contribution_pp"]
    assert contributions_table[required_columns].notna().all().all(), (
        "missing contribution inputs for surge and cooling comparison"
    )
    assert not contributions_table.duplicated(["date", "series"]).any(), (
        "duplicate contribution category-month rows"
    )
    assert not surge.empty, "no contribution rows in the surge period"
    assert not cooling.empty, "no contribution rows in the cooling period"

    expected_surge_dates = pd.date_range(surge_start, surge_end, freq="MS")
    expected_cooling_dates = pd.date_range(cooling_start, latest_date, freq="MS")
    assert set(surge["date"].unique()) == set(expected_surge_dates), (
        "surge period is missing contribution months"
    )
    assert set(cooling["date"].unique()) == set(expected_cooling_dates), (
        "cooling period is missing contribution months"
    )
    assert surge.groupby("date")["series"].nunique().eq(DIVISION_COUNT).all(), (
        "each surge month must have exactly 10 category contributions"
    )
    assert cooling.groupby("date")["series"].nunique().eq(DIVISION_COUNT).all(), (
        "each cooling month must have exactly 10 category contributions"
    )
    assert surge.groupby("series")["weight_used"].nunique().eq(1).all(), (
        "surge category weights must be consistent"
    )
    assert cooling.groupby("series")["weight_used"].nunique().eq(1).all(), (
        "cooling category weights must be consistent"
    )

    # 3. Calculate period averages and ranks without comparing contribution sizes
    surge_averages = (
        surge.groupby("series", as_index=False)
        .agg(
            surge_avg_pp=("contribution_pp", "mean"),
            weights_surge=("weight_used", "first"),
        )
        .sort_values(["surge_avg_pp", "series"], ascending=[False, True])
        .reset_index(drop=True)
    )
    cooling_averages = (
        cooling.groupby("series", as_index=False)
        .agg(
            cooling_avg_pp=("contribution_pp", "mean"),
            weights_cooling=("weight_used", "first"),
        )
        .sort_values(["cooling_avg_pp", "series"], ascending=[False, True])
        .reset_index(drop=True)
    )
    surge_averages["surge_rank"] = (
        surge_averages["surge_avg_pp"].rank(method="first", ascending=False).astype(int)
    )
    cooling_averages["cooling_rank"] = (
        cooling_averages["cooling_avg_pp"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    result = surge_averages.merge(
        cooling_averages, on="series", how="inner", validate="one_to_one"
    )
    result = result[
        [
            "series",
            "surge_avg_pp",
            "cooling_avg_pp",
            "surge_rank",
            "cooling_rank",
            "weights_surge",
            "weights_cooling",
        ]
    ].sort_values(["surge_avg_pp", "series"], ascending=[False, True])
    result = result.reset_index(drop=True)

    # 4. Validate the output before saving it
    assert len(result) == DIVISION_COUNT, "surge and cooling categories do not match"
    assert not result.duplicated(["series"]).any(), (
        "duplicate categories in surge and cooling comparison"
    )
    assert result.notna().all().all(), "missing surge and cooling output values"

    # 5. Store and share the table
    TABLES.mkdir(parents=True, exist_ok=True)
    result.to_csv(TABLES / "surge_vs_cooling.csv", index=False)
    print(
        f"Saved {len(result):,} categories for Jan 2022-Dec 2023 and "
        f"Jan 2024-{latest_date:%b %Y}"
    )
    return result


def residual_check():
    """Compare summed division contributions with headline inflation.

    Parameters
    ----------
    None

    Returns
    -------
    pandas.DataFrame
        Headline inflation, summed contributions, and their residual by month.
    """
    # 1. Read headline inflation and contribution tables
    monthly = pd.read_csv(TABLES / "inflation_by_category.csv")
    contributions_table = pd.read_csv(TABLES / "contributions_monthly.csv")
    monthly["date"] = pd.to_datetime(monthly["date"], format="%Y-%m-%d")
    contributions_table["date"] = pd.to_datetime(
        contributions_table["date"], format="%Y-%m-%d"
    )
    print(monthly.head())
    monthly.info()
    print(contributions_table.head())
    contributions_table.info()

    # 2. Sum the 10 divisions and join to All Items inflation
    summed = (
        contributions_table.groupby("date", as_index=False)
        .agg(sum_of_contributions=("contribution_pp", "sum"))
    )
    headline = monthly.loc[
        monthly["series"] == "All Items", ["date", "yoy_pct"]
    ].rename(columns={"yoy_pct": "headline_yoy"})
    result = headline.merge(summed, on="date", how="inner", validate="one_to_one")
    result["residual_pp"] = result["headline_yoy"] - result["sum_of_contributions"]
    result = result.sort_values("date").reset_index(drop=True)

    # 3. Validate, then measure how close the sum is to headline inflation
    assert not result.duplicated(["date"]).any(), "duplicate residual month"
    assert result["residual_pp"].notna().all(), "missing residual values"
    within_tolerance = result["residual_pp"].abs() < 0.3
    share_within_tolerance = within_tolerance.mean() * 100
    largest_residual = result.loc[result["residual_pp"].abs().idxmax()]
    print(
        f"Residuals below 0.3 pp: {within_tolerance.sum()}/{len(result)} "
        f"months ({share_within_tolerance:.1f}%). "
        f"Largest absolute residual: {largest_residual['residual_pp']:.3f} pp "
        f"in {largest_residual['date']:%b %Y}."
    )
    for year, year_rows in result.groupby(result["date"].dt.year):
        largest_year_residual = year_rows.loc[
            year_rows["residual_pp"].abs().idxmax()
        ]
        print(
            f"Largest absolute residual in {year}: "
            f"{abs(largest_year_residual['residual_pp']):.3f} pp "
            f"in {largest_year_residual['date']:%b %Y}."
        )

    # 4. Store and share the table
    TABLES.mkdir(parents=True, exist_ok=True)
    result.to_csv(TABLES / "contribution_residual_check.csv", index=False)
    print(
        f"Saved {len(result):,} rows, {result['date'].min():%b %Y} "
        f"to {result['date'].max():%b %Y}"
    )
    return result


def weight_sensitivity():
    """Compare division contribution rankings under the 2019 and 2024 weights.

    Parameters
    ----------
    None

    Returns
    -------
    pandas.DataFrame
        Monthly division contributions and ranks calculated with both weights.
    """
    # 1. Read CPI and weight inputs, then inspect their contents
    monthly = pd.read_csv(PROCESSED / "cpi_monthly_long.csv")
    weights = pd.read_csv(PROCESSED / "cpi_weights_2024.csv")
    monthly["date"] = pd.to_datetime(monthly["date"], format="%Y-%m-%d")
    print(monthly.head())
    monthly.info()
    print(weights.head())
    weights.info()

    # 2. Identify exactly the 10 divisions and validate their weight totals
    division_names = sorted(
        monthly.loc[monthly["level_name"] == "division", "series"].unique()
    )
    division_weights = weights[weights["series"].isin(division_names)].copy()
    assert len(division_names) == DIVISION_COUNT, "expected exactly 10 CPI divisions"
    assert len(division_weights) == DIVISION_COUNT, "division weights are incomplete"
    assert division_weights["weight_2019"].sum() == 10000, (
        "2019 division weights should add up to 10,000"
    )
    assert division_weights["weight_2024"].sum() == 10000, (
        "2024 division weights should add up to 10,000"
    )

    # 3. Calculate the same-month and 12-month-prior CPI for each series
    monthly = monthly.sort_values(["series", "date"]).copy()
    monthly["cpi_12_months_ago"] = monthly.groupby("series")["cpi"].shift(12)
    cpi_2019_average = monthly.loc[monthly["date"].dt.year == 2019].groupby(
        "series"
    )["cpi"].mean()
    monthly["cpi_2019base"] = (
        monthly["cpi"] / monthly["series"].map(cpi_2019_average) * 100
    )
    monthly["cpi_2019base_12_months_ago"] = monthly.groupby("series")[
        "cpi_2019base"
    ].shift(12)
    analysis_rows = monthly[monthly["date"] >= pd.Timestamp("2025-01-01")]
    division_rows = analysis_rows[
        analysis_rows["series"].isin(division_names)
    ].merge(
        analysis_rows.loc[
            analysis_rows["series"] == "All Items",
            [
                "date",
                "cpi_12_months_ago",
                "cpi_2019base_12_months_ago",
            ],
        ].rename(
            columns={
                "cpi_12_months_ago": "all_items_cpi_12_months_ago",
                "cpi_2019base_12_months_ago": (
                    "all_items_cpi_2019base_12_months_ago"
                ),
            }
        ),
        on="date",
        how="inner",
    )
    division_rows = division_rows.merge(
        division_weights[["series", "weight_2019", "weight_2024"]],
        on="series",
        how="inner",
        validate="many_to_one",
    )

    # 4. Calculate contributions and rank each division under both weight sets
    cpi_change_2019base = (
        division_rows["cpi_2019base"]
        - division_rows["cpi_2019base_12_months_ago"]
    ) / division_rows["all_items_cpi_2019base_12_months_ago"] * 100
    cpi_change_2024base = (
        division_rows["cpi"] - division_rows["cpi_12_months_ago"]
    ) / division_rows["all_items_cpi_12_months_ago"] * 100
    division_rows["contribution_2019w_pp"] = (
        division_rows["weight_2019"] / 10000
    ) * cpi_change_2019base
    division_rows["contribution_2024w_pp"] = (
        division_rows["weight_2024"] / 10000
    ) * cpi_change_2024base
    division_rows = division_rows.sort_values(["date", "series"]).copy()
    division_rows["rank_2019w"] = division_rows.groupby("date")[
        "contribution_2019w_pp"
    ].rank(method="first", ascending=False)
    division_rows["rank_2024w"] = division_rows.groupby("date")[
        "contribution_2024w_pp"
    ].rank(method="first", ascending=False)
    result = division_rows[
        [
            "date",
            "series",
            "contribution_2019w_pp",
            "contribution_2024w_pp",
            "rank_2019w",
            "rank_2024w",
        ]
    ].reset_index(drop=True)

    # 5. Validate rows and compare the ordered top-three lists for each month
    assert not result.duplicated(["date", "series"]).any(), (
        "duplicate sensitivity division-month rows"
    )
    divisions_per_month = result.groupby("date")["series"].nunique()
    assert divisions_per_month.eq(DIVISION_COUNT).all(), (
        "each month must have exactly 10 division comparisons"
    )
    assert result[
        ["contribution_2019w_pp", "contribution_2024w_pp"]
    ].notna().all().all(), "missing sensitivity contributions"

    identical_months = 0
    month_count = 0
    for _, month in result.groupby("date"):
        top_2019 = month.nsmallest(3, "rank_2019w")["series"].tolist()
        top_2024 = month.nsmallest(3, "rank_2024w")["series"].tolist()
        identical_months += top_2019 == top_2024
        month_count += 1
    assert month_count > 0, "no months available for weight sensitivity"
    identical_share = identical_months / month_count * 100
    print(
        f"Top-three ranking identical in {identical_months}/{month_count} "
        f"months ({identical_share:.1f}%)."
    )

    # 6. Store and share the sensitivity table
    TABLES.mkdir(parents=True, exist_ok=True)
    result.to_csv(TABLES / "weight_sensitivity.csv", index=False)
    print(
        f"Saved {len(result):,} rows, {result['date'].min():%b %Y} "
        f"to {result['date'].max():%b %Y}"
    )
    return result


def income_group_gaps():
    """Compare All Items inflation rates across household income groups.

    Parameters
    ----------
    None

    Returns
    -------
    pandas.DataFrame
        Half-yearly All Items inflation rates and income-group gaps.
    """
    # 1. Read and inspect the income-group CPI file
    income = pd.read_csv(PROCESSED / "cpi_income_groups_long.csv")
    income["date"] = pd.to_datetime(income["date"], format="%Y-%m-%d")
    print(income.head())
    income.info()

    # 2. Keep All Items from 2019 1H onward and reshape income groups to columns
    selected = income[
        (income["series"] == "All Items") & (income["period"] >= "2019 1H")
    ].copy()
    result = selected.pivot(
        index="period", columns="income_group", values="yoy_pct"
    ).reset_index()
    result.columns.name = None
    result = result[
        ["period", "Lowest 20%", "Middle 60%", "Highest 20%"]
    ].sort_values("period").reset_index(drop=True)
    result["gap_low_minus_high_pp"] = result["Lowest 20%"] - result["Highest 20%"]
    result["gap_middle_minus_high_pp"] = (
        result["Middle 60%"] - result["Highest 20%"]
    )

    # 3. Validate the output before saving it
    assert not result.duplicated(["period"]).any(), "duplicate income-group period"
    assert (result["period"] >= "2019 1H").all(), "periods before 2019 1H found"

    # 4. Store and share the table
    TABLES.mkdir(parents=True, exist_ok=True)
    result.to_csv(TABLES / "income_group_inflation_gaps.csv", index=False)
    print(f"Saved {len(result):,} rows, {result['period'].min()} to {result['period'].max()}")
    return result


def income_gap_drivers():
    """Compare division inflation rates across income groups by half-year.

    Parameters
    ----------
    None

    Returns
    -------
    pandas.DataFrame
        Division year-on-year inflation rates and the low-minus-high gap.
    """
    # 1. Read and inspect the income-group CPI file
    income = pd.read_csv(PROCESSED / "cpi_income_groups_long.csv")
    monthly = pd.read_csv(PROCESSED / "cpi_monthly_long.csv")
    income["date"] = pd.to_datetime(income["date"], format="%Y-%m-%d")
    print(income.head())
    income.info()

    # 2. Use the monthly CPI labels to exclude special aggregates from level 1
    division_names = monthly.loc[
        monthly["level_name"] == "division", "series"
    ].unique()
    selected = income[
        (income["level"] == 1)
        & income["series"].isin(division_names)
        & (income["period"] >= "2019 1H")
    ].copy()
    # 3. Reshape so each income group's rate is a separate column
    result = selected.pivot(
        index=["period", "series"], columns="income_group", values="yoy_pct"
    ).reset_index()
    result.columns.name = None
    result = result[
        ["period", "series", "Lowest 20%", "Middle 60%", "Highest 20%"]
    ].sort_values(["period", "series"]).reset_index(drop=True)
    result["rate_gap_low_minus_high_pp"] = (
        result["Lowest 20%"] - result["Highest 20%"]
    )

    # TODO: Add weighted income-group contributions when the group weights file exists.

    # 4. Validate the output before saving it
    assert not result.duplicated(["period", "series"]).any(), (
        "duplicate income-group division rows"
    )
    assert (result["period"] >= "2019 1H").all(), "periods before 2019 1H found"
    assert result.groupby("period")["series"].nunique().eq(DIVISION_COUNT).all(), (
        "each period must have exactly 10 divisions"
    )

    # 5. Store and share the table
    TABLES.mkdir(parents=True, exist_ok=True)
    result.to_csv(TABLES / "income_gap_drivers.csv", index=False)
    print(
        f"Saved {len(result):,} rows, {result['period'].min()} "
        f"to {result['period'].max()}"
    )
    return result


def behind_the_numbers():
    """Create indexed Private Transport, COE, Accommodation, and rent comparisons.

    Parameters
    ----------
    None

    Returns
    -------
    tuple of pandas.DataFrame
        Private Transport and COE table, followed by accommodation and HDB rent.
    """
    # 1. Read and inspect CPI, COE, and HDB rent data
    monthly = pd.read_csv(PROCESSED / "cpi_monthly_long.csv")
    coe = pd.read_csv(PROCESSED / "coe_monthly.csv")
    rents = pd.read_csv(PROCESSED / "hdb_rents_monthly.csv")
    for frame in [monthly, coe, rents]:
        frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
        print(frame.head())
        frame.info()

    # 2. Average Category A and B COE premiums by month
    category_ab = coe[coe["vehicle_class"].isin(["Category A", "Category B"])]
    coe_counts = category_ab.groupby("date")["vehicle_class"].nunique()
    assert coe_counts.eq(2).all(), "a month is missing Category A or B COE data"
    coe_monthly = (
        category_ab.groupby("date", as_index=False)
        .agg(coe_premium=("premium", "mean"))
    )

    # 3. Select the Private Transport group CPI and the Accommodation group CPI
    private_transport = monthly.loc[
        (monthly["series"] == "Private Transport")
        & (monthly["level_name"] == "group")
        & (monthly["date"] >= COMPARISON_START),
        ["date", "cpi", "parent"],
    ].rename(columns={"cpi": "transport_cpi"})
    accommodation = monthly.loc[
        (monthly["series"] == "Accommodation")
        & (monthly["level_name"] == "group")
        & (monthly["date"] >= COMPARISON_START),
        ["date", "cpi"],
    ].rename(columns={"cpi": "accommodation_cpi"})
    all_rents = rents.loc[
        (rents["flat_type"] == "ALL")
        & (rents["date"] >= COMPARISON_START),
        ["date", "median_rent"],
    ]
    assert len(private_transport) > 0, "no Private Transport CPI months found"
    assert private_transport["parent"].eq("Transport").all(), (
        "Private Transport must have Transport as its parent"
    )
    assert private_transport["transport_cpi"].notna().all(), (
        "missing Private Transport CPI values"
    )
    assert not private_transport.duplicated(["date"]).any(), (
        "duplicate Private Transport CPI month"
    )
    assert not accommodation.duplicated(["date"]).any(), (
        "duplicate Accommodation CPI month"
    )
    assert not all_rents.duplicated(["date"]).any(), "duplicate HDB rent month"

    # 4. Combine each pair of monthly series, then set the February 2021 index to 100
    transport_table = pd.merge(
        private_transport[["date", "transport_cpi"]],
        coe_monthly,
        on="date",
        how="inner",
        validate="one_to_one",
    )
    accommodation_table = pd.merge(
        accommodation, all_rents, on="date", how="inner", validate="one_to_one"
    )
    transport_base = transport_table.loc[
        transport_table["date"] == COMPARISON_START
    ]
    accommodation_base = accommodation_table.loc[
        accommodation_table["date"] == COMPARISON_START
    ]
    assert len(transport_base) == 1, (
        "February 2021 Private Transport/COE baseline is missing"
    )
    assert len(accommodation_base) == 1, (
        "February 2021 Accommodation/HDB baseline is missing"
    )
    transport_table["transport_cpi_index"] = (
        transport_table["transport_cpi"] / transport_base["transport_cpi"].iloc[0] * 100
    )
    transport_table["coe_premium_index"] = (
        transport_table["coe_premium"] / transport_base["coe_premium"].iloc[0] * 100
    )
    transport_table = transport_table[
        ["date", "transport_cpi_index", "coe_premium_index"]
    ].sort_values("date").reset_index(drop=True)
    accommodation_table["accommodation_cpi_index"] = (
        accommodation_table["accommodation_cpi"]
        / accommodation_base["accommodation_cpi"].iloc[0]
        * 100
    )
    accommodation_table["hdb_rent_index"] = (
        accommodation_table["median_rent"]
        / accommodation_base["median_rent"].iloc[0]
        * 100
    )
    accommodation_table = accommodation_table[
        ["date", "accommodation_cpi_index", "hdb_rent_index"]
    ].sort_values("date").reset_index(drop=True)

    # 5. Validate both output tables before saving them
    assert not transport_table.duplicated(["date"]).any(), (
        "duplicate Private Transport/COE date"
    )
    assert not accommodation_table.duplicated(["date"]).any(), (
        "duplicate accommodation date"
    )
    assert transport_table.loc[
        transport_table["date"] == COMPARISON_START,
        ["transport_cpi_index", "coe_premium_index"],
    ].eq(100).all().all(), (
        "Private Transport/COE comparison baseline should equal 100"
    )
    assert accommodation_table.loc[
        accommodation_table["date"] == COMPARISON_START,
        ["accommodation_cpi_index", "hdb_rent_index"],
    ].eq(100).all().all(), "accommodation comparison baseline should equal 100"

    # 6. Store and share the tables
    TABLES.mkdir(parents=True, exist_ok=True)
    transport_table.to_csv(TABLES / "transport_vs_coe.csv", index=False)
    accommodation_table.to_csv(
        TABLES / "accommodation_vs_hdb_rent.csv", index=False
    )
    print(
        f"Saved {len(transport_table):,} Private Transport/COE rows, "
        f"{transport_table['date'].min():%b %Y} to "
        f"{transport_table['date'].max():%b %Y}"
    )
    print(
        f"Saved {len(accommodation_table):,} accommodation rows, "
        f"{accommodation_table['date'].min():%b %Y} to "
        f"{accommodation_table['date'].max():%b %Y}"
    )
    return transport_table, accommodation_table


def key_findings():
    """Write a plain-English summary using the saved analysis tables.

    Parameters
    ----------
    None

    Returns
    -------
    str
        Plain-English findings saved to the key findings file.
    """
    # 1. Read the result tables needed for the summary
    inflation = pd.read_csv(TABLES / "inflation_by_category.csv")
    contributions_table = pd.read_csv(TABLES / "contributions_monthly.csv")
    surge_vs_cooling_table = pd.read_csv(TABLES / "surge_vs_cooling.csv")
    income_gaps = pd.read_csv(TABLES / "income_group_inflation_gaps.csv")
    income_gap_drivers_table = pd.read_csv(TABLES / "income_gap_drivers.csv")
    residuals = pd.read_csv(TABLES / "contribution_residual_check.csv")
    sensitivity = pd.read_csv(TABLES / "weight_sensitivity.csv")
    transport_table = pd.read_csv(TABLES / "transport_vs_coe.csv")
    inflation["date"] = pd.to_datetime(inflation["date"], format="%Y-%m-%d")
    contributions_table["date"] = pd.to_datetime(
        contributions_table["date"], format="%Y-%m-%d"
    )
    residuals["date"] = pd.to_datetime(residuals["date"], format="%Y-%m-%d")
    sensitivity["date"] = pd.to_datetime(
        sensitivity["date"], format="%Y-%m-%d"
    )
    transport_table["date"] = pd.to_datetime(
        transport_table["date"], format="%Y-%m-%d"
    )
    print(inflation.head())
    inflation.info()

    # 2. Find peak headline inflation and the top three contributions
    headline = inflation[inflation["series"] == "All Items"].dropna(
        subset=["yoy_pct"]
    )
    peak_headline = headline.loc[headline["yoy_pct"].idxmax()]
    latest_date = headline["date"].max()
    latest_headline = headline.loc[headline["date"] == latest_date].iloc[0]
    later_period_contributions = contributions_table[
        (contributions_table["date"] >= pd.Timestamp("2025-01-01"))
        & (contributions_table["date"] == latest_date)
    ].nlargest(3, "contribution_pp")
    earlier_period_contributions = contributions_table[
        (contributions_table["date"] >= pd.Timestamp("2019-01-01"))
        & (contributions_table["date"] <= pd.Timestamp("2023-12-01"))
        & (contributions_table["date"] == peak_headline["date"])
    ].nlargest(3, "contribution_pp")
    assert len(later_period_contributions) == 3, (
        "latest month needs three divisions in the 2025 onward period"
    )
    assert len(earlier_period_contributions) == 3, (
        "peak month needs three divisions in the 2019-2023 period"
    )

    # 3. Find cumulative category price changes and latest income-group rates
    category_cpi = inflation[inflation["series"] != "All Items"].sort_values(
        ["series", "date"]
    )
    assert not category_cpi.empty, "no category CPI values available"
    assert category_cpi[["series", "date", "cpi"]].notna().all().all(), (
        "missing category CPI values"
    )
    category_first = category_cpi.groupby("series", as_index=False).first()
    category_last = category_cpi.groupby("series", as_index=False).last()
    assert category_first["date"].nunique() == 1, (
        "categories must share a common start date"
    )
    assert category_last["date"].nunique() == 1, (
        "categories must share a common latest date"
    )
    category_changes = category_first[["series", "cpi"]].merge(
        category_last[["series", "cpi"]],
        on="series",
        how="inner",
        validate="one_to_one",
        suffixes=("_first", "_last"),
    )
    category_changes["change_pct"] = (
        category_changes["cpi_last"] / category_changes["cpi_first"] - 1
    ) * 100
    top_cumulative_categories = category_changes.nlargest(3, "change_pct")
    assert len(top_cumulative_categories) == 3, (
        "fewer than three categories have cumulative price changes"
    )

    latest_income = income_gaps.sort_values("period").iloc[-1]
    latest_period = latest_income["period"]
    latest_driver_rows = income_gap_drivers_table.loc[
        income_gap_drivers_table["period"] == latest_period
    ].copy()
    assert len(latest_driver_rows) == DIVISION_COUNT, (
        "latest half-year must have exactly 10 category gaps"
    )
    assert latest_driver_rows["rate_gap_low_minus_high_pp"].notna().all(), (
        "missing latest half-year category gaps"
    )
    largest_negative_gaps = latest_driver_rows.nsmallest(
        2, "rate_gap_low_minus_high_pp"
    )
    largest_positive_gap = latest_driver_rows.nlargest(
        1, "rate_gap_low_minus_high_pp"
    ).iloc[0]
    assert largest_negative_gaps["rate_gap_low_minus_high_pp"].lt(0).all(), (
        "latest half-year must have two negative category gaps"
    )
    assert largest_positive_gap["rate_gap_low_minus_high_pp"] > 0, (
        "latest half-year must have a positive category gap"
    )
    assert latest_income["period"] == income_gap_drivers_table["period"].max(), (
        "overall and category income gaps must use the same latest half-year"
    )

    # 4. Summarize the residual check and weight sensitivity
    largest_residual = residuals.loc[residuals["residual_pp"].abs().idxmax()]
    residual_share = (residuals["residual_pp"].abs() < 0.3).mean() * 100
    monthly_rankings = []
    for _, month in sensitivity.groupby("date"):
        top_2019 = month.nsmallest(3, "rank_2019w")["series"].tolist()
        top_2024 = month.nsmallest(3, "rank_2024w")["series"].tolist()
        monthly_rankings.append((month["date"].iloc[0], top_2019 == top_2024))
    assert monthly_rankings, "no weight sensitivity months available"
    latest_months_start = None
    next_expected_date = sensitivity["date"].max()
    for date, rankings_match in reversed(monthly_rankings):
        if date != next_expected_date or not rankings_match:
            break
        latest_months_start = date
        next_expected_date -= pd.DateOffset(months=1)
    assert latest_months_start is not None, (
        "latest month does not have matching top-three rankings"
    )
    differing_2025_months = [
        date
        for date, rankings_match in monthly_rankings
        if date.year == 2025 and not rankings_match
    ]
    assert differing_2025_months, "no differing top-three rankings in 2025"
    sensitivity_sentence = (
        f"- The top three ranking is the same under both sets of weights in the "
        f"latest months (from {latest_months_start:%B %Y} onward), but differs "
        "in some months of 2025 and early 2026, so findings about the latest "
        "month are robust, "
        "while no category is claimed to be the top contributor throughout "
        "2025-2026."
    )

    # 5. Build one short sentence for each dashboard page from saved tables
    later_period_top_text = "; ".join(
        f"{row.series} contributed {row.contribution_pp:.2f} pp"
        for row in later_period_contributions.itertuples(index=False)
    )
    earlier_period_top_text = "; ".join(
        f"{row.series} contributed {row.contribution_pp:.2f} pp"
        for row in earlier_period_contributions.itertuples(index=False)
    )

    latest_top_categories = ", ".join(
        later_period_contributions["series"].iloc[:2]
    ) + f", and {later_period_contributions['series'].iloc[2]}"
    surge_top = surge_vs_cooling_table.nsmallest(3, "surge_rank")["series"].tolist()
    cooling_top = surge_vs_cooling_table.nsmallest(3, "cooling_rank")["series"].tolist()
    surge_top_text = ", ".join(surge_top[:2]) + f", and {surge_top[2]}"
    cooling_top_text = ", ".join(cooling_top[:2]) + f", and {cooling_top[2]}"
    surge_cooling_sentence = (
        f"{surge_top_text} ranked highest in the 2022-23 surge, while "
        f"{cooling_top_text} ranked highest in the 2024-{latest_date:%y} cooling."
    )
    cumulative_start = category_first["date"].iloc[0]
    top_cumulative_names = top_cumulative_categories["series"].tolist()
    top_cumulative_values = top_cumulative_categories["change_pct"].tolist()
    top_cumulative_text = (
        f"{top_cumulative_names[0]} ({top_cumulative_values[0]:.1f}%), "
        f"{top_cumulative_names[1]} ({top_cumulative_values[1]:.1f}%), and "
        f"{top_cumulative_names[2]} ({top_cumulative_values[2]:.1f}%)"
    )
    cumulative_sentence = (
        f"Since {cumulative_start:%B %Y}, {top_cumulative_text} had the "
        f"largest category CPI increases through {latest_date:%B %Y}."
    )
    negative_gap_text = (
        f"{largest_negative_gaps.iloc[0]['series']} "
        f"({largest_negative_gaps.iloc[0]['rate_gap_low_minus_high_pp']:+.2f} pp) "
        f"and {largest_negative_gaps.iloc[1]['series']} "
        f"({largest_negative_gaps.iloc[1]['rate_gap_low_minus_high_pp']:+.2f} pp)"
    )
    overall_gap = income_gaps.loc[income_gaps["period"] == latest_period].iloc[0][
        "gap_low_minus_high_pp"
    ]
    income_gap_sentence = (
        f"In {latest_period}, the overall low-minus-high gap was {overall_gap:+.2f} pp; "
        f"the largest category gaps were {negative_gap_text} on the negative side "
        f"and {largest_positive_gap['series']} "
        f"({largest_positive_gap['rate_gap_low_minus_high_pp']:+.2f} pp) "
        "on the positive side."
    )
    transport_latest = transport_table.sort_values("date").iloc[-1]
    transport_first = transport_table.sort_values("date").iloc[0]
    assert transport_first["date"] == COMPARISON_START, (
        "Private Transport/COE comparison must start in February 2021"
    )
    assert transport_table[
        ["transport_cpi_index", "coe_premium_index"]
    ].notna().all().all(), "missing Private Transport/COE index values"
    private_transport_direction = (
        transport_latest["transport_cpi_index"]
        - transport_first["transport_cpi_index"]
    )
    coe_direction = (
        transport_latest["coe_premium_index"]
        - transport_first["coe_premium_index"]
    )
    if private_transport_direction > 0 and coe_direction > 0:
        movement_text = "both rose"
    elif private_transport_direction < 0 and coe_direction < 0:
        movement_text = "both fell"
    elif private_transport_direction == 0 and coe_direction == 0:
        movement_text = "both remained unchanged"
    else:
        movement_text = "moved in opposite directions"
    behind_sentence = (
        f"Since February 2021, the Private Transport CPI and COE premium indexes "
        f"{movement_text}, reaching {transport_latest['transport_cpi_index']:.1f} "
        f"and {transport_latest['coe_premium_index']:.1f}, respectively, in "
        f"{transport_latest['date']:%B %Y}."
    )
    page_findings = [
        (
            "**Overview & Category Explorer:** "
            f"Headline year-on-year inflation was {latest_headline['yoy_pct']:.2f}% "
            f"in {latest_date:%B %Y}, with {latest_top_categories} the top "
            "contributing categories."
        ),
        f"**What Drove Inflation?:** {surge_cooling_sentence}",
        f"**Cumulative Price Changes:** {cumulative_sentence}",
        f"**Rich vs Poor:** {income_gap_sentence}",
        f"**Behind the Numbers:** {behind_sentence}",
    ]
    page_bodies = [finding.split(":** ", 1)[1] for finding in page_findings]
    assert len(page_findings) == 5, "exactly five dashboard page findings are required"
    assert all(len(sentence.split()) < 40 for sentence in page_bodies), (
        "each dashboard page finding must be under 40 words"
    )

    # 6. Write the findings in descriptive wording only
    findings = [
        "# Key Findings",
        "",
        (
            f"- Peak headline year-on-year inflation since 2019 was "
            f"{peak_headline['yoy_pct']:.2f}% in {peak_headline['date']:%B %Y}."
        ),
        (
            f"- In the 2019-2023 period, the top contributing divisions in the "
            f"peak headline month ({peak_headline['date']:%B %Y}), using 2019 "
            f"basket weights, ranked as follows: {earlier_period_top_text}."
        ),
        (
            f"- In the 2025 onward period, the top contributing divisions in the "
            f"latest available CPI month ({latest_date:%B %Y}), using 2024 "
            f"basket weights, ranked as follows: {later_period_top_text}."
        ),
        (
            "- The CPI basket changed in 2024, so contribution values in these "
            "periods are not fully comparable; across periods, comparisons are "
            "limited to inflation rates and category rankings, not contribution sizes."
        ),
        (
            f"- Headline year-on-year inflation in the latest available month "
            f"({latest_date:%B %Y}) was {latest_headline['yoy_pct']:.2f}%."
        ),
        (
            f"- In {latest_income['period']}, year-on-year All Items inflation was "
            f"{latest_income['Lowest 20%']:.2f}% for the Lowest 20%, "
            f"{latest_income['Middle 60%']:.2f}% for the Middle 60%, and "
            f"{latest_income['Highest 20%']:.2f}% for the Highest 20%."
        ),
        (
            f"- The low-minus-high gap was "
            f"{latest_income['gap_low_minus_high_pp']:.2f} pp, and the "
            f"middle-minus-high gap was "
            f"{latest_income['gap_middle_minus_high_pp']:.2f} pp."
        ),
        (
            f"- The residual was below 0.3 pp in {residual_share:.1f}% of months. "
            f"The largest absolute residual was "
            f"{abs(largest_residual['residual_pp']):.2f} pp in "
            f"{largest_residual['date']:%B %Y}."
        ),
        (
            "- The residual is close to zero in all years except 2019 and 2024, "
            "which are the years when the comparison crosses a CPI basket change."
        ),
        sensitivity_sentence,
        "",
        "## Page findings",
        *page_findings,
    ]
    text = "\n".join(findings) + "\n"

    # 7. Validate the summary inputs and store the findings
    assert len(headline) > 0, "no headline inflation values available"
    assert len(income_gaps) > 0, "no income-group periods available"
    page_findings_index = findings.index("## Page findings")
    prose = "\n".join(findings[2:page_findings_index] + page_bodies)
    assert "caused" not in prose.lower()
    assert "drove" not in prose.lower()
    assert "led to" not in prose.lower()
    assert "is correlated with" not in prose.lower()
    assert "accounts for" not in prose.lower()
    assert "explains" not in prose.lower()
    TABLES.mkdir(parents=True, exist_ok=True)
    (TABLES / "key_findings.md").write_text(text, encoding="utf-8")
    print(
        f"Saved key findings for {headline['date'].min():%b %Y} "
        f"to {latest_date:%b %Y}"
    )
    return text


if __name__ == "__main__":
    category_inflation()
    contributions()
    surge_vs_cooling()
    residual_check()
    weight_sensitivity()
    income_group_gaps()
    income_gap_drivers()
    behind_the_numbers()
    key_findings()
