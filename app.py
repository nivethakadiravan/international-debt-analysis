"""International Debt Analysis - Streamlit dashboard (reads from MySQL).

Run:  streamlit run app.py
"""

from __future__ import annotations

import mysql.connector
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import config
from src.db import run_query
from src.queries import LEVELS, QUERIES

st.set_page_config(page_title="International Debt Analysis", page_icon="🌍", layout="wide")

LATEST = config.LATEST_ACTUAL_YEAR
PALETTE = px.colors.sequential.Teal
COMPONENT_COLORS = ["#264653", "#2a9d8f", "#e9c46a", "#e76f51"]


# =====================================================================
# Helpers
# =====================================================================
def usd(v: float) -> str:
    """Compact US$ formatting: $8.94T, $716.0B, $173.2M."""
    if v is None or pd.isna(v):
        return "–"
    a = abs(v)
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return f"${v / div:,.2f}{suf}" if suf == "T" else f"${v / div:,.1f}{suf}"
    return f"${v:,.0f}"


@st.cache_data(ttl=3600, show_spinner=False)
def q(sql: str, params: tuple | None = None) -> pd.DataFrame:
    return run_query(sql, params)


def country_debt(year: int | None = None) -> pd.DataFrame:
    sql = "SELECT country_name, country_code, region, income_group, year, total_debt FROM v_country_debt"
    if year is not None:
        return q(sql + " WHERE year = %s", (year,))
    return q(sql)


def indicator_values(code: str, year: int | None = None) -> pd.DataFrame:
    sql = """SELECT c.country_name, c.country_code, c.region, c.income_group, d.year, d.value
             FROM debt_data d
             JOIN countries c  ON c.country_id = d.country_id
             JOIN indicators i ON i.indicator_id = d.indicator_id
             WHERE i.indicator_code = %s AND c.is_aggregate = 0 AND d.is_projection = 0"""
    if year is not None:
        return q(sql + " AND d.year = %s", (code, year))
    return q(sql, (code,))


def apply_filters(df: pd.DataFrame, regions: list[str], incomes: list[str]) -> pd.DataFrame:
    if regions:
        df = df[df["region"].isin(regions)]
    if incomes:
        df = df[df["income_group"].isin(incomes)]
    return df


def money_config(df: pd.DataFrame) -> dict:
    return {c: st.column_config.NumberColumn(c.replace("_", " ").title(), format="dollar")
            for c in df.columns if any(k in c for k in ("debt", "value", "usd"))
            and pd.api.types.is_numeric_dtype(df[c])}


# =====================================================================
# Sidebar
# =====================================================================
st.sidebar.title("🌍 International Debt")
st.sidebar.caption("World Bank International Debt Statistics · 120 low- & middle-income countries")
page = st.sidebar.radio("Navigate", ["📊 Overview", "🏳️ Country analysis", "📈 Indicator analysis",
                                     "🗺️ Regions & income", "⚖️ Compare countries",
                                     "🧮 SQL queries", "🔎 Data explorer"], label_visibility="collapsed")

try:
    meta = q("SELECT DISTINCT region, income_group FROM countries WHERE is_aggregate = 0")
except mysql.connector.Error as exc:
    st.error(f"Could not connect to MySQL: {exc.msg}\n\nCheck your `.env` file and run "
             "`python -m src.load_to_mysql` first.")
    st.stop()

st.sidebar.divider()
st.sidebar.markdown("**Filters**")
year = st.sidebar.slider("Year", 2000, LATEST, LATEST)
regions = st.sidebar.multiselect("Region", sorted(meta["region"].unique()))
incomes = st.sidebar.multiselect("Income group", sorted(meta["income_group"].unique()))
st.sidebar.caption("Debt = External debt stocks, total (DOD, current US$). Aggregates excluded.")


