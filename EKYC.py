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
# KPI PER NIK
# ======================

# Hitung kemunculan per NIK
nik_counts = df_f.groupby("Nik").size()

# Total NIK (per orang)
total_nik = nik_counts.shape[0]

# NIK hit 1 kali
nik_hit_1 = (nik_counts == 1).sum()

# NIK hit lebih dari 1 kali
nik_hit_gt1 = (nik_counts > 1).sum()

# Persentase (basis per NIK)
pct_hit_1 = nik_hit_1 / total_nik if total_nik else 0
pct_hit_gt1 = nik_hit_gt1 / total_nik if total_nik else 0


# ======================
# DISPLAY KPI
# ======================
k1, k2, k3, k4 = st.columns(4)

k1.metric("Total NIK", f"{total_nik:,}")
k2.metric("NIK Hit 1x", f"{nik_hit_1:,}", f"{pct_hit_1:.2%}")
k3.metric("NIK Hit >1x", f"{nik_hit_gt1:,}", f"{pct_hit_gt1:.2%}")
k4.metric("Total Request", f"{len(df_f):,}")

# ======================
# ======================
# SOURCE RESULT - STACKED BAR (NIK + TOTAL REQUEST)
# ======================
st.subheader("Source Result Distribution (NIK vs Request)")

# Hitung hit per NIK per SourceResult
nik_source = (
    df_f
    .groupby(["SourceResult", "Nik"])
    .size()
    .reset_index(name="hit_count")
)

nik_source["hit_type"] = nik_source["hit_count"].apply(
    lambda x: "Hit 1x" if x == 1 else "Hit >1x"
)

# Agregasi NIK
src_nik_stack = (
    nik_source
    .groupby(["SourceResult", "hit_type"])
    .size()
    .reset_index(name="nik_count")
)

# Total request per source
src_request = (
    df_f
    .groupby("SourceResult")
    .size()
    .reset_index(name="total_request")
)

# Merge supaya bisa kasih label request
src_chart = src_nik_stack.merge(
    src_request,
    on="SourceResult",
    how="left"
)

# Plot
fig_src = px.bar(
    src_chart,
    x="SourceResult",
    y="nik_count",
    color="hit_type",
    text="nik_count",
    title="NIK Distribution per Source Result (with Total Request)",
    labels={
        "nik_count": "Jumlah NIK",
        "hit_type": "Kategori Hit"
    }
)

# Tambahin total request di atas bar
fig_src.update_traces(
    textposition="inside"
)

fig_src.update_xaxes(categoryorder="total descending")

# Tambah anotasi total request
for i, row in src_request.iterrows():
    fig_src.add_annotation(
        x=row["SourceResult"],
        y=src_nik_stack[src_nik_stack["SourceResult"] == row["SourceResult"]]["nik_count"].sum(),
        text=f"Req: {row['total_request']:,}",
        showarrow=False,
        yshift=10
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
# SIDEBAR - NIK DRILL DOWN
# ======================
st.sidebar.subheader("🔍 NIK Drill Down")

nik_list = sorted(df["Nik"].dropna().astype(str).unique())

nik_options = [""] + nik_list  # opsi kosong

selected_nik = st.sidebar.selectbox(
    "Cari NIK",
    options=nik_options,
    format_func=lambda x: "Ketik NIK..." if x == "" else x
)

# Drill-down data
if selected_nik != "":
    df_nik = df[df["Nik"].astype(str) == selected_nik]
else:
    df_nik = df.iloc[0:0]

###

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
# CACHE EFFICIENCY / COST ANALYSIS
# ======================
st.subheader("Cache Efficiency / Repeat Paid Analysis (Per NIK & Per Row)")

# Urutkan data berdasarkan waktu
df_sorted = df_f.sort_values("CreatedDate")

# Ambil sequence SourceResult per NIK
nik_seq = (
    df_sorted
    .groupby("Nik")["SourceResult"]
    .apply(list)
)

# Inisialisasi kategori (per NIK, non-overlap)
direct_cache = set()
bca_cache = set()
dukcapil_cache = set()
dukcapil_bca_cache = set()

# Klasifikasi per NIK
for nik, seq in nik_seq.items():

    if "DB_CACHE" not in seq:
        continue

    # 1️⃣ Direct DB_CACHE
    if seq == ["DB_CACHE"]:
        direct_cache.add(nik)

    # 2️⃣ DUKCAPIL → BCA → DB_CACHE
    elif "DUKCAPIL" in seq and "BCA" in seq:
        if seq.index("DUKCAPIL") < seq.index("BCA") < seq.index("DB_CACHE"):
            dukcapil_bca_cache.add(nik)

    # 3️⃣ BCA → DB_CACHE (tanpa DUKCAPIL)
    elif "BCA" in seq and "DUKCAPIL" not in seq:
        if seq.index("BCA") < seq.index("DB_CACHE"):
            bca_cache.add(nik)

    # 4️⃣ DUKCAPIL → DB_CACHE (tanpa BCA)
    elif "DUKCAPIL" in seq and "BCA" not in seq:
        if seq.index("DUKCAPIL") < seq.index("DB_CACHE"):
            dukcapil_cache.add(nik)

# Fungsi hitung row (request)
def count_rows(nik_set):
    return df_f[df_f["Nik"].isin(nik_set)].shape[0]

# ======================
# KPI OUTPUT
# ======================
c1, c2 = st.columns(2)
c1.metric("Direct DB_CACHE (NIK)", len(direct_cache))
c2.metric("Direct DB_CACHE (Rows)", count_rows(direct_cache))

c3, c4 = st.columns(2)
c3.metric("BCA → DB_CACHE (NIK)", len(bca_cache))
c4.metric("BCA → DB_CACHE (Rows)", count_rows(bca_cache))

c5, c6 = st.columns(2)
c5.metric("DUKCAPIL → DB_CACHE (NIK)", len(dukcapil_cache))
c6.metric("DUKCAPIL → DB_CACHE (Rows)", count_rows(dukcapil_cache))

c7, c8 = st.columns(2)
c7.metric("DUKCAPIL → BCA → DB_CACHE (NIK)", len(dukcapil_bca_cache))
c8.metric("DUKCAPIL → BCA → DB_CACHE (Rows)", count_rows(dukcapil_bca_cache))

# ======================
# TOTAL SUMMARY
# ======================
total_nik_cache = (
    len(direct_cache)
    + len(bca_cache)
    + len(dukcapil_cache)
    + len(dukcapil_bca_cache)
)

total_rows_cache = count_rows(
    direct_cache
    | bca_cache
    | dukcapil_cache
    | dukcapil_bca_cache
)

st.markdown("---")
st.metric("Total NIK with DB_CACHE", total_nik_cache)
st.metric("Total DB_CACHE Related Rows", total_rows_cache)

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










