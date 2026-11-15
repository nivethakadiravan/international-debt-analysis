# 🌍 International Debt Analysis System

An end-to-end data analytics pipeline for the **World Bank International Debt Statistics**. Raw CSV data is cleaned with **Python/pandas**, explored in a **Jupyter EDA notebook** (Matplotlib and Seaborn), stored in a normalized **MySQL** database, queried with **30 SQL analytical queries**, and presented in an interactive **Streamlit + Plotly** dashboard.

**Domain:** Finance Analytics & Global Economic Data Analysis

```
 CSV (raw)  ──►  pandas cleaning  ──►  MySQL (3 tables + views)  ──►  SQL queries  ──►  Streamlit dashboard
 62,983 rows     1,345,046 records     countries · indicators ·        30 questions      7 pages, Plotly
 wide format     long format           debt_data                                         + EDA notebook
```

---

## Contents
1. [Key results](#key-results)
2. [Project structure](#project-structure)
3. [Setup & run](#setup--run)
4. [Data cleaning & preprocessing](#data-cleaning--preprocessing)
5. [Database design](#database-design)
6. [SQL analytical queries](#sql-analytical-queries)
7. [Dashboard](#dashboard)
8. [EDA & insights](#eda--insights)
9. [Design decisions](#design-decisions)

---

## Key results

| | |
|---|---|
| Total external debt, 120 countries (2024) | **$8.94 trillion**, 4.9× the 2000 level |
| Most indebted | China $2.42T · India $716B · Brazil $605B · Mexico $591B · Turkiye $515B |
| Least indebted | Tonga $173M · Timor-Leste $297M · Sao Tome and Principe $326M |
| Concentration | China = 27.1% of the total, top 10 = 68.2%, 18 countries = 80% |
| Heaviest burden (debt % of GNI) | Mozambique 351% · Mongolia 182% · Senegal 151% |
| Cost of debt | Interest payments +57% from 2020 to 2024, while debt grew only +10% |

The full analysis is in the [EDA Report](reports/EDA_Report.md).

## Project structure

```
international-debt-analysis/
├── data/
│   ├── raw/                         # Original World Bank CSV files (unchanged)
│   │   ├── IDS_ALLCountries_Data.csv
│   │   ├── IDS_CountryMetaData.csv  # region, income group
│   │   ├── IDS_SeriesMetaData.csv   # indicator definitions
│   │   └── ...
│   └── processed/                   # Output of the cleaning step
│       ├── countries_clean.csv
│       ├── indicators_clean.csv
│       ├── debt_data_clean.csv.gz   # 1.35 M rows (gzipped to stay under GitHub limits)
│       └── cleaning_report.json     # what was removed / fixed, with counts
├── notebooks/
│   └── 01_data_cleaning_and_eda.ipynb   # Data collection, cleaning, EDA (executed, with outputs)
├── reports/
│   ├── EDA_Report.md                # EDA write-up with insights
│   └── figures/                     # 13 charts produced by the notebook
├── sql/
│   ├── 01_schema.sql                # Database, tables, PK / FK, indexes
│   ├── 02_views.sql                 # Analysis views (defines "debt")
│   └── 03_analysis_queries.sql      # All 30 SQL questions
├── src/
│   ├── config.py                    # Paths & analysis constants
│   ├── cleaning.py                  # CSV → DataFrame → cleaned tables
│   ├── db.py                        # Python ↔ MySQL connection
│   ├── load_to_mysql.py             # Inserts cleaned data into MySQL
│   └── queries.py                   # The 30 queries (used by the dashboard)
├── scripts/export_queries.py        # Regenerates sql/03_analysis_queries.sql
├── app.py                           # Streamlit dashboard
├── run_pipeline.py                  # One command: clean + load
├── requirements.txt
└── .env.example
```

## Setup & run

**Prerequisites:** Python 3.10+ and MySQL 8.0+.

```bash
# 1. Install
git clone https://github.com/nivethakadiravan/international-debt-analysis.git
cd international-debt-analysis
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Database connection
cp .env.example .env              # then set DB_PASSWORD

# 3. Clean the data and load it into MySQL (about 30 seconds)
python run_pipeline.py

# 4. Dashboard
streamlit run app.py

# 5. (optional) EDA notebook
jupyter notebook notebooks/01_data_cleaning_and_eda.ipynb
```

Steps can also be run one at a time: `python -m src.cleaning`, then `python -m src.load_to_mysql`.

## Data cleaning & preprocessing

The logic lives in [`src/cleaning.py`](src/cleaning.py), and every step is logged to `cleaning_report.json`.

| Step | Detail |
|---|---|
| **CSV → DataFrame** | `pd.read_csv(..., encoding="latin-1")`. The file isn't valid UTF-8 because it contains `0xA0` bytes |
| **Text standardisation** | Strip padded codes (`"AFG       "` → `"AFG"`), replace non-breaking spaces |
| **Footer rows** | 5 removed ("Last Updated: 12/03/2025", etc.) |
| **Constant column** | `Counterpart-Area` is always "World", so it is dropped |
| **Duplicates** | Checked on full rows and on (country, series) keys. Only the blank footer lines repeated; no real data rows were duplicated |
| **Missing values** | 35.3% of cells are empty (19–22% per actual year, ~80% in projection years). They are **dropped, not imputed**, because a missing debt figure means "not reported", not 0 |
| **Missing metadata** | Ethiopia has no income group, so it is labelled "Not classified" |
| **Reshape** | Wide (33 year columns) → long (`country, indicator, year, value`) |
| **Type conversion** | Year → int, value → numeric (DECIMAL in MySQL), flags → 0/1 |
| **Aggregates** | 14 regions / income groups are flagged `is_aggregate = 1` so they are never added to country totals |
| **Enrichment** | Region and income group from country metadata. Unit and category (stock, interest, principal…) parsed from series names. Topic and definition from series metadata. `is_projection` = year > 2024 |
| **Validation** | The 4 debt components sum to total external debt (within 0.05%). Row counts in MySQL are checked against the DataFrames after loading |

## Database design

Database **`international_debt_db`**, normalized (3NF) star schema:

```
countries (1) ──< (many) debt_data (many) >── (1) indicators
```

| Table | Rows | Key columns |
|---|---|---|
| **countries** | 134 | `country_id` PK, `country_code` UNIQUE, region, income_group, `is_aggregate` |
| **indicators** | 576 | `indicator_id` PK, `indicator_code` UNIQUE, name, unit, category, topic, definition |
| **debt_data** | 1,345,046 | `debt_id` PK, `country_id` FK, `indicator_id` FK, year, value DECIMAL(22,4), `is_projection`; UNIQUE (country, indicator, year) |

Indexes on `(indicator_id, year)` and `year` cover the common access pattern: filter by indicator and year, then group by country.

**Views** ([`sql/02_views.sql`](sql/02_views.sql)):
- `v_country_debt`: each country's total external debt for every actual year
- `v_debt_latest`: all debt-stock indicators per country for 2024
- `v_top10_countries_debt`: SQL question 25

## SQL analytical queries

All 30 are in [`sql/03_analysis_queries.sql`](sql/03_analysis_queries.sql). They also run live on the dashboard's **SQL queries** page, where you can download each result as CSV.

| Level | # | Highlights |
|---|---|---|
| Basic | 1–10 | Distinct countries, counts, first 10 records, total global debt ($8.94T), > $1B records, min/max/avg |
| Intermediate | 11–20 | Debt per country, top 10, per indicator, lowest debtor (Tonga), above-average countries, `RANK()` |
| Advanced | 21–30 | % of global debt, top 3 per indicator (`ROW_NUMBER` + CTE), view, High/Medium/Low `CASE`, cumulative debt (window `SUM`), > 5% contributors, dominant indicator per country |

Every query runs in under a second on 1.35 M rows. For example, Q4 applies `LIMIT` in a sub-query *before* joining, which took it from 2.3 s to 6 ms.

## Dashboard

`streamlit run app.py`. Every page reads from MySQL. The sidebar filters by **year (2000–2024)**, **region** and **income group**.

| Page | What it shows |
|---|---|
| 📊 **Overview** | KPIs (total debt, change vs the previous year, top-10 share), trend, regional share, top / bottom 10, High / Medium / Low categories, auto-generated insights |
| 🏳️ **Country analysis** | Rank, share of global debt, debt % of GNI, debt service, 2000–2024 trend, composition donut, actual and scheduled principal & interest, searchable table of all indicators |
| 📈 **Indicator analysis** | Any of the 576 indicators: top N countries, trend over time, distribution by income group, definition |
| 🗺️ **Regions & income** | World map (US$ or % of GNI), region → country treemap, region and income-group tables |
| ⚖️ **Compare countries** | Multi-country trends (US$ or indexed to 2010 = 100) and a key-ratio table |
| 🧮 **SQL queries** | All 30 queries with their SQL, results and CSV download |
| 🔎 **Data explorer** | Pick countries, indicators and years (including projections), then view and download |

## EDA & insights

[`notebooks/01_data_cleaning_and_eda.ipynb`](notebooks/01_data_cleaning_and_eda.ipynb) holds the full analysis (13 charts), and [`reports/EDA_Report.md`](reports/EDA_Report.md) is the write-up. Main findings:

1. **Growth:** debt rose from $1.83T to $8.94T between 2000 and 2024 (6.8% a year).
2. **Concentration:** 18 countries hold 80% of the debt. The median country owes $12.8B against a mean of $74.5B.
3. **Regions:** East Asia & Pacific holds 38%. Sub-Saharan Africa has the most countries (45) but the smallest typical debt.
4. **Composition:** public & publicly guaranteed debt is 39.8% of the total and the largest component in 101 of 120 countries. China is the exception, with 54% short-term.
5. **Cost:** interest payments rose 57% in 2020–24 while the debt stock grew 10%, and new long-term lending fell.
6. **Burden ≠ size:** 9 countries owe more than 100% of GNI (Mozambique, Mongolia, Senegal…). Debt size and debt/GNI are almost uncorrelated (r = 0.11).

## Design decisions

- **How "debt" is measured.** The 576 indicators overlap: *total* contains *long-term*, which contains *PPG*, and so on. Adding them all up would count the same dollar many times. So a country's debt is **External debt stocks, total** (`DT.DOD.DECT.CD`), and composition uses its 4 non-overlapping parts. Indicator-level questions (Q14, Q21, Q23…) compare debt-stock indicators side by side, so they are never summed into one total.
- **Latest year = 2024.** 2025–2032 contain only scheduled repayments on existing debt. They are kept, but flagged `is_projection = 1` and excluded from "current debt".
- **Aggregates are kept but flagged.** They are useful as a cross-check (the World Bank's own "Low & middle income" total is $8.94T, which matches the sum of the 120 countries), but they are never mixed into country rankings.
- **No imputation.** Filling missing debt with 0 or with averages would invent liabilities, so missing values are dropped.
- **Single source of truth.** Cleaning lives in one module, and the 30 queries live in one Python file that the dashboard uses and that generates the `.sql` deliverable, so they can't drift apart.