# =====================================================================
# Pages
# =====================================================================
def page_overview() -> None:
    st.title("📊 Global external debt overview")
    snap = apply_filters(country_debt(year), regions, incomes).sort_values("total_debt", ascending=False)
    prev = apply_filters(country_debt(year - 1), regions, incomes) if year > 2000 else pd.DataFrame()
    allyears = apply_filters(country_debt(), regions, incomes)
    if snap.empty:
        st.warning("No data for these filters.")
        return

    total = snap.total_debt.sum()
    c1, c2, c3, c4, c5 = st.columns(5)
    delta = f"{(total / prev.total_debt.sum() - 1) * 100:+.1f}% vs {year - 1}" if not prev.empty else None
    c1.metric(f"Total external debt ({year})", usd(total), delta, delta_color="inverse")
    c2.metric("Countries", f"{len(snap)}")
    c3.metric("Largest debtor", snap.iloc[0].country_name, usd(snap.iloc[0].total_debt), delta_color="off")
    c4.metric("Median country debt", usd(snap.total_debt.median()))
    top10 = snap.total_debt.head(10).sum() / total * 100
    c5.metric("Top-10 share", f"{top10:.1f}%")

    left, right = st.columns([3, 2])
    with left:
        trend = allyears.groupby("year", as_index=False)["total_debt"].sum()
        fig = px.area(trend, x="year", y="total_debt", title="Total external debt over time",
                      labels={"total_debt": "US$", "year": ""}, color_discrete_sequence=["#2a9d8f"])
        fig.add_vline(x=year, line_dash="dot", line_color="grey")
        st.plotly_chart(fig, width="stretch")
    with right:
        reg = snap.groupby("region", as_index=False)["total_debt"].sum()
        fig = px.pie(reg, names="region", values="total_debt", hole=.5, title=f"Share by region ({year})",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_traces(textinfo="percent")
        fig.update_layout(legend=dict(font=dict(size=10)))
        st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    with left:
        t = snap.head(10).iloc[::-1]
        fig = px.bar(t, x="total_debt", y="country_name", orientation="h", title=f"Top 10 countries ({year})",
                     labels={"total_debt": "US$", "country_name": ""}, color="total_debt",
                     color_continuous_scale="Reds")
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig, width="stretch")
    with right:
        b = snap.tail(10)
        fig = px.bar(b, x="total_debt", y="country_name", orientation="h", title=f"Least indebted 10 ({year})",
                     labels={"total_debt": "US$", "country_name": ""}, color_discrete_sequence=["#2a9d8f"])
        st.plotly_chart(fig, width="stretch")

    st.subheader("Debt categories")
    cat = pd.cut(snap.total_debt, [0, config.MEDIUM_DEBT_THRESHOLD, config.HIGH_DEBT_THRESHOLD, float("inf")],
                 labels=["Low (< $10B)", "Medium ($10B–$100B)", "High (≥ $100B)"], right=False)
    summary = snap.assign(category=cat).groupby("category", observed=False).agg(
        countries=("country_name", "count"), total_debt=("total_debt", "sum")).reset_index()
    summary["share_pct"] = (summary.total_debt / total * 100).round(1)
    cols = st.columns(3)
    for col, r in zip(cols, summary.itertuples()):
        col.metric(r.category, f"{r.countries} countries", f"{usd(r.total_debt)} · {r.share_pct}% of debt", delta_color="off")

    st.subheader("Key insights")
    cum = snap.total_debt.cumsum() / total * 100
    n80 = int((cum < 80).sum()) + 1
    first = allyears[allyears.year == 2000].total_debt.sum()
    reg_top = reg.sort_values("total_debt", ascending=False).iloc[0]
    st.markdown(f"""
- **{snap.iloc[0].country_name}** alone holds **{snap.iloc[0].total_debt / total * 100:.1f}%** of the debt; the top 10 hold **{top10:.1f}%** and just **{n80}** of {len(snap)} countries account for 80%.
- Debt in {year} is **{total / first:.1f}×** the 2000 level ({usd(first)} → {usd(total)}).
- **{reg_top.region}** is the most indebted region ({reg_top.total_debt / total * 100:.0f}% of the total).
- The typical (median) country owes **{usd(snap.total_debt.median())}**, far below the mean of **{usd(snap.total_debt.mean())}**, a sign of strong concentration.
""")


