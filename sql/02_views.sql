-- =====================================================================
-- International Debt Analysis - Analysis views
-- Run AFTER the data has been loaded (python -m src.load_to_mysql
-- runs this file automatically).
--
-- Why views?  The dataset has 576 overlapping indicators: "External debt
-- stocks, total" already contains "long-term", "short-term", "PPG", ...
-- Summing every indicator would count the same dollar many times. These
-- views define "debt" once, so every query and the dashboard agree.
-- =====================================================================

USE international_debt_db;

-- ---------------------------------------------------------------------
-- v_country_debt : headline debt of each COUNTRY for every actual year
--   = "External debt stocks, total (DOD, current US$)"  (DT.DOD.DECT.CD)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_country_debt AS
SELECT c.country_id,
       c.country_code,
       c.country_name,
       c.region,
       c.income_group,
       d.year,
       d.value AS total_debt
FROM debt_data d
JOIN countries  c ON c.country_id   = d.country_id
JOIN indicators i ON i.indicator_id = d.indicator_id
WHERE i.indicator_code = 'DT.DOD.DECT.CD'
  AND c.is_aggregate = 0
  AND d.is_projection = 0;

-- ---------------------------------------------------------------------
-- v_debt_latest : every debt-STOCK indicator (DOD, current US$) for each
--   country in the latest actual year (2024). Used for indicator-level
--   analysis ("which type of debt is largest?").
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_debt_latest AS
SELECT c.country_id,
       c.country_name,
       c.region,
       c.income_group,
       i.indicator_id,
       i.indicator_code,
       i.indicator_name,
       d.value AS debt_usd
FROM debt_data d
JOIN countries  c ON c.country_id   = d.country_id
JOIN indicators i ON i.indicator_id = d.indicator_id
WHERE i.category = 'Debt outstanding (stock)'
  AND i.unit = 'USD'
  AND c.is_aggregate = 0
  AND d.year = 2024;

-- ---------------------------------------------------------------------
-- v_top10_countries_debt : SQL question 25
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_top10_countries_debt AS
SELECT country_name,
       region,
       income_group,
       total_debt
FROM v_country_debt
WHERE year = 2024
ORDER BY total_debt DESC
LIMIT 10;
