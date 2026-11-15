"""Data collection + cleaning + preprocessing for the IDS dataset.

Steps (each one is recorded in data/processed/cleaning_report.json):

 1. Load the raw CSV into a pandas DataFrame (latin-1 encoding).
 2. Standardise text: strip padding from codes/names, replace non-breaking spaces.
 3. Drop footer / blank rows (e.g. "Last Updated: ...").
 4. Drop constant columns (Counterpart-Area is always "World").
 5. Remove duplicate records.
 6. Reshape wide (one column per year) -> long (country, indicator, year, value).
 7. Convert data types and drop missing values (no imputation - a missing debt
    figure is "not reported", not zero).
 8. Enrich: country region/income group, indicator category/unit/topic,
    aggregate flag (regions & income groups are NOT countries), projection flag.

Run:  python -m src.cleaning
"""

from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from src import config

# Measurement prefix in IDS series names -> readable category
CATEGORY_NAMES = {
    "DOD": "Debt outstanding (stock)",
    "DIS": "Disbursements",
    "AMT": "Principal repayments",
    "INT": "Interest payments",
    "TDS": "Total debt service",
    "NFL": "Net flows",
    "NTR": "Net transfers",
    "COM": "Commitments",
    "UND": "Undisbursed debt",
    "DRS": "Balance of payments (DRS)",
}


def _clean_text(s: pd.Series) -> pd.Series:
    return (s.astype("string")
             .str.replace("\xa0", " ", regex=False)
             .str.replace(r"\s+", " ", regex=True)
             .str.strip())


def _unit_and_category(name: str) -> tuple[str, str]:
    """Derive (unit, category) from a series name like 'X (DOD, current US$)'."""
    m = re.search(r"\(([^()]*)\)\s*$", name)
    tail = m.group(1) if m else ""
    if "US$" in tail:
        unit = "USD"
        prefix = tail.split(",")[0].strip() if "," in tail else ""
        category = CATEGORY_NAMES.get(prefix, "Other (US$)")
    elif tail.startswith("%"):
        unit, category = "Percent", "Ratio / percentage"
    elif tail == "years":
        unit, category = "Years", "Terms"
    else:
        unit, category = "Other", "Other"
    return unit, category


def load_raw() -> pd.DataFrame:
    return pd.read_csv(config.RAW_DATA_FILE, encoding=config.RAW_ENCODING, low_memory=False)


