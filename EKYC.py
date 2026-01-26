import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="NIK Verification Analytics", layout="wide")

# ======================
# LOAD & CLEAN DATA
# ======================
FILE_NAME = "LogDUKCAPIL_2025 (1).xlsx"

if not Path(FILE_NAME).exists():
    st.error(f"❌ File '{FILE_NAME}' tidak ditemukan")
    st.stop()

df = pd.read_excel(FILE_NAME)
df.columns = df.columns.str.strip()
df["CreatedDate"] = pd.to_datetime(df["CreatedDate"], errors="coerce")

status_cols = ["NamaDenganGelar", "Nama", "JenisKelamin", "TempatLahir", "TglLahir",
               "Provinsi", "Kabupaten", "Kecamatan", "Kelurahan"]

for c in status_cols:
    if c in df.columns:
        df[c] = df[c].fillna("-")

# ======================
# FILTERS
# ======================
st.sidebar.header(" Filter")

source_filter = st.sidebar.multiselect(
    "Source Result",
    options=sorted(df["SourceResult"].dropna().unique()),
    default=sorted(df["SourceResult"].dropna().unique())
)

date_min = df["CreatedDate"].min().date()
date_max = df["CreatedDate"].max().date()
date_range = st.sidebar.date_input("Periode", [date_min, date_max])

df_f = df[
    (df["SourceResult"].isin(source_filter)) &
    (df["CreatedDate"].dt.date.between(date_range[0], date_range[1]))
]

# ======================
# ANALYTICAL METRICS
# ======================
st.title(" NIK Verification Analytics")

# Hitung metrics
nik_counts = df_f.groupby("Nik").size()
total_nik = nik_counts.shape[0]
total_requests = len(df_f)
avg_hit_per_nik = total_requests / total_nik if total_nik > 0 else 0

# Duplicate rate
duplicate_requests = total_requests - total_nik
duplicate_rate = duplicate_requests / total_requests if total_requests > 0 else 0

# Fraud risk (NIK hit >5x)
high_risk_nik = (nik_counts > 5).sum()
risk_rate = high_risk_nik / total_nik if total_nik > 0 else 0

# Data quality
total_fields = len(df_f) * len(status_cols)
sesuai_count = (df_f[status_cols] == "Sesuai").sum().sum()
quality_score = sesuai_count / total_fields if total_fields > 0 else 0

# Display KPI
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total NIK", f"{total_nik:,}", f"Req: {total_requests:,}")
col2.metric("Duplicate Rate", f"{duplicate_rate:.1%}", f"{duplicate_requests:,} duplikat")
col3.metric("Fraud Risk (>5x)", f"{risk_rate:.1%}", f"{high_risk_nik:,} NIK")
col4.metric("Data Quality", f"{quality_score:.1%}", "avg field accuracy")

# ======================
# ANOMALY DETECTION
# ======================
st.subheader(" Anomaly Detection")

col_a, col_b = st.columns(2)

with col_a:
    # Top repeat offenders
    top_repeat = nik_counts.nlargest(10).reset_index()
    top_repeat.columns = ["NIK", "Hit Count"]
    
    fig_repeat = px.bar(
        top_repeat,
        x="NIK",
        y="Hit Count",
        title="Top 10 Repeat NIK (Fraud Risk)",
        color="Hit Count",
        color_continuous_scale="Reds"
    )
    st.plotly_chart(fig_repeat, use_container_width=True)

with col_b:
    # Hourly anomaly
    df_f["Hour"] = df_f["CreatedDate"].dt.hour
    hourly = df_f.groupby("Hour").size()
    
    mean_hourly = hourly.mean()
    std_hourly = hourly.std()
    
    hourly_df = hourly.reset_index(name="Requests")
    hourly_df["Anomaly"] = hourly_df["Requests"] > (mean_hourly + 2*std_hourly)
    
    fig_hourly = px.bar(
        hourly_df,
        x="Hour",
        y="Requests",
        title="Peak Hours (Red = Anomaly)",
        color="Anomaly",
        color_discrete_map={True: "red", False: "steelblue"}
    )
    st.plotly_chart(fig_hourly, use_container_width=True)

# ======================
# SOURCE PERFORMANCE
# ======================
st.subheader(" Source Performance Analysis")

# Source efficiency
source_stats = df_f.groupby("SourceResult").agg({
    "Nik": "count",
    "Id": "count"
}).rename(columns={"Nik": "Requests", "Id": "Count"})

# Quality per source
source_quality = df_f.groupby("SourceResult")[status_cols].apply(
    lambda x: (x == "Sesuai").sum().sum() / (len(x) * len(status_cols))
).reset_index(name="Quality_Score")

# Unique NIK per source
source_unique = df_f.groupby("SourceResult")["Nik"].nunique().reset_index(name="Unique_NIK")

# Merge all
source_perf = source_stats.merge(source_quality, on="SourceResult").merge(source_unique, on="SourceResult")
source_perf["Duplicate_Rate"] = (source_perf["Requests"] - source_perf["Unique_NIK"]) / source_perf["Requests"]
source_perf["Cost_Efficiency"] = source_perf["Unique_NIK"] / source_perf["Requests"]  # unique/total = efisiensi

