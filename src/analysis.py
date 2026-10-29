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
    analysis_rows = monthly[monthly["date"] >= ANALYSIS_START].copy()

    # 4. Match each division with All Items CPI from the same month
    division_rows = analysis_rows[
        analysis_rows["series"].isin(division_names)
    ].merge(
        analysis_rows.loc[
            analysis_rows["series"] == "All Items",
            ["date", "cpi_12_months_ago"],
        ].rename(columns={"cpi_12_months_ago": "all_items_cpi_12_months_ago"}),
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
    division_rows["weight_note"] = ""
    in_2024 = division_rows["date"].dt.year == 2024
    division_rows.loc[in_2024, "weight_note"] = "approximate (basket change)"
    division_rows["contribution_pp"] = (
        (division_rows["weight_used"] / 10000)
        * (
            division_rows["cpi"]
            - division_rows["cpi_12_months_ago"]
        )
        / division_rows["all_items_cpi_12_months_ago"]
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
    analysis_rows = monthly[monthly["date"] >= pd.Timestamp("2025-01-01")]
    division_rows = analysis_rows[
        analysis_rows["series"].isin(division_names)
    ].merge(
        analysis_rows.loc[
            analysis_rows["series"] == "All Items",
            ["date", "cpi_12_months_ago"],
        ].rename(columns={"cpi_12_months_ago": "all_items_cpi_12_months_ago"}),
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
    cpi_change = (
        division_rows["cpi"] - division_rows["cpi_12_months_ago"]
    ) / division_rows["all_items_cpi_12_months_ago"] * 100
    division_rows["contribution_2019w_pp"] = (
        division_rows["weight_2019"] / 10000
    ) * cpi_change
    division_rows["contribution_2024w_pp"] = (
        division_rows["weight_2024"] / 10000
    ) * cpi_change
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
    """Create indexed CPI comparisons with COE premiums and HDB rents.

    Parameters
    ----------
    None

    Returns
    -------
    tuple of pandas.DataFrame
        Transport and COE table, followed by accommodation and HDB rent table.
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

    # 3. Select the Transport CPI series and the Accommodation group CPI
    transport = monthly.loc[
        (monthly["series"] == "Transport")
        & (monthly["level_name"] == "division")
        & (monthly["date"] >= COMPARISON_START),
        ["date", "cpi"],
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
    assert not transport.duplicated(["date"]).any(), "duplicate Transport CPI month"
    assert not accommodation.duplicated(["date"]).any(), (
        "duplicate Accommodation CPI month"
    )
    assert not all_rents.duplicated(["date"]).any(), "duplicate HDB rent month"

    # 4. Combine each pair of monthly series, then set the February 2021 index to 100
    transport_table = pd.merge(
        transport, coe_monthly, on="date", how="inner", validate="one_to_one"
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
    assert len(transport_base) == 1, "February 2021 Transport/COE baseline is missing"
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
    assert not transport_table.duplicated(["date"]).any(), "duplicate transport date"
    assert not accommodation_table.duplicated(["date"]).any(), (
        "duplicate accommodation date"
    )
    assert transport_table.loc[
        transport_table["date"] == COMPARISON_START,
        ["transport_cpi_index", "coe_premium_index"],
    ].eq(100).all().all(), "transport comparison baseline should equal 100"
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
        f"Saved {len(transport_table):,} transport rows, "
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
    income_gaps = pd.read_csv(TABLES / "income_group_inflation_gaps.csv")
    residuals = pd.read_csv(TABLES / "contribution_residual_check.csv")
    sensitivity = pd.read_csv(TABLES / "weight_sensitivity.csv")
    inflation["date"] = pd.to_datetime(inflation["date"], format="%Y-%m-%d")
    contributions_table["date"] = pd.to_datetime(
        contributions_table["date"], format="%Y-%m-%d"
    )
    residuals["date"] = pd.to_datetime(residuals["date"], format="%Y-%m-%d")
    sensitivity["date"] = pd.to_datetime(
        sensitivity["date"], format="%Y-%m-%d"
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

    # 3. Select the latest income-group rates and summarize the residual check
    latest_income = income_gaps.sort_values("period").iloc[-1]
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
        "in some months of 2025, so findings about the latest month are robust, "
        "while no category is claimed to be the top contributor throughout "
        "2025-2026."
    )

    later_period_top_text = "; ".join(
        f"{row.series} contributed {row.contribution_pp:.2f} pp"
        for row in later_period_contributions.itertuples(index=False)
    )
    earlier_period_top_text = "; ".join(
        f"{row.series} contributed {row.contribution_pp:.2f} pp"
        for row in earlier_period_contributions.itertuples(index=False)
    )

    # 4. Write the findings in descriptive wording only
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
            f"{largest_residual['residual_pp']:.2f} pp in "
            f"{largest_residual['date']:%B %Y}."
        ),
        (
            "- The largest residuals are in 2022, when prices of different "
            "categories moved very differently, so fixed basket weights are less exact."
        ),
        sensitivity_sentence,
    ]
    text = "\n".join(findings) + "\n"

    # 5. Validate the summary inputs and store the findings
    assert len(headline) > 0, "no headline inflation values available"
    assert len(income_gaps) > 0, "no income-group periods available"
    assert "caused" not in text.lower()
    assert "drove" not in text.lower()
    assert "led to" not in text.lower()
    assert "is correlated with" not in text.lower()
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
    residual_check()
    weight_sensitivity()
    income_group_gaps()
    income_gap_drivers()
    behind_the_numbers()
    key_findings()
