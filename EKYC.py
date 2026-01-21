import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(
    page_title="NIK Verification Dashboard",
    layout="wide"
)

st.title("NIK Verification Monitoring Dashboard")

# ======================
# LOAD EXCEL FILE
# ======================
FILE_NAME = "LogDukcapil_2025.xlsx"

if not Path(FILE_NAME).exists():
    st.error(f"❌ File '{FILE_NAME}' tidak ditemukan di folder app.py")
    st.stop()

df = pd.read_excel(FILE_NAME)

# ======================
# BASIC CLEANING
# ======================
df.columns = df.columns.str.strip()

df["CreatedDate"] = pd.to_datetime(df["CreatedDate"], errors="coerce")

status_cols = [
    "NamaDenganGelar", "Nama", "JenisKelamin",
    "TempatLahir", "TglLahir",
    "Provinsi", "Kabupaten", "Kecamatan", "Kelurahan"
]

for c in status_cols:
    if c in df.columns:
        df[c] = df[c].fillna("-")

# ======================
# SIDEBAR FILTER
# ======================
st.sidebar.header("Filter")

source_filter = st.sidebar.multiselect(
    "SourceResult",
    options=sorted(df["SourceResult"].dropna().unique()),
    default=sorted(df["SourceResult"].dropna().unique())
)

date_min = df["CreatedDate"].min().date()
date_max = df["CreatedDate"].max().date()

date_range = st.sidebar.date_input(
    "Tanggal",
    [date_min, date_max]
)

df_f = df[
    (df["SourceResult"].isin(source_filter)) &
    (df["CreatedDate"].dt.date.between(date_range[0], date_range[1]))
]

# ======================
# KPI SECTION
# ======================

# Total request (jumlah row)
total_request = len(df_f)

# Hitung frekuensi NIK
nik_counts = df_f["Nik"].value_counts()

# Total NIK unik
total_nik = nik_counts.count()

# NIK hit 1 kali
nik_hit_1 = (nik_counts == 1).sum()

# NIK hit lebih dari 1 kali
nik_hit_gt1 = (nik_counts > 1).sum()

# Persentase
pct_hit_1 = nik_hit_1 / total_nik if total_nik else 0
pct_hit_gt1 = nik_hit_gt1 / total_nik if total_nik else 0

# ======================
# DISPLAY KPI
# ======================
k1, k2, k3, k4 = st.columns(4)

k1.metric("Total Request", f"{total_request:,}")
k2.metric("NIK Hit 1x", f"{nik_hit_1:,}", f"{pct_hit_1:.2%}")
k3.metric("NIK Hit >1x", f"{nik_hit_gt1:,}", f"{pct_hit_gt1:.2%}")
k4.metric("Total Unique NIK", f"{total_nik:,}")

# ======================
# SOURCE RESULT CHART
# ======================
st.subheader("Source Result Distribution")

src_count = df_f["SourceResult"].value_counts().reset_index()
src_count.columns = ["SourceResult", "Count"]

fig_src = px.bar(
    src_count,
    x="SourceResult",
    y="Count",
    text="Count",
    color="SourceResult"
)

st.plotly_chart(fig_src, use_container_width=True)

# ======================
# STATUS RECAP
# ======================
st.subheader("Kesesuaian per Field")

rekap_long = (
    df_f[status_cols]
    .melt(var_name="Field", value_name="Status")
    .groupby(["Field", "Status"])
    .size()
    .reset_index(name="Count")
)

fig_status = px.bar(
    rekap_long,
    x="Field",
    y="Count",
    color="Status",
    barmode="stack"
)

st.plotly_chart(fig_status, use_container_width=True)

# ======================
# REPEAT NIK
# ======================
st.subheader("Repeat NIK (Top 20)")

repeat_table = (
    df_f["Nik"]
    .value_counts()
    .reset_index()
)

repeat_table.columns = ["Nik", "Total Request"]
repeat_table = repeat_table[repeat_table["Total Request"] > 1].head(50)

st.dataframe(repeat_table, use_container_width=True)

# ======================
# DAILY TREND
# ======================
st.subheader("Daily Request Trend")

daily = (
    df_f
    .groupby(df_f["CreatedDate"].dt.date)
    .size()
    .reset_index(name="Total")
)

fig_trend = px.line(
    daily,
    x="CreatedDate",
    y="Total",
    markers=True
)

st.plotly_chart(fig_trend, use_container_width=True)

# ======================
# SOURCE QUALITY
# ======================
st.subheader("% Sesuai per Source")

source_quality = (
    df_f
    .groupby("SourceResult")[status_cols]
    .apply(lambda x: (x == "Sesuai").mean())
    .reset_index()
)

st.dataframe(source_quality, use_container_width=True)

# ======================
# NIK DRILL DOWN
# ======================
st.subheader("NIK Drill Down")

nik_list = df_f["Nik"].dropna().unique()

selected_nik = st.selectbox(
    "Pilih NIK",
    options=sorted(nik_list)
)

df_nik = df_f[df_f["Nik"] == selected_nik]

