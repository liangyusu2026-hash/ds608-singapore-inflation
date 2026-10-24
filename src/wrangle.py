from pathlib import Path

import pandas as pd

# Paths are relative to the project folder, so the script works on any computer
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

# Each indent of 4 spaces in the SingStat table is one level down the tree
LEVEL_NAMES = {0: "all items", 1: "division", 2: "group", 3: "class"}

# Rows that are not part of the normal tree (summing them with the divisions double counts)
SPECIAL_SERIES = {
    "Food Excl Food & Beverage Serving Services",
    "Food & Beverage Serving Services",
    "All Items Less Accommodation",
    "All Items Less Imputed Rentals For Housing",
}


def clean_cpi():
    # 1. Read the raw file exactly as downloaded
    raw = pd.read_csv(RAW / "cpi_2024base_monthly.csv")

    # 2. Work out each series' level from its leading spaces, then strip the spaces
    indent = raw["DataSeries"].str.len() - raw["DataSeries"].str.lstrip().str.len()
    raw["level"] = indent // 4
    raw["series"] = raw["DataSeries"].str.strip()

    # 3. Find each series' parent (the nearest row above it with a smaller level)
    parents, stack = [], {}
    for name, level in zip(raw["series"], raw["level"]):
        parents.append(stack.get(level - 1))
        stack[level] = name
    raw["parent"] = parents

    raw["level_name"] = raw["level"].map(LEVEL_NAMES)
    raw.loc[raw["series"].isin(SPECIAL_SERIES), "level_name"] = "special aggregate"

    # 4. Wide to long: one row per series per month
    long = raw.drop(columns="DataSeries").melt(
        id_vars=["series", "level", "level_name", "parent"],
        var_name="month",
        value_name="cpi",
    )

    # 5. Fix types: "2026Aug" -> date, "na" -> missing number
    long["date"] = pd.to_datetime(long["month"], format="%Y%b")
    long["cpi"] = pd.to_numeric(long["cpi"], errors="coerce")
    long = long.dropna(subset=["cpi"]).drop(columns="month")

    # 6. Sort and add inflation rates
    long = long.sort_values(["series", "date"]).reset_index(drop=True)
    long["yoy_pct"] = long.groupby("series")["cpi"].pct_change(12, fill_method=None) * 100
    long["mom_pct"] = long.groupby("series")["cpi"].pct_change(1, fill_method=None) * 100

    # 7. Quick checks so problems show up early
    assert not long.duplicated(["series", "date"]).any(), "duplicate series-month rows"
    base = long[long["date"].dt.year == 2024].groupby("series")["cpi"].mean()
    assert base.between(99.5, 100.5).all(), "2024 average should be about 100"

    cols = ["date", "series", "level", "level_name", "parent", "cpi", "yoy_pct", "mom_pct"]
    long = long[cols]
    PROCESSED.mkdir(parents=True, exist_ok=True)
    long.to_csv(PROCESSED / "cpi_monthly_long.csv", index=False)
    print(f"Saved {len(long):,} rows, {long['series'].nunique()} series, "
          f"{long['date'].min():%b %Y} to {long['date'].max():%b %Y}")
    return long

