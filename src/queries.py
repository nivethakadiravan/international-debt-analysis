"""The 30 SQL analytical questions.

Definitions used throughout (see sql/02_views.sql):
  * "debt" of a country  = External debt stocks, total (DT.DOD.DECT.CD), current US$
  * "debt records"       = debt-stock indicators (DOD, current US$) per country
  * latest year          = 2024 (last year of actual data; 2025+ are projections)
  * countries            = the 120 reporting countries; the 14 regional /
                           income-group aggregates are excluded from totals

sql/03_analysis_queries.sql is generated from this file
(python scripts/export_queries.py).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Query:
    level: str
    question: str
    sql: str
    note: str = ""


QUERIES: list[Query] = [
    # ================================================================ BASIC
    Query("Basic", "Retrieve all distinct country names from the dataset.",
          """SELECT DISTINCT country_name
FROM countries
WHERE is_aggregate = 0
ORDER BY country_name;""",
          "Regional / income-group aggregates are excluded - they are not countries."),
    Query("Basic", "Count the total number of countries available.",
          """SELECT COUNT(CASE WHEN is_aggregate = 0 THEN 1 END) AS countries,
       COUNT(CASE WHEN is_aggregate = 1 THEN 1 END) AS regional_income_aggregates,
       COUNT(*)              AS total_entities
FROM countries;"""),
    Query("Basic", "Find the total number of indicators present.",
          """SELECT COUNT(*) AS total_indicators,
       COUNT(CASE WHEN unit = 'USD' THEN 1 END) AS usd_indicators
FROM indicators;"""),
    Query("Basic", "Display the first 10 records of the dataset.",
          """SELECT d.debt_id, c.country_name, i.indicator_name, d.year, d.value
FROM (SELECT * FROM debt_data ORDER BY debt_id LIMIT 10) d   -- limit first, then join
JOIN countries  c ON c.country_id   = d.country_id
JOIN indicators i ON i.indicator_id = d.indicator_id
ORDER BY d.debt_id;"""),
    Query("Basic", "Calculate the total global debt.",
          """SELECT COUNT(*)                         AS countries,
       SUM(total_debt)                  AS total_global_debt_usd,
       ROUND(SUM(total_debt) / 1e12, 2) AS total_global_debt_trillion
FROM v_country_debt
WHERE year = 2024;""",
          "Sum of total external debt stocks of all 120 countries in 2024."),
    Query("Basic", "List all unique indicator names.",
          """SELECT DISTINCT indicator_name, unit, category
FROM indicators
ORDER BY indicator_name;"""),
    Query("Basic", "Find the number of records for each country.",
          """SELECT c.country_name, COUNT(*) AS records
FROM debt_data d
JOIN countries c ON c.country_id = d.country_id
WHERE c.is_aggregate = 0
GROUP BY c.country_id, c.country_name
ORDER BY records DESC;"""),
    Query("Basic", "Display all records where debt is greater than 1 billion USD.",
          """SELECT country_name, indicator_name, debt_usd
FROM v_debt_latest
WHERE debt_usd > 1000000000
ORDER BY debt_usd DESC;""",
          "Debt-stock indicators, 2024."),
    Query("Basic", "Find the minimum, maximum, and average debt values.",
          """SELECT MIN(total_debt) AS min_debt_usd,
       MAX(total_debt) AS max_debt_usd,
       ROUND(AVG(total_debt), 2) AS avg_debt_usd
FROM v_country_debt
WHERE year = 2024;""",
          "Across countries' total external debt, 2024."),
    Query("Basic", "Count total number of records in the dataset.",
          """SELECT COUNT(*)              AS total_records,
       COUNT(CASE WHEN is_projection = 0 THEN 1 END) AS actual_records,
       COUNT(CASE WHEN is_projection = 1 THEN 1 END) AS projected_records
FROM debt_data;"""),

    # ========================================================= INTERMEDIATE
    Query("Intermediate", "Find the total debt for each country.",
          """SELECT country_name, region, income_group, total_debt
