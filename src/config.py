"""Shared paths and analysis constants."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

RAW_DATA_FILE = RAW_DIR / "IDS_ALLCountries_Data.csv"
RAW_COUNTRY_META = RAW_DIR / "IDS_CountryMetaData.csv"
RAW_SERIES_META = RAW_DIR / "IDS_SeriesMetaData.csv"

CLEAN_COUNTRIES = PROCESSED_DIR / "countries_clean.csv"
CLEAN_INDICATORS = PROCESSED_DIR / "indicators_clean.csv"
CLEAN_DEBT = PROCESSED_DIR / "debt_data_clean.csv.gz"
CLEANING_REPORT = PROCESSED_DIR / "cleaning_report.json"

# The World Bank files are not UTF-8 (they contain non-breaking spaces, 0xA0)
RAW_ENCODING = "latin-1"

# Last year with actual (reported) figures. 2025+ are projections of
# future debt-service payments on existing debt.
LATEST_ACTUAL_YEAR = 2024

# Headline measure of a country's external debt. Its four components
# (PPG + PNG long-term, short-term, IMF credit) sum exactly to it.
TOTAL_DEBT_CODE = "DT.DOD.DECT.CD"
DEBT_COMPONENT_CODES = {
    "DT.DOD.DPPG.CD": "Public & publicly guaranteed (long-term)",
    "DT.DOD.DPNG.CD": "Private non-guaranteed (long-term)",
    "DT.DOD.DSTC.CD": "Short-term debt",
    "DT.DOD.DIMF.CD": "IMF credit & SDR allocations",
}

# Thresholds for the High / Medium / Low debt categories (current US$)
HIGH_DEBT_THRESHOLD = 100e9   # >= $100 B
MEDIUM_DEBT_THRESHOLD = 10e9  # >= $10 B