# Visualize
fig_source = go.Figure()

fig_source.add_trace(go.Bar(
    name="Quality Score",
    x=source_perf["SourceResult"],
    y=source_perf["Quality_Score"],
    yaxis="y",
    marker_color="lightblue"
))

fig_source.add_trace(go.Scatter(
    name="Cost Efficiency",
    x=source_perf["SourceResult"],
    y=source_perf["Cost_Efficiency"],
    yaxis="y2",
    marker_color="red",
    mode="lines+markers"
))

fig_source.update_layout(
    title="Source Quality vs Cost Efficiency",
    yaxis=dict(title="Quality Score"),
    yaxis2=dict(title="Cost Efficiency", overlaying="y", side="right"),
    hovermode="x"
)

st.plotly_chart(fig_source, use_container_width=True)

# Table
st.dataframe(
    source_perf.style.format({
        "Quality_Score": "{:.1%}",
        "Duplicate_Rate": "{:.1%}",
        "Cost_Efficiency": "{:.1%}"
    }).background_gradient(subset=["Quality_Score", "Cost_Efficiency"], cmap="RdYlGn"),
    use_container_width=True
)

# ======================
# FIELD ACCURACY HEATMAP
# ======================
st.subheader(" Field Accuracy Matrix")

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
    range_color=[0, 100]
)
st.plotly_chart(fig_field, use_container_width=True)

# ======================
# TREND ANALYSIS
# ======================
st.subheader(" Trend Analysis")

col_t1, col_t2 = st.columns(2)

with col_t1:
    # Daily trend
    daily = df_f.groupby(df_f["CreatedDate"].dt.date).agg({
        "Nik": ["count", "nunique"]
    })
    daily.columns = ["Total_Requests", "Unique_NIK"]
    daily["Duplicate_Rate"] = (daily["Total_Requests"] - daily["Unique_NIK"]) / daily["Total_Requests"]
    daily = daily.reset_index()
    
    fig_trend = px.line(
        daily,
        x="CreatedDate",
        y=["Total_Requests", "Unique_NIK"],
        title="Daily Request vs Unique NIK",
        markers=True
    )
    st.plotly_chart(fig_trend, use_container_width=True)

with col_t2:
    # Day of week pattern
    df_f["DayOfWeek"] = df_f["CreatedDate"].dt.day_name()
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    
    dow = df_f.groupby("DayOfWeek").size().reindex(day_order).reset_index(name="Requests")
    
    fig_dow = px.bar(
        dow,
        x="DayOfWeek",
        y="Requests",
        title="Weekly Pattern",
        color="Requests",
        color_continuous_scale="Blues"
    )
    st.plotly_chart(fig_dow, use_container_width=True)

# ======================
# ACTIONABLE INSIGHTS
# ======================
st.subheader(" Actionable Insights")

insights = []

# Insight 1: Fraud risk
if high_risk_nik > 0:
    insights.append(f" **{high_risk_nik} NIK** hit >5x → Investigate for fraud")

# Insight 2: Source efficiency
worst_source = source_perf.loc[source_perf["Cost_Efficiency"].idxmin()]
insights.append(f" **{worst_source['SourceResult']}** has lowest efficiency ({worst_source['Cost_Efficiency']:.1%}) → Consider optimization")

# Insight 3: Field issues
worst_field = field_df.iloc[0]
if worst_field["Accuracy"] < 80:
    insights.append(f" **{worst_field['Field']}** accuracy only {worst_field['Accuracy']:.1f}% → Data quality issue")

# Insight 4: Peak time
peak_hour = hourly_df.loc[hourly_df["Requests"].idxmax()]
insights.append(f" Peak traffic at **{int(peak_hour['Hour'])}:00** ({int(peak_hour['Requests'])} req) → Scale resources")

for i in insights:
    st.markdown(i)

# ======================
# DRILL DOWN
# ======================
with st.expander(" NIK Drill Down"):
    selected_nik = st.selectbox(
        "Search NIK",
        options=[""] + sorted(df["Nik"].dropna().astype(str).unique()),
        format_func=lambda x: "Select NIK..." if x == "" else x
    )
    
    if selected_nik:
        df_nik = df[df["Nik"].astype(str) == selected_nik]
        
        col_n1, col_n2, col_n3 = st.columns(3)
        col_n1.metric("Total Hits", len(df_nik))
        col_n2.metric("Date Range", f"{df_nik['CreatedDate'].min().date()} - {df_nik['CreatedDate'].max().date()}")
        col_n3.metric("Sources Used", df_nik["SourceResult"].nunique())
        
        st.dataframe(
            df_nik.sort_values("CreatedDate", ascending=False)[
                ["CreatedDate", "SourceResult", "SourceApps"] + status_cols
            ],
            use_container_width=True
        )

# ======================
# RAW DATA
# ======================
with st.expander(" Raw Data"):
    st.dataframe(df_f, use_container_width=True)
