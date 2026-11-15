"""Write sql/03_analysis_queries.sql from src/queries.py.

Run:  python scripts/export_queries.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.queries import QUERIES  # noqa: E402

lines = [
    "-- =====================================================================",
    "-- International Debt Analysis - 30 SQL Analytical Queries",
    "-- (generated from src/queries.py by scripts/export_queries.py)",
    "--",
    "-- Definitions:",
    "--   debt of a country = External debt stocks, total (DT.DOD.DECT.CD), US$",
    "--   latest year       = 2024 (last actual year; 2025+ are projections)",
    "--   views used        = v_country_debt, v_debt_latest (sql/02_views.sql)",
    "-- =====================================================================",
    "",
    "USE international_debt_db;",
]
level = None
for i, q in enumerate(QUERIES, start=1):
    if q.level != level:
        level = q.level
        lines += ["", "-- ---------------------------------------------------------------------",
                  f"-- {level} level", "-- ---------------------------------------------------------------------"]
    lines += ["", f"-- Q{i}. {q.question}"]
    if q.note:
        lines += [f"-- {ln}" for ln in q.note.splitlines()]
    lines.append(q.sql)
lines.append("")
out = ROOT / "sql" / "03_analysis_queries.sql"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {out.relative_to(ROOT)} ({len(QUERIES)} queries)")
