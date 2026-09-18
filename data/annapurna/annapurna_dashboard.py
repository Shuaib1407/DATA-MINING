import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
SALES_DIR = ROOT / "sales"


@st.cache_data
def load_sales_data():
    files = sorted(SALES_DIR.glob("SALES_*.csv"))
    if not files:
        raise FileNotFoundError(f"No sales CSV files found in {SALES_DIR}")

    frames = []
    for file in files:
        try:
            sample = file.read_text(encoding="utf-8-sig", errors="replace").splitlines()[0]
            sep = ";" if ";" in sample else ","
            raw = pd.read_csv(file, sep=sep, engine="python", dtype=str, keep_default_na=False)

            columns = {c.strip().lower(): c for c in raw.columns}
            renamed = raw.rename(columns={v: k for k, v in columns.items()})

            if "item_code" in renamed.columns:
                renamed = renamed.rename(columns={"item_code": "product_code", "quantity": "qty", "rate": "unit_price", "type": "line_type", "txn_time": "ts"})

            if "store_id" not in renamed.columns:
                store_match = re.search(r"SALES_(S\d+)_", file.name)
                renamed["store_id"] = store_match.group(1) if store_match else "UNKNOWN"

            if "business_date" not in renamed.columns:
                date_match = re.search(r"SALES_[A-Z0-9]+_(\d{8})", file.name)
                if date_match:
                    renamed["business_date"] = pd.to_datetime(date_match.group(1), format="%Y%m%d")
                else:
                    renamed["business_date"] = pd.NaT

            if "line_type" in renamed.columns:
                renamed["line_type"] = renamed["line_type"].astype(str).str.upper().str.strip()

            needed = ["store_id", "business_date", "bill_no", "line_no", "product_code", "qty", "unit_price", "line_type", "ts"]
            for col in needed:
                if col not in renamed.columns:
                    renamed[col] = ""

            renamed["line_no"] = pd.to_numeric(renamed["line_no"], errors="coerce").fillna(0).astype(int)
            renamed["qty"] = pd.to_numeric(renamed["qty"], errors="coerce").fillna(0)
            renamed["unit_price"] = pd.to_numeric(renamed["unit_price"], errors="coerce").fillna(0)
            renamed["source_file"] = file.name

            frames.append(renamed[needed])
        except Exception:
            continue

    if not frames:
        raise ValueError("No valid sales files could be parsed")

    sales = pd.concat(frames, ignore_index=True)
    sales["store_id"] = sales["store_id"].astype(str)
    sales["bill_no"] = sales["bill_no"].astype(str)
    sales["product_code"] = sales["product_code"].astype(str)
    sales["line_type"] = sales["line_type"].astype(str).str.upper()
    sales["revenue_amount"] = sales["qty"] * sales["unit_price"]
    sales["month"] = sales["business_date"].dt.to_period("M").astype(str)
    sales["year_month"] = sales["business_date"].dt.to_period("M").astype(str)

    sales = sales.sort_values(["store_id", "business_date", "bill_no", "line_no"]).reset_index(drop=True)
    return sales


sales = load_sales_data()

st.set_page_config(page_title="Annapurna 12-Store Dashboard", layout="wide")
st.title("Annapurna Stores — 12-store overview")
st.caption("All sales files across the network, normalized into one dashboard view")

store_summary = (
    sales.groupby("store_id", as_index=False)
    .agg(
        revenue=("revenue_amount", "sum"),
        bills=("bill_no", "nunique"),
        lines=("line_no", "count"),
        stores_days=("business_date", "nunique"),
        avg_bill_value=("revenue_amount", "mean"),
    )
    .sort_values("revenue", ascending=False)
)

revenue_by_month = (
    sales.groupby(["year_month", "store_id"], as_index=False)["revenue_amount"].sum()
)

# KPI cards
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.metric("Stores", f"{sales['store_id'].nunique()}")
with kpi2:
    st.metric("Total revenue", f"₹{sales['revenue_amount'].sum():,.2f}")
with kpi3:
    st.metric("Unique bills", f"{sales['bill_no'].nunique():,}")
with kpi4:
    st.metric("Days covered", f"{sales['business_date'].nunique()}")

st.subheader("Store performance")
col1, col2 = st.columns([2, 1])
with col1:
    store_bar = px.bar(
        store_summary,
        x="store_id",
        y="revenue",
        color="store_id",
        title="Revenue by store",
        labels={"store_id": "Store", "revenue": "Revenue (₹)"},
    )
    st.plotly_chart(store_bar, use_container_width=True)

with col2:
    st.dataframe(
        store_summary[["store_id", "revenue", "bills", "lines"]].sort_values("revenue", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

st.subheader("Monthly trend")
monthly_plot = px.line(
    revenue_by_month,
    x="year_month",
    y="revenue_amount",
    color="store_id",
    title="Monthly revenue by store",
    labels={"year_month": "Month", "revenue_amount": "Revenue (₹)", "store_id": "Store"},
)
st.plotly_chart(monthly_plot, use_container_width=True)

st.subheader("Store detail")
selected_store = st.selectbox("Choose store", sorted(sales["store_id"].unique()))
store_detail = sales[sales["store_id"] == selected_store].copy()
store_detail["day"] = store_detail["business_date"].dt.strftime("%Y-%m-%d")
store_daily = (
    store_detail.groupby("day", as_index=False)["revenue_amount"].sum().sort_values("day")
)
store_daily_chart = px.line(
    store_daily,
    x="day",
    y="revenue_amount",
    title=f"Daily revenue for {selected_store}",
    labels={"day": "Date", "revenue_amount": "Revenue (₹)"},
)
st.plotly_chart(store_daily_chart, use_container_width=True)

st.dataframe(
    store_detail.groupby("line_type", as_index=False)["revenue_amount"].sum().sort_values("revenue_amount", ascending=False),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Raw data preview")
st.dataframe(sales.head(200), use_container_width=True, hide_index=True)
