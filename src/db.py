"""Python <-> MySQL connection helpers.

Settings come from environment variables or a local ``.env`` file
(see ``.env.example``): DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from decimal import Decimal

import mysql.connector
import pandas as pd

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

DB_NAME = os.getenv("DB_NAME", "international_debt_db")


def db_config(include_database: bool = True) -> dict:
    cfg = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
    }
    if include_database:
        cfg["database"] = DB_NAME
    return cfg


@contextmanager
def get_connection(include_database: bool = True):
    conn = mysql.connector.connect(**db_config(include_database))
    try:
        yield conn
    finally:
        conn.close()


def run_query(sql: str, params=None) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame (DECIMALs converted to float)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        cols = [c[0] for c in cur.description] if cur.description else []
        rows = cur.fetchall()
        cur.close()
    df = pd.DataFrame(rows, columns=cols)
    for col in df.columns:
        if len(df) and df[col].map(lambda v: isinstance(v, Decimal)).any():
            df[col] = pd.to_numeric(df[col])
    return df


def split_statements(script: str) -> list[str]:
    """Split a .sql script on ';' (ignores comment-only lines)."""
    out, buf = [], []
    for line in script.splitlines():
        s = line.strip()
        if not buf and (not s or s.startswith("--")):
            continue
        buf.append(line)
        if s.endswith(";"):
            out.append("\n".join(buf).rstrip().rstrip(";"))
            buf = []
    if "".join(buf).strip():
        out.append("\n".join(buf))
    return out


def run_script(path, include_database: bool = False) -> int:
    with get_connection(include_database) as conn:
        cur = conn.cursor()
        stmts = split_statements(open(path, encoding="utf-8").read())
        for stmt in stmts:
            cur.execute(stmt)
        conn.commit()
        cur.close()
    return len(stmts)


if __name__ == "__main__":
    with get_connection(include_database=False) as conn:
        cur = conn.cursor()
        cur.execute("SELECT VERSION()")
        print("Connected to MySQL", cur.fetchone()[0])