def page_country() -> None:
    st.title("🏳️ Country analysis")
    snap = country_debt(year).sort_values("total_debt", ascending=False).reset_index(drop=True)
    names = apply_filters(snap, regions, incomes).country_name.tolist() or snap.country_name.tolist()
    default = names.index("India") if "India" in names else 0
    name = st.selectbox("Country", names, index=default)
    row = snap[snap.country_name == name].iloc[0]
    rank = int(snap.index[snap.country_name == name][0]) + 1

    gni = indicator_values("DT.DOD.DECT.GN.ZS", year)
    gni_v = gni.loc[gni.country_name == name, "value"]
    ds = indicator_values("DT.TDS.DECT.CD", year)
    ds_v = ds.loc[ds.country_name == name, "value"]

    st.caption(f"{row.region} · {row.income_group}")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(f"Total external debt ({year})", usd(row.total_debt))
    c2.metric("Global rank", f"#{rank} of {len(snap)}")
    share = row.total_debt / snap.total_debt.sum() * 100
    c3.metric("Share of global debt", f"{share:.2f}%" if share >= 0.01 else f"{share:.4f}%")
    c4.metric("Debt % of GNI", f"{gni_v.iloc[0]:.1f}%" if len(gni_v) else "–")
    c5.metric("Debt service paid", usd(ds_v.iloc[0]) if len(ds_v) else "–")

    hist = country_debt()
    hist = hist[hist.country_name == name]
    left, right = st.columns([3, 2])
    with left:
        fig = px.line(hist, x="year", y="total_debt", markers=True, title="Total external debt, 2000–2024",
                      labels={"total_debt": "US$", "year": ""}, color_discrete_sequence=["#264653"])
        fig.add_vline(x=year, line_dash="dot", line_color="grey")
        st.plotly_chart(fig, width="stretch")
    with right:
        comp = q("""SELECT i.indicator_code, d.value FROM debt_data d
                    JOIN countries c ON c.country_id = d.country_id
                    JOIN indicators i ON i.indicator_id = d.indicator_id
                    WHERE c.country_name = %s AND d.year = %s AND i.indicator_code IN
                          ('DT.DOD.DPPG.CD','DT.DOD.DPNG.CD','DT.DOD.DSTC.CD','DT.DOD.DIMF.CD')""", (name, year))
        comp["component"] = comp.indicator_code.map(config.DEBT_COMPONENT_CODES)
        fig = px.pie(comp, names="component", values="value", hole=.5, title=f"Debt composition ({year})",
                     color_discrete_sequence=COMPONENT_COLORS)
        fig.update_layout(legend=dict(orientation="h", y=-0.15, font=dict(size=10)))
        st.plotly_chart(fig, width="stretch")

    flows = q("""SELECT i.indicator_code, d.year, d.value, d.is_projection FROM debt_data d
                 JOIN countries c ON c.country_id = d.country_id
                 JOIN indicators i ON i.indicator_id = d.indicator_id
                 WHERE c.country_name = %s AND i.indicator_code IN ('DT.AMT.DLXF.CD','DT.INT.DLXF.CD')""", (name,))
    flows["type"] = flows.indicator_code.map({"DT.AMT.DLXF.CD": "Principal", "DT.INT.DLXF.CD": "Interest"})
    fig = px.bar(flows.sort_values("year"), x="year", y="value", color="type",
                 title="Long-term debt service: actual and scheduled (dashed line = start of projections)",
                 labels={"value": "US$", "year": ""}, color_discrete_map={"Principal": "#2a9d8f", "Interest": "#e76f51"})
    fig.add_vline(x=LATEST + .5, line_dash="dash", line_color="black")
    st.plotly_chart(fig, width="stretch")

    with st.expander(f"All indicators for {name} in {year}"):
        allind = q("""SELECT i.category, i.indicator_name, i.unit, d.value FROM debt_data d
                      JOIN countries c ON c.country_id = d.country_id
                      JOIN indicators i ON i.indicator_id = d.indicator_id
                      WHERE c.country_name = %s AND d.year = %s ORDER BY i.category, d.value DESC""", (name, year))
        search = st.text_input("Search indicators", placeholder="e.g. interest, bonds, IMF")
        if search:
            allind = allind[allind.indicator_name.str.contains(search, case=False)]
        st.dataframe(allind, hide_index=True, width="stretch",
                     column_config={"value": st.column_config.NumberColumn("Value", format="%,.2f")})


