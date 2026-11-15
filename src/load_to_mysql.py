"""Create the MySQL database and insert the cleaned data.

    python -m src.load_to_mysql

1. Runs sql/01_schema.sql   (drops & recreates international_debt_db)
2. Inserts countries, indicators, then ~1.3 M debt_data rows in batches
3. Runs sql/02_views.sql    (analysis views)
4. Verifies row counts in MySQL match the cleaned DataFrames
"""

from __future__ import annotations

import time

import pandas as pd

from src import config
from src.cleaning import load_clean
from src.db import get_connection, run_script

BATCH = 20_000


def _rows(df: pd.DataFrame) -> list[tuple]:
    """DataFrame -> list of tuples with NaN converted to None (SQL NULL)."""
    clean = df.astype(object).where(df.notna(), None)
    return [tuple(r) for r in clean.itertuples(index=False, name=None)]


def insert(cur, table: str, df: pd.DataFrame) -> None:
    cols = ", ".join(df.columns)
    marks = ", ".join(["%s"] * len(df.columns))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({marks})"
    rows = _rows(df)
    for start in range(0, len(rows), BATCH):
        cur.executemany(sql, rows[start:start + BATCH])
        if len(rows) > BATCH:
            done = min(start + BATCH, len(rows))
            print(f"\r    {table}: {done:,}/{len(rows):,} rows", end="", flush=True)
    if len(rows) > BATCH:
        print()


def main() -> None:
    t0 = time.time()
    if not config.CLEAN_DEBT.exists():
        raise SystemExit("Cleaned data not found - run `python -m src.cleaning` first.")
    data = load_clean()

    n = run_script(config.ROOT / "sql" / "01_schema.sql")
    print(f"OK  schema created ({n} statements)")

    with get_connection() as conn:
        cur = conn.cursor()
        insert(cur, "countries", data["countries"])
        insert(cur, "indicators", data["indicators"])
        conn.commit()
        print(f"OK  countries ({len(data['countries'])}) and indicators ({len(data['indicators'])}) inserted")
        insert(cur, "debt_data", data["debt_data"][["country_id", "indicator_id", "year", "value", "is_projection"]])
        conn.commit()
        print(f"OK  debt_data ({len(data['debt_data']):,} rows) inserted")

        # verify
        for table, df in data.items():
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            db_count = cur.fetchone()[0]
            status = "match" if db_count == len(df) else "MISMATCH"
            print(f"    {table:<11} MySQL={db_count:>10,}  DataFrame={len(df):>10,}  {status}")
        cur.close()

    n = run_script(config.ROOT / "sql" / "02_views.sql")
    print(f"OK  analysis views created ({n} statements)")
    print(f"Done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