def clean() -> dict[str, pd.DataFrame]:
    report: dict = {}

    # 1. Load -----------------------------------------------------------
    raw = load_raw()
    report["raw_shape"] = list(raw.shape)
    year_cols = [c for c in raw.columns if str(c).strip().isdigit()]
    report["year_columns"] = [int(year_cols[0]), int(year_cols[-1])]

    # 2. Standardise text ------------------------------------------------
    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    text_cols = ["Country Name", "Country Code", "Counterpart-Area Name",
                 "Counterpart-Area Code", "Series Name", "Series Code"]
    for c in text_cols:
        df[c] = _clean_text(df[c])

    # 3. Drop footer / blank rows ----------------------------------------
    footer = df["Series Code"].isna() | df["Country Code"].isna()
    report["footer_or_blank_rows_dropped"] = int(footer.sum())
    df = df[~footer]

    # 4. Constant columns --------------------------------------------------
    report["counterpart_area_values"] = df["Counterpart-Area Name"].unique().tolist()
    df = df.drop(columns=["Counterpart-Area Name", "Counterpart-Area Code"])

    # 5. Duplicates ---------------------------------------------------------
    full_dups = int(df.duplicated().sum())
    key = ["Country Code", "Series Code"]
    key_dups = int(df.duplicated(key).sum())
    df = df.drop_duplicates().drop_duplicates(key, keep="first")
    report["duplicate_rows_removed"] = full_dups
    report["duplicate_keys_removed"] = key_dups

    # Missing-value profile before reshaping
    values = df[year_cols].apply(pd.to_numeric, errors="coerce")
    report["cells_total"] = int(values.size)
    report["cells_missing"] = int(values.isna().sum().sum())
    report["missing_pct"] = round(report["cells_missing"] / report["cells_total"] * 100, 2)
    report["rows_with_no_data_at_all"] = int(values.isna().all(axis=1).sum())

    # 6 + 7. Wide -> long, numeric, drop missing -----------------------------
    long = (df.melt(id_vars=["Country Name", "Country Code", "Series Name", "Series Code"],
                    value_vars=year_cols, var_name="year", value_name="value"))
    long["year"] = long["year"].astype(int)
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    before = len(long)
    long = long.dropna(subset=["value"])
    long = long[np.isfinite(long["value"])]
    report["long_rows_before_dropna"] = before
    report["long_rows_after_dropna"] = len(long)

    # 8a. Countries (+ metadata) ---------------------------------------------
    meta = pd.read_csv(config.RAW_COUNTRY_META, encoding=config.RAW_ENCODING)
    meta = meta.rename(columns={"Code": "country_code", "Region": "region",
                                "Income Group": "income_group", "Lending category": "lending_category"})
    for c in ["country_code", "region", "income_group", "lending_category"]:
        meta[c] = _clean_text(meta[c])
    countries = (df[["Country Code", "Country Name"]].drop_duplicates()
                 .rename(columns={"Country Code": "country_code", "Country Name": "country_name"})
                 .merge(meta[["country_code", "region", "income_group", "lending_category"]],
                        on="country_code", how="left"))
    # Regions / income groups have no Region in the metadata -> aggregates
    countries["is_aggregate"] = countries["region"].isna().astype(int)
    # Countries the World Bank has not assigned an income group (e.g. Ethiopia)
    unclassified = (countries["is_aggregate"] == 0) & countries["income_group"].isna()
    report["countries_without_income_group"] = countries.loc[unclassified, "country_name"].tolist()
    countries.loc[unclassified, "income_group"] = "Not classified"
    countries = countries.sort_values(["is_aggregate", "country_name"]).reset_index(drop=True)
    countries.insert(0, "country_id", range(1, len(countries) + 1))
    report["countries"] = int((countries.is_aggregate == 0).sum())
    report["aggregates"] = countries.loc[countries.is_aggregate == 1, "country_name"].tolist()

    # 8b. Indicators (+ metadata) ---------------------------------------------
    smeta = pd.read_csv(config.RAW_SERIES_META, encoding=config.RAW_ENCODING)
    smeta = smeta.rename(columns={"Code": "indicator_code", "Topic": "topic",
                                  "Short definition": "short_definition"})
    smeta["indicator_code"] = _clean_text(smeta["indicator_code"])
    smeta["topic"] = _clean_text(smeta["topic"]).str.replace("Economic Policy & Debt: ", "", regex=False)
    smeta["short_definition"] = _clean_text(smeta["short_definition"]).str.slice(0, 1000)
    indicators = (df[["Series Code", "Series Name"]].drop_duplicates()
                  .rename(columns={"Series Code": "indicator_code", "Series Name": "indicator_name"})
                  .merge(smeta[["indicator_code", "topic", "short_definition"]], on="indicator_code", how="left"))
    uc = indicators["indicator_name"].map(_unit_and_category)
    indicators["unit"] = [u for u, _ in uc]
    indicators["category"] = [c for _, c in uc]
    # A few US$ series lack the "(..., current US$)" suffix, e.g.
    # "Principal arrears, long-term DOD" - World Bank codes ending in .CD are US$
    fix = indicators["indicator_code"].str.endswith(".CD") & (indicators["unit"] == "Other")
    indicators.loc[fix, "unit"] = "USD"
    indicators.loc[fix, "category"] = "Arrears"
    indicators = indicators.sort_values("indicator_code").reset_index(drop=True)
    indicators.insert(0, "indicator_id", range(1, len(indicators) + 1))
    report["indicators"] = len(indicators)
    report["indicators_by_unit"] = indicators["unit"].value_counts().to_dict()

    # 8c. Fact table ------------------------------------------------------------
    debt = (long.merge(countries[["country_id", "country_code"]], left_on="Country Code", right_on="country_code")
                .merge(indicators[["indicator_id", "indicator_code"]], left_on="Series Code", right_on="indicator_code"))
    debt = debt[["country_id", "indicator_id", "year", "value"]].copy()
    debt["value"] = debt["value"].round(4)
    debt = debt.sort_values(["country_id", "indicator_id", "year"]).reset_index(drop=True)
    debt["is_projection"] = (debt["year"] > config.LATEST_ACTUAL_YEAR).astype(int)
    report["fact_rows"] = len(debt)
    report["projection_rows"] = int(debt["is_projection"].sum())

    # Sanity check: components of total external debt add up to the total
    total_id = indicators.loc[indicators.indicator_code == config.TOTAL_DEBT_CODE, "indicator_id"].item()
    comp_ids = indicators.loc[indicators.indicator_code.isin(config.DEBT_COMPONENT_CODES), "indicator_id"]
    country_ids = countries.loc[countries.is_aggregate == 0, "country_id"]
    latest = debt[(debt.year == config.LATEST_ACTUAL_YEAR) & debt.country_id.isin(country_ids)]
    total = latest.loc[latest.indicator_id == total_id, "value"].sum()
    comps = latest.loc[latest.indicator_id.isin(comp_ids), "value"].sum()
    report["global_external_debt_latest_usd"] = float(total)
    report["components_sum_latest_usd"] = float(comps)
    # within 0.5% - the World Bank rounds component figures
    report["components_match_total"] = bool(abs(comps / total - 1) < 0.005)

    return {"countries": countries, "indicators": indicators, "debt_data": debt, "report": report}


def save(result: dict) -> None:
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    result["countries"].to_csv(config.CLEAN_COUNTRIES, index=False)
    result["indicators"].to_csv(config.CLEAN_INDICATORS, index=False)
    result["debt_data"].to_csv(config.CLEAN_DEBT, index=False, compression="gzip")
    config.CLEANING_REPORT.write_text(json.dumps(result["report"], indent=2, default=str))


def load_clean() -> dict[str, pd.DataFrame]:
    """Read the processed files back (used by the loader and the notebook)."""
    return {
        "countries": pd.read_csv(config.CLEAN_COUNTRIES),
        "indicators": pd.read_csv(config.CLEAN_INDICATORS),
        "debt_data": pd.read_csv(config.CLEAN_DEBT),
    }


if __name__ == "__main__":
    res = clean()
    save(res)
    r = res["report"]
    print(f"Raw shape                 : {r['raw_shape']}")
    print(f"Footer/blank rows dropped : {r['footer_or_blank_rows_dropped']}")
    print(f"Duplicates removed        : {r['duplicate_rows_removed']} rows, {r['duplicate_keys_removed']} keys")
    print(f"Missing cells             : {r['cells_missing']:,} of {r['cells_total']:,} ({r['missing_pct']}%)")
    print(f"Countries / aggregates    : {r['countries']} / {len(r['aggregates'])}")
    print(f"Indicators                : {r['indicators']} {r['indicators_by_unit']}")
    print(f"Clean fact rows           : {r['fact_rows']:,} ({r['projection_rows']:,} projections)")
    print(f"Global external debt {config.LATEST_ACTUAL_YEAR} : ${r['global_external_debt_latest_usd'] / 1e12:,.2f} T "
          f"(components match: {r['components_match_total']})")