def page_indicator() -> None:
    st.title("📈 Indicator analysis")
    inds = q("SELECT indicator_code, indicator_name, category, unit FROM indicators ORDER BY indicator_name")
    c1, c2 = st.columns([1, 2])
    cats = sorted(inds.category.unique())
    cat = c1.selectbox("Category", cats, index=cats.index("Debt outstanding (stock)"))
    sub = inds[inds.category == cat]
    default = sub.index[sub.indicator_code == config.TOTAL_DEBT_CODE]
    names = sub.indicator_name.tolist()
    ind_name = c2.selectbox("Indicator", names,
                            index=names.index(sub.loc[default[0], "indicator_name"]) if len(default) else 0)
    meta_row = sub[sub.indicator_name == ind_name].iloc[0]
    is_usd = meta_row.unit == "USD"

    data = apply_filters(indicator_values(meta_row.indicator_code), regions, incomes)
    snap = data[data.year == year].sort_values("value", ascending=False)
    if snap.empty:
        st.warning(f"No {year} data for this indicator and filters.")
        return
    fmt = usd if is_usd else (lambda v: f"{v:,.2f}")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Countries reporting", len(snap))
    k2.metric("Total" if is_usd else "Average", fmt(snap.value.sum() if is_usd else snap.value.mean()))
    k3.metric("Highest", snap.iloc[0].country_name, fmt(snap.iloc[0].value), delta_color="off")
    k4.metric("Median", fmt(snap.value.median()))

    n = st.slider("Countries to show", 5, 30, 15)
    left, right = st.columns([3, 2])
    with left:
        t = snap.head(n).iloc[::-1]
        fig = px.bar(t, x="value", y="country_name", orientation="h", color="region",
                     title=f"Top {n} countries ({year})", labels={"value": meta_row.unit, "country_name": ""},
                     color_discrete_sequence=px.colors.qualitative.Set2, height=max(400, n * 24))
        st.plotly_chart(fig, width="stretch")
    with right:
        agg = data.groupby("year", as_index=False)["value"].agg("sum" if is_usd else "mean")
        fig = px.line(agg, x="year", y="value", markers=True,
                      title=("Sum" if is_usd else "Average") + " across countries over time",
                      labels={"value": meta_row.unit, "year": ""}, color_discrete_sequence=["#264653"])
        st.plotly_chart(fig, width="stretch")
        fig = px.box(snap, x="income_group", y="value", points="all", log_y=is_usd and (snap.value > 0).all(),
                     title=f"Distribution by income group ({year})", labels={"value": meta_row.unit, "income_group": ""},
                     category_orders={"income_group": ["Low income", "Lower middle income", "Upper middle income"]})
        st.plotly_chart(fig, width="stretch")
    with st.expander("Definition"):
        d = q("SELECT topic, short_definition FROM indicators WHERE indicator_code = %s", (meta_row.indicator_code,))
        st.markdown(f"**{meta_row.indicator_code}** · {d.topic.iloc[0]}\n\n{d.short_definition.iloc[0]}")


