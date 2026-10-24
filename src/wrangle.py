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


if __name__ == "__main__":
    clean_cpi()