FROM v_country_debt
WHERE year = 2024
ORDER BY total_debt DESC;"""),
    Query("Intermediate", "Display the top 10 countries with the highest total debt.",
          """SELECT country_name, total_debt,
       ROUND(total_debt / 1e9, 1) AS debt_billion
FROM v_country_debt
WHERE year = 2024
ORDER BY total_debt DESC
LIMIT 10;"""),
    Query("Intermediate", "Find the average debt per country.",
          """SELECT country_name,
       COUNT(*)                  AS years_reported,
       ROUND(AVG(total_debt), 2) AS avg_debt_2000_2024
FROM v_country_debt
GROUP BY country_id, country_name
ORDER BY avg_debt_2000_2024 DESC;""",
          "Average of each country's yearly total external debt, 2000-2024."),
    Query("Intermediate", "Calculate total debt for each indicator.",
          """SELECT indicator_name,
       COUNT(*)      AS countries,
       SUM(debt_usd) AS total_debt_usd
FROM v_debt_latest
GROUP BY indicator_id, indicator_name
ORDER BY total_debt_usd DESC;"""),
    Query("Intermediate", "Identify the indicator contributing the highest total debt.",
          """SELECT indicator_name, SUM(debt_usd) AS total_debt_usd
FROM v_debt_latest
GROUP BY indicator_id, indicator_name
ORDER BY total_debt_usd DESC
LIMIT 1;"""),
    Query("Intermediate", "Find the country with the lowest total debt.",
          """SELECT country_name, region, total_debt
FROM v_country_debt
WHERE year = 2024
ORDER BY total_debt ASC
LIMIT 1;"""),
    Query("Intermediate", "Calculate total debt for each country and indicator combination.",
          """SELECT country_name, indicator_name, SUM(debt_usd) AS total_debt_usd
FROM v_debt_latest
GROUP BY country_id, country_name, indicator_id, indicator_name
ORDER BY country_name, total_debt_usd DESC;"""),
    Query("Intermediate", "Count how many indicators each country has.",
          """SELECT c.country_name, COUNT(DISTINCT d.indicator_id) AS indicators_with_data
FROM debt_data d
JOIN countries c ON c.country_id = d.country_id
WHERE c.is_aggregate = 0
GROUP BY c.country_id, c.country_name
ORDER BY indicators_with_data DESC;"""),
    Query("Intermediate", "Display countries whose total debt is above the global average.",
          """SELECT country_name, total_debt,
       (SELECT AVG(total_debt) FROM v_country_debt WHERE year = 2024) AS global_average
FROM v_country_debt
WHERE year = 2024
  AND total_debt > (SELECT AVG(total_debt) FROM v_country_debt WHERE year = 2024)
ORDER BY total_debt DESC;"""),
    Query("Intermediate", "Rank countries based on total debt (highest to lowest).",
          """SELECT RANK() OVER (ORDER BY total_debt DESC) AS debt_rank,
       country_name, total_debt
FROM v_country_debt
WHERE year = 2024
ORDER BY debt_rank;"""),

    # ============================================================= ADVANCED
    Query("Advanced", "Find the top 5 indicators contributing most to global debt.",
          """SELECT indicator_name, SUM(debt_usd) AS total_debt_usd
FROM v_debt_latest
GROUP BY indicator_id, indicator_name
ORDER BY total_debt_usd DESC
LIMIT 5;"""),
    Query("Advanced", "Calculate percentage contribution of each country to total global debt.",
          """SELECT country_name, total_debt,
       ROUND(total_debt * 100 / SUM(total_debt) OVER (), 2) AS pct_of_global_debt
FROM v_country_debt
WHERE year = 2024
ORDER BY pct_of_global_debt DESC;"""),
    Query("Advanced", "Identify the top 3 countries for each indicator based on debt.",
          """WITH ranked AS (
    SELECT indicator_name, country_name, debt_usd,
           ROW_NUMBER() OVER (PARTITION BY indicator_id ORDER BY debt_usd DESC) AS rn
    FROM v_debt_latest
    WHERE debt_usd > 0
)
SELECT indicator_name, rn AS position, country_name, debt_usd
FROM ranked
WHERE rn <= 3
ORDER BY indicator_name, rn;"""),
    Query("Advanced", "Find the difference between maximum and minimum debt for each country.",
          """SELECT country_name,
       MIN(total_debt)                   AS min_debt,
       MAX(total_debt)                   AS max_debt,
       MAX(total_debt) - MIN(total_debt) AS debt_range