def clean_income_groups():
    # SingStat Table Builder files have 10 lines of notes above the table
    # and footnotes below it, so we read only the table part
    frames = []
    for group in ["lowest", "middle", "highest"]:
        raw = pd.read_csv(RAW / f"cpi_by_income_group_{group}.csv", skiprows=10)
        raw = raw.dropna(subset=["Data Series"])
        last_row = raw.index[raw["Data Series"] == "All Items Less Imputed Rentals For Housing"][0]
        raw = raw.loc[:last_row]

        # Here each level is indented by 2 spaces (the monthly file used 4)
        indent = raw["Data Series"].str.len() - raw["Data Series"].str.lstrip().str.len()
        raw["level"] = indent // 2
        raw["series"] = raw["Data Series"].str.strip()

        long = raw.drop(columns="Data Series").melt(
            id_vars=["series", "level"], var_name="period", value_name="cpi"
        )
        long["period"] = long["period"].str.strip()            # "2026 1H "
        long["cpi"] = pd.to_numeric(long["cpi"], errors="coerce")
        long = long.dropna(subset=["cpi"])
        long["income_group"] = {"lowest": "Lowest 20%", "middle": "Middle 60%",
                                "highest": "Highest 20%"}[group]
        frames.append(long)

    df = pd.concat(frames, ignore_index=True)

    # "2026 1H" -> 1 Jan 2026, "2026 2H" -> 1 Jul 2026 (start of each half-year)
    year = df["period"].str[:4]
    month = df["period"].str[-2:].map({"1H": "01", "2H": "07"})
    df["date"] = pd.to_datetime(year + "-" + month + "-01")

    # Year-on-year inflation = change versus the same half one year (2 periods) earlier
    df = df.sort_values(["income_group", "series", "date"]).reset_index(drop=True)
    df["yoy_pct"] = df.groupby(["income_group", "series"])["cpi"].pct_change(2, fill_method=None) * 100

    assert not df.duplicated(["income_group", "series", "date"]).any()
    cols = ["date", "period", "income_group", "series", "level", "cpi", "yoy_pct"]
    df[cols].to_csv(PROCESSED / "cpi_income_groups_long.csv", index=False)
    print(f"Saved {len(df):,} income-group rows, {df['period'].min()} to {df['period'].max()}")
    return df


def clean_weights():
    # Typed from Appendix III of SingStat's 2024 CPI rebasing paper (per 10,000)
    w = pd.read_csv(RAW / "cpi_weights_2024.csv")
    w["share_2024_pct"] = w["weight_2024"] / 100
    divisions = w[(w["level"] == 1) & ~w["series"].isin(SPECIAL_SERIES)]
    assert divisions["weight_2024"].sum() == 10000, "division weights should add to 10,000"
    w.to_csv(PROCESSED / "cpi_weights_2024.csv", index=False)
    print(f"Saved {len(w)} weights")
    return w


def clean_coe():
    coe = pd.read_csv(RAW / "coe_bidding_results.csv")

    # Numbers like "1,007" are stored as text, so remove the commas first
    for col in ["bids_success", "bids_received"]:
        coe[col] = pd.to_numeric(coe[col].astype(str).str.replace(",", ""))

    # There are 2 bidding rounds a month: average them into one monthly premium
    coe["date"] = pd.to_datetime(coe["month"], format="%Y-%m")
    monthly = (coe.groupby(["date", "vehicle_class"], as_index=False)
                  .agg(premium=("premium", "mean"), quota=("quota", "sum")))
    monthly.to_csv(PROCESSED / "coe_monthly.csv", index=False)
    print(f"Saved {len(monthly):,} COE rows, {monthly['date'].min():%b %Y} to {monthly['date'].max():%b %Y}")
    return monthly


def clean_hdb_rents():
    hdb = pd.read_csv(RAW / "hdb_rents.csv")
    hdb["date"] = pd.to_datetime(hdb["rent_approval_date"], format="%Y-%m")

    # One row per rental is too detailed for the dashboard:
    # keep the median rent per month for each flat type, plus all flats together
    by_type = (hdb.groupby(["date", "flat_type"], as_index=False)
                  .agg(median_rent=("monthly_rent", "median"), n_rentals=("monthly_rent", "size")))
    all_flats = (hdb.groupby("date", as_index=False)
                    .agg(median_rent=("monthly_rent", "median"), n_rentals=("monthly_rent", "size")))
    all_flats["flat_type"] = "ALL"
    monthly = pd.concat([by_type, all_flats], ignore_index=True).sort_values(["flat_type", "date"])
    monthly.to_csv(PROCESSED / "hdb_rents_monthly.csv", index=False)
    print(f"Saved {len(monthly):,} HDB rent rows from {len(hdb):,} rentals")
    return monthly

if __name__ == "__main__":
    clean_cpi()
    clean_income_groups()
    clean_weights()
    clean_coe()
    clean_hdb_rents()