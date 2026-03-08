# Streamlit dashboard
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Ringostat RevOps Dashboard", layout="wide")

# ── Load & clean ──────────────────────────────────────────────────────────────

@st.cache_data
def load_data():
    df = pd.read_excel("data/deals.xlsx", sheet_name="база угод")

    # Parse dates
    df["AQL date"] = pd.to_datetime(df["AQL date"], format="mixed", errors="coerce")
    df["Closing Date"] = pd.to_datetime(df["Closing Date"], format="mixed", errors="coerce")

    # Normalize PPC budget
    budget_order = ["0-500", "500-1000", "1000-2000", "2000-5000",
                    "5000-10000", "20000+", "Unknown"]

    def normalize_budget(val):
        if pd.isna(val):
            return "Unknown"
        if isinstance(val, (int, float)):
            return "0-500"
        return str(val).strip() if str(val).strip() in budget_order else "Unknown"

    df["PPC budget USD"] = df["PPC budget USD"].apply(normalize_budget)
    df["PPC budget USD"] = pd.Categorical(df["PPC budget USD"], categories=budget_order, ordered=True)

    return df

df = load_data()

# ── Sidebar filters ───────────────────────────────────────────────────────────

st.sidebar.header("Filters")

all_countries = sorted(df["Client country"].dropna().unique().tolist())
sel_countries = st.sidebar.multiselect("Client country", all_countries, default=all_countries)

all_crms = sorted(df["Client CRM"].dropna().unique().tolist())
sel_crms = st.sidebar.multiselect("Client CRM", all_crms, default=all_crms)

min_date = df["AQL date"].min().date()
max_date = df["AQL date"].max().date()
start_date = st.sidebar.date_input("Start date", value=min_date, min_value=min_date, max_value=max_date)
end_date   = st.sidebar.date_input("End date",   value=max_date, min_value=min_date, max_value=max_date)

# Apply filters
mask = (
    df["Client country"].isin(sel_countries) &
    df["Client CRM"].isin(sel_crms) &
    (df["AQL date"].dt.date >= start_date) &
    (df["AQL date"].dt.date <= end_date)
)
fdf = df[mask].copy()

# ── Helper ────────────────────────────────────────────────────────────────────

def win_rate(sub: pd.DataFrame) -> float:
    closed = sub[sub["Stage"].isin(["Closed Won", "Closed Lost"])]
    if len(closed) == 0:
        return float("nan")
    return round(closed[closed["Stage"] == "Closed Won"].shape[0] / len(closed) * 100, 1)

# ── Top metrics ───────────────────────────────────────────────────────────────

st.title("Ringostat RevOps Dashboard")

total       = len(fdf)
won         = fdf[fdf["Stage"] == "Closed Won"].shape[0]
lost        = fdf[fdf["Stage"] == "Closed Lost"].shape[0]
wr          = win_rate(fdf)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deals", total)
c2.metric("Win Rate %", f"{wr:.1f}%" if not pd.isna(wr) else "N/A")
c3.metric("Closed Won", won)
c4.metric("Closed Lost", lost)

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────

col_left, col_right = st.columns(2)

# 1. Win Rate by Country
with col_left:
    st.subheader("Win Rate by Country")
    closed_df = fdf[fdf["Stage"].isin(["Closed Won", "Closed Lost"])]
    country_stats = (
        closed_df.groupby("Client country")
        .apply(lambda g: pd.Series({
            "closed": len(g),
            "win_rate": round(g[g["Stage"] == "Closed Won"].shape[0] / len(g) * 100, 1)
        }))
        .reset_index()
    )
    country_stats = country_stats[country_stats["closed"] >= 5].sort_values("win_rate", ascending=True)
    if not country_stats.empty:
        fig = px.bar(country_stats, x="win_rate", y="Client country", orientation="h",
                     labels={"win_rate": "Win Rate %", "Client country": "Country"},
                     text="win_rate")
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough data (need ≥ 5 closed deals per country).")

# 2. Win Rate by CRM
with col_right:
    st.subheader("Win Rate by CRM")
    crm_stats = (
        closed_df.groupby("Client CRM")
        .apply(lambda g: pd.Series({
            "closed": len(g),
            "win_rate": round(g[g["Stage"] == "Closed Won"].shape[0] / len(g) * 100, 1)
        }))
        .reset_index()
    )
    crm_stats = crm_stats[crm_stats["closed"] >= 5].sort_values("win_rate", ascending=True)
    if not crm_stats.empty:
        fig2 = px.bar(crm_stats, x="win_rate", y="Client CRM", orientation="h",
                      labels={"win_rate": "Win Rate %", "Client CRM": "CRM"},
                      text="win_rate")
        fig2.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Not enough data (need ≥ 5 closed deals per CRM).")

col_left2, col_right2 = st.columns(2)

# 3. Deal Distribution by Stage
with col_left2:
    st.subheader("Deal Distribution by Stage")
    stage_data = fdf["Stage"].fillna("Missing stage").value_counts().reset_index()
    stage_data.columns = ["Stage", "Count"]
    fig3 = px.pie(stage_data, names="Stage", values="Count")
    st.plotly_chart(fig3, use_container_width=True)

