"""Read the analysis tables that the dashboard displays.

Each function reads one table from outputs/tables/ and returns it as a
DataFrame. Date columns are converted to datetime so they plot correctly.
"""
from pathlib import Path

import pandas as pd

# Paths are relative to the project folder, so the app works on any computer
ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"


def read_table_with_dates(file_name):
    """Read a table from outputs/tables/ and convert its date column."""
    table = pd.read_csv(TABLES / file_name)
    table["date"] = pd.to_datetime(table["date"])
    return table


def load_category_inflation():
    """Monthly CPI index and YoY inflation for All Items and the 10 divisions."""
    return read_table_with_dates("inflation_by_category.csv")


def load_contributions():
    """Monthly contribution of each division to headline inflation (pp)."""
    return read_table_with_dates("contributions_monthly.csv")


def load_income_group_gaps():
    """Half-yearly All Items inflation for each income group, with gaps."""
    return pd.read_csv(TABLES / "income_group_inflation_gaps.csv")


def load_income_gap_drivers():
    """Half-yearly division inflation gaps between income groups."""
    return pd.read_csv(TABLES / "income_gap_drivers.csv")


def load_transport_vs_coe():
    """Private Transport CPI and COE premiums, indexed to Feb 2021 = 100."""
    return read_table_with_dates("transport_vs_coe.csv")


def load_accommodation_vs_rent():
    """Accommodation CPI and HDB median rents, indexed to Feb 2021 = 100."""
    return read_table_with_dates("accommodation_vs_hdb_rent.csv")


def load_residual_check():
    """Monthly gap between headline inflation and summed contributions."""
    return read_table_with_dates("contribution_residual_check.csv")