FROM v_country_debt
GROUP BY country_id, country_name
ORDER BY debt_range DESC;""",
          "Range of each country's total external debt across 2000-2024."),
    Query("Advanced", "Create a view for the top 10 countries with highest debt.",
          """SELECT * FROM v_top10_countries_debt;""",
          "The view is created in sql/02_views.sql:\n"
          "CREATE OR REPLACE VIEW v_top10_countries_debt AS\n"
          "SELECT country_name, region, income_group, total_debt\n"
          "FROM v_country_debt WHERE year = 2024\n"
          "ORDER BY total_debt DESC LIMIT 10;"),
    Query("Advanced", "Categorize countries into High / Medium / Low debt (based on thresholds).",
          """SELECT country_name, total_debt,
       CASE
           WHEN total_debt >= 100000000000 THEN 'High Debt'    -- >= $100 B
           WHEN total_debt >=  10000000000 THEN 'Medium Debt'  -- $10 B - $100 B
           ELSE 'Low Debt'                                     -- < $10 B
       END AS debt_category
FROM v_country_debt
WHERE year = 2024
ORDER BY total_debt DESC;"""),
    Query("Advanced", "Use window functions to calculate cumulative debt per country.",
          """SELECT RANK() OVER (ORDER BY total_debt DESC) AS debt_rank,
       country_name,
       total_debt,
       SUM(total_debt) OVER (ORDER BY total_debt DESC
                             ROWS UNBOUNDED PRECEDING)  AS cumulative_debt,
       ROUND(SUM(total_debt) OVER (ORDER BY total_debt DESC ROWS UNBOUNDED PRECEDING)
             * 100 / SUM(total_debt) OVER (), 2)        AS cumulative_pct
FROM v_country_debt
WHERE year = 2024
ORDER BY debt_rank;""",
          "Running total from the most to the least indebted country (a Pareto view)."),
    Query("Advanced", "Find indicators where average debt is higher than overall average debt.",
          """SELECT indicator_name, ROUND(AVG(debt_usd), 2) AS avg_debt_usd
FROM v_debt_latest
GROUP BY indicator_id, indicator_name
HAVING AVG(debt_usd) > (SELECT AVG(debt_usd) FROM v_debt_latest)
ORDER BY avg_debt_usd DESC;"""),
    Query("Advanced", "Identify countries contributing more than 5% of global debt.",
          """WITH share AS (
    SELECT country_name, total_debt,
           total_debt * 100 / SUM(total_debt) OVER () AS pct
    FROM v_country_debt
    WHERE year = 2024
)
SELECT country_name, total_debt, ROUND(pct, 2) AS pct_of_global_debt
FROM share
WHERE pct > 5
ORDER BY pct DESC;"""),
    Query("Advanced", "Find the most dominant indicator (highest contribution) for each country.",
          """WITH comp AS (
    SELECT country_name, indicator_name, debt_usd,
           debt_usd * 100 / SUM(debt_usd) OVER (PARTITION BY country_id) AS pct_of_country,
           ROW_NUMBER() OVER (PARTITION BY country_id ORDER BY debt_usd DESC) AS rn
    FROM v_debt_latest
    WHERE indicator_code IN ('DT.DOD.DPPG.CD',   -- public & publicly guaranteed
                             'DT.DOD.DPNG.CD',   -- private non-guaranteed
                             'DT.DOD.DSTC.CD',   -- short-term
                             'DT.DOD.DIMF.CD')   -- IMF credit & SDR
)
SELECT country_name, indicator_name AS dominant_indicator, debt_usd,
       ROUND(pct_of_country, 1) AS pct_of_country_debt
FROM comp
WHERE rn = 1
ORDER BY debt_usd DESC;""",
          "Compared among the 4 components that add up to total external debt, so shares sum to 100%."),
]


LEVELS = ["Basic", "Intermediate", "Advanced"]