# Ringkasan per Source
nik_source = (
    df_nik["SourceResult"]
    .value_counts()
    .reset_index()
)

nik_source.columns = ["SourceResult", "Total"]

c1, c2, c3 = st.columns(3)

c1.metric(
    "DB_CACHE",
    int(nik_source.loc[nik_source["SourceResult"] == "DB_CACHE", "Total"].sum())
)

c2.metric(
    "DUKCAPIL",
    int(nik_source.loc[nik_source["SourceResult"] == "DUKCAPIL", "Total"].sum())
)

c3.metric(
    "BCA",
    int(nik_source.loc[nik_source["SourceResult"] == "BCA", "Total"].sum())
)

# Chart
fig_nik = px.bar(
    nik_source,
    x="SourceResult",
    y="Total",
    color="SourceResult",
    text="Total",
    title=f"Request Distribution for NIK {selected_nik}"
)

st.plotly_chart(fig_nik, use_container_width=True)

# Detail Table
st.markdown("**Detail Request**")

st.dataframe(
    df_nik.sort_values("CreatedDate", ascending=False),
    use_container_width=True
)

# ======================
# RAW DATA
# ======================
with st.expander("Raw Data"):
    st.dataframe(df_f, use_container_width=True)

# ======================
# CACHE EFFICIENCY / REPEAT PAID ANALYSIS NON-OVERLAP
# ======================
st.subheader("Cache Efficiency / Repeat Paid Analysis (Per Row, Non-Overlap)")

# Semua baris DB_CACHE
df_cache = df_f[df_f["SourceResult"] == "DB_CACHE"]

# Urutkan dataframe
df_sorted = df_f.sort_values("CreatedDate")

# 1️⃣ DUKCAPIL → BCA → DB_CACHE (strict sequence)
def dukcapil_bca_cache_row(row):
    nik = row["Nik"]
    s = df_sorted[df_sorted["Nik"] == nik]["SourceResult"].tolist()
    return "DUKCAPIL" in s and "BCA" in s and "DB_CACHE" in s and s.index("DUKCAPIL") < s.index("BCA") < s.index("DB_CACHE")

df_dukapil_bca_cache = df_cache[df_cache.apply(dukcapil_bca_cache_row, axis=1)]

# 2️⃣ BCA → DB_CACHE (exclude kategori 1)
nik_dukapil_bca = set(df_dukapil_bca_cache["Nik"])
df_bca_cache = df_cache[(df_cache["Nik"].isin(df_f[df_f["SourceResult"] == "BCA"]["Nik"])) & (~df_cache["Nik"].isin(nik_dukapil_bca))]

# 3️⃣ DUKCAPIL → DB_CACHE (exclude kategori 1 & 2)
nik_bca_only = set(df_bca_cache["Nik"])
df_dukcapil_cache = df_cache[(df_cache["Nik"].isin(df_f[df_f["SourceResult"] == "DUKCAPIL"]["Nik"])) &
                             (~df_cache["Nik"].isin(nik_dukapil_bca)) &
                             (~df_cache["Nik"].isin(nik_bca_only))]

# 4️⃣ Direct Cache
direct_cache_rows = df_cache[~df_cache["Nik"].isin(pd.concat([
    df_f[df_f["SourceResult"] == "BCA"]["Nik"],
    df_f[df_f["SourceResult"] == "DUKCAPIL"]["Nik"]
]))]

# Jumlah per kategori
st.metric("Total DB_CACHE Rows", len(df_cache))
st.metric("Direct Cache Rows", len(direct_cache_rows))
st.metric("Repeat Paid Rows → Cache", len(df_cache) - len(direct_cache_rows))
st.metric("DUKCAPIL → BCA → DB_CACHE Rows", len(df_dukapil_bca_cache))
st.metric("BCA → DB_CACHE Rows", len(df_bca_cache))
st.metric("DUKCAPIL → DB_CACHE Rows", len(df_dukcapil_cache))

# ======================
# PEAK TIME - HOURLY
# ======================
st.subheader("Peak Time – Hourly Request")

df_f["Hour"] = df_f["CreatedDate"].dt.hour

hourly = df_f.groupby("Hour").size().reset_index(name="Total_Request")

fig_hour = px.bar(
    hourly,
    x="Hour",
    y="Total_Request",
    text="Total_Request"
)
st.plotly_chart(fig_hour, use_container_width=True)

peak_hour = hourly.loc[hourly["Total_Request"].idxmax()]
st.metric(
    "Jam Tersibuk",
    f"{int(peak_hour['Hour'])}:00",
    f"{int(peak_hour['Total_Request']):,} request"
)

# ======================
# PEAK TIME - DAILY
# ======================
st.subheader("Peak Time – Day of Week")

df_f["Day"] = df_f["CreatedDate"].dt.day_name()

day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

daily = (
    df_f.groupby("Day")
    .size()
    .reindex(day_order)
    .reset_index(name="Total_Request")
)

fig_day = px.bar(
    daily,
    x="Day",
    y="Total_Request",
    text="Total_Request"
)
st.plotly_chart(fig_day, use_container_width=True)