def page_regions() -> None:
    st.title("🗺️ Regions & income groups")
    snap = apply_filters(country_debt(year), regions, incomes)
    if snap.empty:
        st.warning("No data for these filters.")
        return
    gni = indicator_values("DT.DOD.DECT.GN.ZS", year)[["country_code", "value"]].rename(columns={"value": "debt_pct_gni"})
    snap = snap.merge(gni, on="country_code", how="left")

    metric = st.radio("Map colour", ["Total debt (US$)", "Debt as % of GNI"], horizontal=True)
    col = "total_debt" if metric.startswith("Total") else "debt_pct_gni"
    fig = px.choropleth(snap, locations="country_code", color=col, hover_name="country_name",
                        hover_data={"total_debt": ":,.0f", "debt_pct_gni": ":.1f", "country_code": False},
                        color_continuous_scale="Reds", title=f"{metric} ({year})",
                        range_color=(0, snap[col].quantile(.95)))
    fig.update_geos(showframe=False, showcoastlines=False, projection_type="natural earth")
    fig.update_layout(height=480, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, width="stretch")
    st.caption("High-income countries are not part of the IDS dataset, so they appear blank. "
               "The colour scale is capped at the 95th percentile so smaller countries remain visible.")

    fig = px.treemap(snap, path=[px.Constant("All countries"), "region", "country_name"], values="total_debt",
                     color="debt_pct_gni", color_continuous_scale="RdYlGn_r",
                     title=f"Debt by region and country ({year}); size = US$, colour = % of GNI")
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    with left:
        reg = snap.groupby("region").agg(countries=("country_name", "count"), total_debt=("total_debt", "sum"),
                                         median_debt=("total_debt", "median"),
                                         median_pct_gni=("debt_pct_gni", "median")).reset_index()
        reg["share_%"] = (reg.total_debt / reg.total_debt.sum() * 100).round(1)
        st.markdown("**By region**")
        st.dataframe(reg.sort_values("total_debt", ascending=False), hide_index=True, width="stretch",
                     column_config=money_config(reg) | {"median_pct_gni": st.column_config.NumberColumn(format="%.1f%%")})
    with right:
        inc = snap.groupby("income_group").agg(countries=("country_name", "count"), total_debt=("total_debt", "sum"),
                                               median_pct_gni=("debt_pct_gni", "median")).reset_index()
        fig = px.bar(inc, x="income_group", y="total_debt", text="countries", title="Total debt by income group",
                     labels={"total_debt": "US$", "income_group": ""}, color_discrete_sequence=["#2a9d8f"],
                     category_orders={"income_group": ["Low income", "Lower middle income", "Upper middle income"]})
        fig.update_traces(texttemplate="%{text} countries", textposition="outside")
        st.plotly_chart(fig, width="stretch")


def page_compare() -> None:
    st.title("⚖️ Compare countries")
    names = sorted(country_debt(LATEST).country_name)
    picks = st.multiselect("Countries", names, default=[n for n in ["India", "Brazil", "Mexico", "Indonesia", "Turkiye"] if n in names])
    if not picks:
        st.info("Pick at least one country.")
        return
    hist = country_debt()
    hist = hist[hist.country_name.isin(picks)]
    view = st.radio("Show", ["US$", "Indexed (2010 = 100)"], horizontal=True)
    if view.startswith("Indexed"):
        base = hist[hist.year == 2010].set_index("country_name").total_debt
        hist = hist.assign(total_debt=hist.total_debt / hist.country_name.map(base) * 100)
    fig = px.line(hist, x="year", y="total_debt", color="country_name", markers=True,
                  title="Total external debt", labels={"total_debt": view, "year": "", "country_name": ""})
    st.plotly_chart(fig, width="stretch")

    codes = {"DT.DOD.DECT.CD": "Total debt", "DT.DOD.DECT.GN.ZS": "Debt % GNI", "DT.TDS.DECT.CD": "Debt service",
             "DT.INT.DECT.CD": "Interest paid", "DT.TDS.DECT.EX.ZS": "Debt service % exports",
             "FI.RES.TOTL.DT.ZS": "Reserves % debt"}
    rows = []
    for code, label in codes.items():
        v = indicator_values(code, year)
        v = v[v.country_name.isin(picks)].set_index("country_name").value
        rows.append(v.rename(label))
    table = pd.concat(rows, axis=1).reindex(picks)
    st.markdown(f"**Key indicators ({year})**")
    st.dataframe(table, width="stretch", column_config={
        "Total debt": st.column_config.NumberColumn(format="dollar"),
        "Debt service": st.column_config.NumberColumn(format="dollar"),
        "Interest paid": st.column_config.NumberColumn(format="dollar"),
        "Debt % GNI": st.column_config.NumberColumn(format="%.1f%%"),
        "Debt service % exports": st.column_config.NumberColumn(format="%.1f%%"),
        "Reserves % debt": st.column_config.NumberColumn(format="%.1f%%")})


