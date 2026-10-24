# Who Feels Inflation Most? Singapore CPI by Category and Household Income
## Data
All data are public aggregate statistics with no personal information.

| File in data/raw/ | Source | Downloaded | Licence |
| --- | --- | --- | --- |
| cpi_2024base_monthly.csv | CPI, 2024 as Base Year, Monthly, data.gov.sg (SingStat) | 24 Oct 2026 | Singapore Open Data Licence |
| cpi_by_income_group_lowest/middle/highest.csv | CPI by Household Income Group, 2024 as Base Year, Half-Yearly, SingStat Table Builder | 24 Oct 2026 | SingStat terms of use |
| cpi_weights_2024.csv | Typed from Appendix III (pp. 29-36) of SingStat's Rebasing of the CPI (2024 as Base Year) information paper, saved as cpi_rebasing_paper_2024.pdf | 24 Oct 2026 | SingStat terms of use |
| coe_bidding_results.csv |	COE Bidding Results / Prices, LTA, data.gov.sg | 24 Oct 2026 | Singapore Open Data Licence |
| hdb_rents.csv | Renting Out of Flats from Jan 2021, HDB, data.gov.sg | 24 Oct 2026 | Singapore Open Data Licence |

### How to rebuild the processed data
```bash
pip install -r requirements.txt
python src/wrangle.py
```

This reads data/raw/ and writes 5 files to data/processed/:

- cpi_monthly_long.csv: one row per CPI series per month (date, series, level, level_name, parent, cpi, yoy_pct, mom_pct)
- cpi_income_groups_long.csv: CPI for the lowest 20%, middle 60% and highest 20% of households, half-yearly, with yoy_pct
- cpi_weights_2024.csv: each category's weight per 10,000 and % share of spending
- coe_monthly.csv: average COE premium per month for each category
- hdb_rents_monthly.csv: median HDB rent per month by flat type

### Data limitations
- CPI measures price changes for an average basket, not price levels.
- Income-group CPI is only half-yearly.
- COE has no data for Apr-Jun 2020 (bidding suspended during the circuit breaker).
- HDB rents are owner-declared and not verified by HDB; the 1-room median is based on very few rentals.