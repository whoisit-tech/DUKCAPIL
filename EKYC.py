import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(
    page_title="Dashboard Verifikasi NIK",
    layout="wide"
)

st.title("Dashboard Monitoring Verifikasi NIK")

# ======================
# LOAD EXCEL FILE
# ======================
FILE_NAME = "LogDUKCAPIL_2025 (1).xlsx"

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
st.sidebar.header("🎯 Filter Data")

source_filter = st.sidebar.multiselect(
    "Sumber Hasil",
    options=sorted(df["SourceResult"].dropna().unique()),
    default=sorted(df["SourceResult"].dropna().unique())
)

date_min = df["CreatedDate"].min().date()
date_max = df["CreatedDate"].max().date()

date_range = st.sidebar.date_input(
    "Periode Tanggal",
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
k4.metric("Total Permintaan", f"{len(df_f):,}")

# ======================
# TAMBAHAN: ANALYTICAL METRICS
# ======================
st.markdown("---")
st.subheader("📊 Metrik Analitik")

total_requests = len(df_f)
duplicate_requests = total_requests - total_nik
duplicate_rate = duplicate_requests / total_requests if total_requests > 0 else 0

# Fraud risk
high_risk_nik = (nik_counts > 5).sum()
risk_rate = high_risk_nik / total_nik if total_nik > 0 else 0

# Data quality
total_fields = len(df_f) * len(status_cols)
sesuai_count = (df_f[status_cols] == "Sesuai").sum().sum()
quality_score = sesuai_count / total_fields if total_fields > 0 else 0

ka1, ka2, ka3 = st.columns(3)
ka1.metric("Tingkat Duplikasi", f"{duplicate_rate:.1%}", f"{duplicate_requests:,} permintaan terbuang")
ka2.metric("Risiko Fraud (>5x)", f"{risk_rate:.1%}", f"{high_risk_nik:,} NIK mencurigakan")
ka3.metric("Kualitas Data", f"{quality_score:.1%}", "akurasi field keseluruhan")

# ======================
# ======================
# SOURCE RESULT - STACKED BAR (NIK + TOTAL REQUEST)
# ======================
st.subheader("Distribusi Sumber Hasil (NIK vs Permintaan)")

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
    title="Distribusi NIK per Sumber Hasil (dengan Total Permintaan)",
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
# TAMBAHAN: SOURCE PERFORMANCE ANALYSIS
# ======================
st.subheader("🎯 Analisis Performa Sumber Data")

source_quality = df_f.groupby("SourceResult")[status_cols].apply(
    lambda x: (x == "Sesuai").sum().sum() / (len(x) * len(status_cols))
).reset_index(name="Quality_Score")

source_unique = df_f.groupby("SourceResult")["Nik"].nunique().reset_index(name="Unique_NIK")
source_total = df_f.groupby("SourceResult").size().reset_index(name="Total_Requests")

source_perf = source_total.merge(source_unique, on="SourceResult").merge(source_quality, on="SourceResult")
source_perf["Cost_Efficiency"] = source_perf["Unique_NIK"] / source_perf["Total_Requests"]
source_perf["Duplicate_Rate"] = 1 - source_perf["Cost_Efficiency"]

fig_perf = go.Figure()

fig_perf.add_trace(go.Bar(
    name="Skor Kualitas",
    x=source_perf["SourceResult"],
    y=source_perf["Quality_Score"],
    yaxis="y",
    marker_color="lightblue"
))

fig_perf.add_trace(go.Scatter(
    name="Efisiensi Biaya",
    x=source_perf["SourceResult"],
    y=source_perf["Cost_Efficiency"],
    yaxis="y2",
    marker_color="red",
    mode="lines+markers",
    line=dict(width=3)
))

fig_perf.update_layout(
    title="Trade-off Kualitas vs Efisiensi per Sumber",
    yaxis=dict(title="Skor Kualitas", range=[0, 1]),
    yaxis2=dict(title="Efisiensi Biaya", overlaying="y", side="right", range=[0, 1]),
    hovermode="x unified"
)

st.plotly_chart(fig_perf, use_container_width=True)

st.dataframe(
    source_perf.style.format({
        "Quality_Score": "{:.1%}",
        "Duplicate_Rate": "{:.1%}",
        "Cost_Efficiency": "{:.1%}"
    }).background_gradient(subset=["Quality_Score", "Cost_Efficiency"], cmap="RdYlGn"),
    use_container_width=True
)

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
# TAMBAHAN: FIELD ACCURACY RANKING
# ======================
st.subheader("🎯 Field Accuracy Ranking")

field_accuracy = (df_f[status_cols] == "Sesuai").mean() * 100
field_df = field_accuracy.reset_index()
field_df.columns = ["Field", "Accuracy"]
field_df = field_df.sort_values("Accuracy")

fig_field = px.bar(
    field_df,
    x="Accuracy",
    y="Field",
    orientation="h",
    title="Field Verification Accuracy (%)",
    color="Accuracy",
    color_continuous_scale="RdYlGn",
    range_color=[0, 100],
    text="Accuracy"
)
fig_field.update_traces(texttemplate='%{text:.1f}%', textposition='outside')

st.plotly_chart(fig_field, use_container_width=True)

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
# TAMBAHAN: FRAUD RISK VISUALIZATION
# ======================
st.subheader("⚠️ Fraud Risk Analysis - Top 10 Suspicious NIK")

top_repeat = nik_counts.nlargest(10).reset_index()
top_repeat.columns = ["NIK", "Hit_Count"]

fig_fraud = px.bar(
    top_repeat,
    x="NIK",
    y="Hit_Count",
    title="Top 10 Most Repeated NIK (Potential Fraud)",
    color="Hit_Count",
    color_continuous_scale="Reds",
    text="Hit_Count"
)
fig_fraud.update_traces(textposition='outside')

st.plotly_chart(fig_fraud, use_container_width=True)

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
# TAMBAHAN: TREND WITH UNIQUE NIK
# ======================
st.subheader("📈 Request vs Unique NIK Trend")

daily_detailed = df_f.groupby(df_f["CreatedDate"].dt.date).agg({
    "Nik": ["count", "nunique"]
})
daily_detailed.columns = ["Total_Requests", "Unique_NIK"]
daily_detailed = daily_detailed.reset_index()
daily_detailed.columns = ["Date", "Total_Requests", "Unique_NIK"]

fig_trend_detail = go.Figure()

fig_trend_detail.add_trace(go.Scatter(
    x=daily_detailed["Date"],
    y=daily_detailed["Total_Requests"],
    name="Total Requests",
    mode="lines+markers",
    line=dict(color="steelblue", width=2)
))

fig_trend_detail.add_trace(go.Scatter(
    x=daily_detailed["Date"],
    y=daily_detailed["Unique_NIK"],
    name="Unique NIK",
    mode="lines+markers",
    line=dict(color="green", width=2)
))

fig_trend_detail.update_layout(
    title="Daily Requests vs Unique NIK (Gap = Duplicates)",
    hovermode="x unified"
)

st.plotly_chart(fig_trend_detail, use_container_width=True)

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
# TAMBAHAN: HOURLY ANOMALY DETECTION
# ======================
mean_hourly = hourly["Total_Request"].mean()
std_hourly = hourly["Total_Request"].std()
hourly["Anomaly"] = hourly["Total_Request"] > (mean_hourly + 2*std_hourly)
hourly["Status"] = hourly["Anomaly"].apply(lambda x: "Anomaly" if x else "Normal")

fig_anomaly = px.bar(
    hourly,
    x="Hour",
    y="Total_Request",
    title="Hourly Traffic with Anomaly Detection (>2σ)",
    color="Status",
    color_discrete_map={"Normal": "steelblue", "Anomaly": "red"},
    text="Total_Request"
)
st.plotly_chart(fig_anomaly, use_container_width=True)

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

# ======================
# FRAUD DETECTION ANALYSIS
# ======================
st.markdown("---")
st.subheader("🚨 Deteksi Fraud & Anomali")

# 1. SAME APP ID ANOMALY
st.markdown("### 1️⃣ Pola SourceApps yang Sama (Potensi Bot/Script)")

same_app = df_f.groupby(["SourceApps", "Nik"]).size().reset_index(name="Hit_Count")
same_app_suspicious = same_app[same_app["Hit_Count"] > 3].sort_values("Hit_Count", ascending=False)

if len(same_app_suspicious) > 0:
    st.error(f"⚠️ Ditemukan **{len(same_app_suspicious)}** kombinasi SourceApps-NIK dengan hit >3x")
    
    # Group by app
    app_summary = same_app_suspicious.groupby("SourceApps").agg({
        "Nik": "count",
        "Hit_Count": "sum"
    }).reset_index()
    app_summary.columns = ["SourceApps", "Unique_NIK", "Total_Hits"]
    app_summary = app_summary.sort_values("Total_Hits", ascending=False)
    
    col_app1, col_app2 = st.columns([1, 2])
    
    with col_app1:
        st.dataframe(
            app_summary.head(10),
            use_container_width=True
        )
    
    with col_app2:
        fig_app = px.bar(
            app_summary.head(10),
            x="SourceApps",
            y="Total_Hits",
            color="Unique_NIK",
            title="Top SourceApps Mencurigakan",
            text="Total_Hits"
        )
        st.plotly_chart(fig_app, use_container_width=True)
    
    st.markdown("**Detail Pola Mencurigakan:**")
    st.dataframe(
        same_app_suspicious.head(20),
        use_container_width=True
    )
else:
    st.success("✅ Tidak ada pola mencurigakan pada SourceApps")

# 2. STATUS DEGRADATION (Sesuai → Tidak Sesuai)
st.markdown("### 2️⃣ Analisis Degradasi Status (Sesuai → Tidak Sesuai)")

# Cari NIK dengan pattern Sesuai → Tidak Sesuai berdasarkan history
degradation_results = []

for nik in df_f["Nik"].unique():
    df_nik_check = df_f[df_f["Nik"] == nik].sort_values("CreatedDate")
    
    if len(df_nik_check) > 1:
        for col in status_cols:
            statuses = df_nik_check[col].tolist()
            dates = df_nik_check["CreatedDate"].tolist()
            sources = df_nik_check["SourceResult"].tolist()
            apps = df_nik_check["SourceApps"].tolist()
            
            # Cek ada pattern Sesuai diikuti Tidak Sesuai dalam chronological order
            for i in range(len(statuses)-1):
                if statuses[i] == "Sesuai" and statuses[i+1] == "Tidak Sesuai":
                    degradation_results.append({
                        "NIK": nik,
                        "Field": col,
                        "Status_Awal": "Sesuai",
                        "Status_Akhir": "Tidak Sesuai",
                        "Tanggal_Cek_Pertama": dates[i],
                        "Tanggal_Degradasi": dates[i+1],
                        "Selisih_Waktu_Jam": (dates[i+1] - dates[i]).total_seconds() / 3600,
                        "Sumber_Pertama": sources[i],
                        "Sumber_Degradasi": sources[i+1],
                        "App_Pertama": apps[i],
                        "App_Degradasi": apps[i+1],
                        "Total_Hit_NIK": len(df_nik_check)
                    })

if len(degradation_results) > 0:
    df_degrade = pd.DataFrame(degradation_results)
    
    st.error(f"🔴 **CRITICAL**: Ditemukan **{len(df_degrade)}** kasus degradasi status (Sesuai → Tidak Sesuai)")
    
    # Summary metrics
    col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
    col_sum1.metric("Total Kasus", len(df_degrade))
    col_sum2.metric("NIK Terpengaruh", df_degrade["NIK"].nunique())
    col_sum3.metric("Rata² Selisih Waktu", f"{df_degrade['Selisih_Waktu_Jam'].mean():.1f} jam")
    col_sum4.metric("Field Paling Terpengaruh", df_degrade["Field"].value_counts().index[0])
    
    # Summary by field
    degrade_by_field = df_degrade.groupby("Field").agg({
        "NIK": "nunique",
        "Selisih_Waktu_Jam": "mean"
    }).reset_index()
    degrade_by_field.columns = ["Field", "NIK_Terpengaruh", "Rata_Selisih_Waktu_Jam"]
    degrade_by_field = degrade_by_field.sort_values("NIK_Terpengaruh", ascending=False)
    
    col_deg1, col_deg2 = st.columns([1, 2])
    
    with col_deg1:
        st.markdown("**Degradasi per Field:**")
        st.dataframe(degrade_by_field, use_container_width=True)
    
    with col_deg2:
        fig_degrade = px.bar(
            degrade_by_field,
            x="Field",
            y="NIK_Terpengaruh",
            title="Degradasi Status per Field",
            color="NIK_Terpengaruh",
            color_continuous_scale="Reds",
            text="NIK_Terpengaruh"
        )
        fig_degrade.update_traces(textposition='outside')
        st.plotly_chart(fig_degrade, use_container_width=True)
    
    # Summary by Source
    st.markdown("**Degradasi per Transisi Sumber:**")
    degrade_by_source = df_degrade.groupby(["Sumber_Pertama", "Sumber_Degradasi"]).size().reset_index(name="Jumlah")
    degrade_by_source = degrade_by_source.sort_values("Jumlah", ascending=False)
    
    col_src1, col_src2 = st.columns([1, 1])
    
    with col_src1:
        st.dataframe(degrade_by_source, use_container_width=True)
    
    with col_src2:
        fig_source_degrade = px.bar(
            degrade_by_source.head(10),
            x="Jumlah",
            y=[f"{row['Sumber_Pertama']} → {row['Sumber_Degradasi']}" for _, row in degrade_by_source.head(10).iterrows()],
            orientation='h',
            title="Top 10 Pola Transisi Sumber",
            color="Jumlah",
            color_continuous_scale="Reds"
        )
        st.plotly_chart(fig_source_degrade, use_container_width=True)
    
    # FULL TABLE - SEMUA DATA
    st.markdown("---")
    st.markdown(f"**📋 Log Degradasi Lengkap - Semua {len(df_degrade)} Kasus:**")
    
    # Format untuk display
    df_degrade_display = df_degrade.copy()
    df_degrade_display["Tanggal_Cek_Pertama"] = df_degrade_display["Tanggal_Cek_Pertama"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_degrade_display["Tanggal_Degradasi"] = df_degrade_display["Tanggal_Degradasi"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_degrade_display["Selisih_Waktu_Jam"] = df_degrade_display["Selisih_Waktu_Jam"].round(2)
    
    # Sort by degraded date descending
    df_degrade_display = df_degrade_display.sort_values("Tanggal_Degradasi", ascending=False)
    
    st.dataframe(
        df_degrade_display,
        use_container_width=True,
        height=600
    )
    
    # Download button
    csv = df_degrade_display.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Log Degradasi Lengkap (CSV)",
        data=csv,
        file_name=f"log_degradasi_status_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
    
else:
    st.success("✅ Tidak ada degradasi status - Semua verifikasi konsisten")

# 3. RAPID FIRE PATTERN (Multiple hits dalam waktu singkat)
st.markdown("### 3️⃣ Rapid Fire Pattern (Bot Detection)")

df_f_sorted = df_f.sort_values(["Nik", "CreatedDate"])
df_f_sorted["Time_Diff"] = df_f_sorted.groupby("Nik")["CreatedDate"].diff().dt.total_seconds()

# Hit dalam waktu < 5 detik
rapid_fire = df_f_sorted[df_f_sorted["Time_Diff"] < 5].copy()

if len(rapid_fire) > 0:
    st.error(f"⚠️ Ditemukan **{len(rapid_fire)}** request dengan interval <5 detik (possible bot)")
    
    rapid_summary = rapid_fire.groupby("Nik").agg({
        "Id": "count",
        "Time_Diff": "mean",
        "SourceApps": lambda x: x.iloc[0]
    }).reset_index()
    rapid_summary.columns = ["NIK", "Rapid_Hits", "Avg_Interval_Sec", "SourceApps"]
    rapid_summary = rapid_summary.sort_values("Rapid_Hits", ascending=False)
    
    col_rapid1, col_rapid2 = st.columns([1, 1])
    
    with col_rapid1:
        st.dataframe(
            rapid_summary.head(15),
            use_container_width=True
        )
    
    with col_rapid2:
        fig_rapid = px.scatter(
            rapid_summary.head(20),
            x="Avg_Interval_Sec",
            y="Rapid_Hits",
            size="Rapid_Hits",
            color="Rapid_Hits",
            hover_data=["NIK", "SourceApps"],
            title="Rapid Fire Pattern Analysis",
            color_continuous_scale="Reds"
        )
        st.plotly_chart(fig_rapid, use_container_width=True)
else:
    st.success("✅ Tidak ada rapid fire pattern")

# 4. CROSS-SOURCE INCONSISTENCY
st.markdown("### 4️⃣ Cross-Source Data Inconsistency")

cross_inconsistency = []

for nik in df_f["Nik"].unique():
    df_nik_cross = df_f[df_f["Nik"] == nik]
    
    if df_nik_cross["SourceResult"].nunique() > 1:
        for col in status_cols:
            statuses_by_source = df_nik_cross.groupby("SourceResult")[col].apply(lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0])
            
            if statuses_by_source.nunique() > 1:
                cross_inconsistency.append({
                    "NIK": nik,
                    "Field": col,
                    "Sources": ", ".join(statuses_by_source.index.tolist()),
                    "Values": ", ".join(statuses_by_source.values.tolist()),
                    "Hit_Count": len(df_nik_cross)
                })

if len(cross_inconsistency) > 0:
    df_cross = pd.DataFrame(cross_inconsistency)
    
    st.warning(f"⚠️ Ditemukan **{len(df_cross)}** kasus inconsistency antar source")
    
    cross_summary = df_cross.groupby("Field").size().reset_index(name="Inconsistency_Count")
    cross_summary = cross_summary.sort_values("Inconsistency_Count", ascending=False)
    
    col_cross1, col_cross2 = st.columns([1, 2])
    
    with col_cross1:
        st.dataframe(cross_summary, use_container_width=True)
    
    with col_cross2:
        fig_cross = px.bar(
            cross_summary,
            x="Field",
            y="Inconsistency_Count",
            title="Cross-Source Inconsistency by Field",
            color="Inconsistency_Count",
            color_continuous_scale="Oranges"
        )
        st.plotly_chart(fig_cross, use_container_width=True)
    
    st.markdown("**Detail Inconsistency Cases (Top 20):**")
    st.dataframe(
        df_cross.head(20),
        use_container_width=True
    )
else:
    st.success("✅ Data konsisten antar source")

# ======================
# TAMBAHAN: ACTIONABLE INSIGHTS
# ======================
st.markdown("---")
st.subheader("💡 Actionable Insights & Recommendations")

insights_col1, insights_col2 = st.columns(2)

with insights_col1:
    st.markdown("### ⚠️ Issues Detected")
    
    # Fraud risk
    if high_risk_nik > 0:
        st.error(f"🚨 **{high_risk_nik} NIK** dengan hit >5x → Investigate for potential fraud")
    
    # Same app pattern
    if len(same_app_suspicious) > 0:
        st.error(f"🤖 **{len(same_app_suspicious)}** suspicious SourceApps patterns → Possible bot activity")
    
    # Status degradation
    if len(degradation_results) > 0:
        st.error(f"🔄 **{len(degradation_results)}** status degradations detected → Data integrity issue")
    
    # Rapid fire
    if len(rapid_fire) > 0:
        st.error(f"⚡ **{len(rapid_fire)}** rapid fire requests → Bot detection")
    
    # Low efficiency source
    worst_source = source_perf.loc[source_perf["Cost_Efficiency"].idxmin()]
    if worst_source["Cost_Efficiency"] < 0.8:
        st.warning(f"💰 **{worst_source['SourceResult']}** efficiency hanya {worst_source['Cost_Efficiency']:.1%} → Optimize caching")
    
    # Field accuracy
    worst_field = field_df.iloc[0]
    if worst_field["Accuracy"] < 80:
        st.warning(f"📋 **{worst_field['Field']}** accuracy {worst_field['Accuracy']:.1f}% → Check data quality")

with insights_col2:
    st.markdown("### ✅ Recommendations")
    
    st.success(f"⏰ Peak hour: **{int(peak_hour['Hour'])}:00** → Scale infrastructure during this time")
    
    best_source = source_perf.loc[source_perf["Cost_Efficiency"].idxmax()]
    st.success(f"🎯 **{best_source['SourceResult']}** has best efficiency ({best_source['Cost_Efficiency']:.1%}) → Use as primary source")
    
    if duplicate_rate > 0.3:
        st.info(f"♻️ {duplicate_rate:.1%} duplicate rate → Implement better caching strategy")
    
    if len(rapid_fire) > 0:
        st.info("🛡️ Implement rate limiting & CAPTCHA for suspicious SourceApps")
    
    if len(degradation_results) > 0:
        st.info("🔍 Audit data source reliability & implement version control")

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
else:
    st.info("👆 Pilih NIK dari dropdown untuk melihat detail")

# ======================
# RAW DATA
# ======================
with st.expander("Raw Data"):
    st.dataframe(df_f, use_container_width=True)