def page_sql() -> None:
    st.title("🧮 SQL analytical queries")
    st.caption("All 30 questions run live against MySQL. Debt = External debt stocks, total (DT.DOD.DECT.CD); "
               "latest year = 2024; aggregates excluded.")
    level = st.radio("Level", LEVELS, horizontal=True)
    opts = [(i, qq) for i, qq in enumerate(QUERIES, 1) if qq.level == level]
    i, query = st.selectbox("Question", opts, format_func=lambda o: f"Q{o[0]}. {o[1].question}")
    if query.note:
        st.info(query.note)
    st.code(query.sql, language="sql")
    try:
        df = q(query.sql)
    except mysql.connector.Error as exc:
        st.error(f"Query failed: {exc.msg}")
        return
    st.caption(f"{len(df):,} row(s)")
    st.dataframe(df, hide_index=True, width="stretch", column_config=money_config(df))
    st.download_button("Download result (CSV)", df.to_csv(index=False).encode(), f"Q{i}.csv", "text/csv")


def page_explorer() -> None:
    st.title("🔎 Data explorer")
    st.caption("Query the cleaned fact table directly.")
    countries = q("SELECT country_name FROM countries ORDER BY is_aggregate, country_name").country_name.tolist()
    inds = q("SELECT indicator_name FROM indicators ORDER BY indicator_name").indicator_name.tolist()
    c1, c2 = st.columns(2)
    pick_c = c1.multiselect("Countries", countries, default=["India"])
    pick_i = c2.multiselect("Indicators", inds, default=["External debt stocks, total (DOD, current US$)"])
    yr = st.slider("Years", 2000, 2032, (2015, LATEST))
    incl_proj = st.checkbox("Include projections (2025+)", value=yr[1] > LATEST)
    if not pick_c or not pick_i:
        st.info("Pick at least one country and one indicator.")
        return
    cm = ", ".join(["%s"] * len(pick_c))
    im = ", ".join(["%s"] * len(pick_i))
    df = q(f"""SELECT c.country_name, i.indicator_name, d.year, d.value, d.is_projection
               FROM debt_data d
               JOIN countries c ON c.country_id = d.country_id
               JOIN indicators i ON i.indicator_id = d.indicator_id
               WHERE c.country_name IN ({cm}) AND i.indicator_name IN ({im})
                 AND d.year BETWEEN %s AND %s {'' if incl_proj else 'AND d.is_projection = 0'}
               ORDER BY c.country_name, i.indicator_name, d.year""", tuple(pick_c + pick_i + [yr[0], yr[1]]))
    if df.empty:
        st.warning("No data for this selection.")
        return
    wide = df.pivot_table(index=["country_name", "indicator_name"], columns="year", values="value")
    wide.columns = [str(c) for c in wide.columns]
    wide = wide.reset_index()
    st.dataframe(wide, hide_index=True, width="stretch")
    if df.indicator_name.nunique() == 1:
        fig = px.line(df, x="year", y="value", color="country_name", markers=True, title=pick_i[0])
        st.plotly_chart(fig, width="stretch")
    st.download_button("Download (CSV)", df.to_csv(index=False).encode(), "debt_data_extract.csv", "text/csv")


PAGES = {
    "📊 Overview": page_overview,
    "🏳️ Country analysis": page_country,
    "📈 Indicator analysis": page_indicator,
    "🗺️ Regions & income": page_regions,
    "⚖️ Compare countries": page_compare,
    "🧮 SQL queries": page_sql,
    "🔎 Data explorer": page_explorer,
}

try:
    PAGES[page]()
except mysql.connector.Error as exc:
    st.error(f"Database error: {exc.msg}")