# 4. Deals by Source
with col_right2:
    st.subheader("Deals by Source")
    source_data = fdf["Source"].dropna().value_counts().reset_index()
    source_data.columns = ["Source", "Count"]
    source_data = source_data.sort_values("Count", ascending=True)
    fig4 = px.bar(source_data, x="Count", y="Source", orientation="h",
                  labels={"Count": "Number of Deals"},
                  text="Count")
    fig4.update_traces(textposition="outside")
    st.plotly_chart(fig4, use_container_width=True)

# 5. Win Rate by PPC Budget
st.subheader("Win Rate by PPC Budget")
budget_stats = (
    closed_df.groupby("PPC budget USD", observed=True)
    .apply(lambda g: round(g[g["Stage"] == "Closed Won"].shape[0] / len(g) * 100, 1))
    .reset_index()
)
budget_stats.columns = ["PPC budget USD", "Win Rate %"]
fig5 = px.bar(budget_stats, x="PPC budget USD", y="Win Rate %",
              text="Win Rate %")
fig5.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
st.plotly_chart(fig5, use_container_width=True)

st.divider()

# ── Data Quality Issues ───────────────────────────────────────────────────────

st.subheader("Data Quality Issues")

issues = []

for idx, row in fdf.iterrows():
    excel_row = idx + 2  # 1-based header + 1

    if row["Stage"] in ("Closed Won", "Closed Lost") and pd.isna(row["Closing Date"]):
        issues.append({**row, "Excel row": excel_row, "Issue": "Closed stage but no Closing Date"})

    if pd.isna(row["Stage"]) or row["Stage"] is None:
        issues.append({**row, "Excel row": excel_row, "Issue": "Missing Stage"})

    if pd.isna(row["Client country"]) or row["Client country"] is None:
        issues.append({**row, "Excel row": excel_row, "Issue": "Missing Client country"})

    if pd.isna(row["Source"]) or row["Source"] is None:
        issues.append({**row, "Excel row": excel_row, "Issue": "Missing Source"})

    if pd.isna(row["AQL date"]):
        issues.append({**row, "Excel row": excel_row, "Issue": "Unparseable AQL date"})

if issues:
    issues_df = pd.DataFrame(issues)[
        ["Excel row", "AQL date", "Source", "Client country", "Stage", "Closing Date", "Issue"]
    ]
    st.dataframe(issues_df, use_container_width=True)
    st.caption(f"Total issues: {len(issues_df)}")
else:
    st.success("No data quality issues found.")

st.divider()

# ── RevOps Insights Summary ───────────────────────────────────────────────────

st.subheader("RevOps Insights Summary")

benchmark = 25.0

# Recalculate on filtered data
total_wr = win_rate(fdf)

# Top/worst countries (>=5 closed deals)
if not country_stats.empty:
    sorted_countries = country_stats.sort_values("win_rate", ascending=False)
    top3    = sorted_countries.head(3)[["Client country", "win_rate"]].values.tolist()
    worst3  = sorted_countries.tail(3)[["Client country", "win_rate"]].values.tolist()
    top3_str    = ", ".join(f"{c} ({w:.1f}%)" for c, w in top3)
    worst3_str  = ", ".join(f"{c} ({w:.1f}%)" for c, w in worst3)
else:
    top3_str = worst3_str = "Not enough data"

# Best source by win rate (>=5 closed deals)
source_wr = (
    closed_df.groupby("Source")
    .apply(lambda g: pd.Series({"closed": len(g),
                                "wr": round(g[g["Stage"] == "Closed Won"].shape[0] / len(g) * 100, 1)}))
    .reset_index()
)
source_wr = source_wr[source_wr["closed"] >= 5].sort_values("wr", ascending=False)
best_source = f"{source_wr.iloc[0]['Source']} ({source_wr.iloc[0]['wr']:.1f}%)" if not source_wr.empty else "N/A"

# No CRM share and win rate
no_crm_df   = fdf[fdf["Client CRM"] == "No CRM"]
no_crm_pct  = round(len(no_crm_df) / total * 100, 1) if total > 0 else 0
no_crm_wr   = win_rate(no_crm_df)

# Data quality count
dq_count = len(issues)

# Most frequent loss reason
loss_reasons = fdf[
    (fdf["Stage"] == "Closed Lost") &
    fdf["Loss reason description"].notna()
]["Loss reason description"]
top_loss = loss_reasons.value_counts().idxmax() if not loss_reasons.empty else "N/A"
top_loss_count = int(loss_reasons.value_counts().max()) if not loss_reasons.empty else 0

# Compare win rate to benchmark
wr_vs_bench = (
    f"**above** benchmark ({total_wr:.1f}% vs {benchmark}%)" if total_wr >= benchmark
    else f"**below** benchmark ({total_wr:.1f}% vs {benchmark}%)"
)

insights_md = f"""
- **Overall win rate:** {total_wr:.1f}% — {wr_vs_bench} (SaaS average).
- **Top-3 countries by win rate** (≥ 5 closed deals): {top3_str}.
- **Worst-3 countries by win rate**: {worst3_str}.
- **Best-performing source:** {best_source}.
- **Deals without CRM ("No CRM"):** {no_crm_pct:.1f}% of total; win rate {no_crm_wr:.1f}% vs overall {total_wr:.1f}%.
- **Data quality issues found:** {dq_count}.
- **Most frequent loss reason:** "{top_loss}" ({top_loss_count} deals).
"""

st.info(insights_md)
