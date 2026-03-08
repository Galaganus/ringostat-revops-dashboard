# Streamlit dashboard
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Ringostat RevOps Dashboard", layout="wide")

# ── Color palette ──────────────────────────────────────────────────────────────

COLOR_PRIMARY = "#4F46E5"   # indigo
COLOR_WON     = "#10B981"   # green
COLOR_LOST    = "#EF4444"   # red
COLOR_NEUTRAL = "#6B7280"   # gray

STAGE_COLORS = {
    "Closed Won":    "#10B981",
    "Closed Lost":   "#EF4444",
    "Negotiations":  "#F59E0B",
    "Project set up":"#3B82F6",
    "Trial":         "#8B5CF6",
    "Payment":       "#06B6D4",
    "Missing stage": "#D1D5DB",
}

CHART_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=40, t=40, b=0),
    yaxis=dict(showgrid=False),
    xaxis=dict(showgrid=False),
)

BUDGET_ORDER = ["0-500", "500-1000", "1000-2000", "2000-5000",
                "5000-10000", "20000+", "Unknown"]

# ── Load & clean ──────────────────────────────────────────────────────────────

@st.cache_data
def load_data():
    raw = pd.read_excel("data/deals.xlsx", sheet_name="база угод")

    raw["AQL date"]     = pd.to_datetime(raw["AQL date"],     format="mixed", errors="coerce")
    raw["Closing Date"] = pd.to_datetime(raw["Closing Date"], format="mixed", errors="coerce")

    def normalize_budget(val):
        if pd.isna(val):
            return "Unknown"
        if isinstance(val, (int, float)):
            return "0-500"
        return str(val).strip() if str(val).strip() in BUDGET_ORDER else "Unknown"

    raw["PPC budget USD"] = raw["PPC budget USD"].apply(normalize_budget)
    raw["PPC budget USD"] = pd.Categorical(raw["PPC budget USD"],
                                           categories=BUDGET_ORDER, ordered=True)
    return raw

df = load_data()

# ── Sidebar filters ───────────────────────────────────────────────────────────

st.sidebar.header("Filters")

# 1. Date range — first
min_date = df["AQL date"].min().date()
max_date = df["AQL date"].max().date()
start_date = st.sidebar.date_input("Start date", value=min_date,
                                   min_value=min_date, max_value=max_date)
end_date   = st.sidebar.date_input("End date",   value=max_date,
                                   min_value=min_date, max_value=max_date)

if start_date > end_date:
    st.warning("Start date must be before End date.")
    st.stop()

# 2. Client country — single selectbox with "All"
all_countries = sorted(df["Client country"].dropna().unique().tolist())
sel_country = st.sidebar.selectbox("Client country", ["All"] + all_countries)

# 3. Client CRM — selectbox with "All"
all_crms = sorted(df["Client CRM"].dropna().unique().tolist())
sel_crm = st.sidebar.selectbox("Client CRM", ["All"] + all_crms)

# Build filter masks
date_mask = (
    (df["AQL date"].dt.date >= start_date) &
    (df["AQL date"].dt.date <= end_date)
)

if sel_country == "All":
    country_mask = pd.Series(True, index=df.index)
else:
    country_mask = df["Client country"] == sel_country

if sel_crm == "All":
    crm_mask = pd.Series(True, index=df.index)
else:
    crm_mask = df["Client CRM"] == sel_crm

filtered_df = df[date_mask & country_mask & crm_mask].copy()

# Sidebar info
st.sidebar.divider()
st.sidebar.caption(f"Showing {len(filtered_df)} of {len(df)} deals")

# ── Empty filter guard ────────────────────────────────────────────────────────

if filtered_df.empty:
    st.warning("No deals match the selected filters. Adjust filters in the sidebar.")
    st.stop()

# ── Helper ────────────────────────────────────────────────────────────────────

def win_rate(sub: pd.DataFrame) -> float:
    closed = sub[sub["Stage"].isin(["Closed Won", "Closed Lost"])]
    if len(closed) == 0:
        return float("nan")
    return round(closed[closed["Stage"] == "Closed Won"].shape[0] / len(closed) * 100, 1)

# ── Top metrics ───────────────────────────────────────────────────────────────

st.title("Ringostat RevOps Dashboard")

total = len(filtered_df)
won   = filtered_df[filtered_df["Stage"] == "Closed Won"].shape[0]
lost  = filtered_df[filtered_df["Stage"] == "Closed Lost"].shape[0]
wr    = win_rate(filtered_df)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Deals", total)
c2.metric("Win Rate %", f"{wr:.1f}%" if not pd.isna(wr) else "N/A")
c3.metric("Closed Won",  won)
c4.metric("Closed Lost", lost)

st.divider()

# ── Row 1: Win Rate by Country | Win Rate by CRM ──────────────────────────────

col_left, col_right = st.columns(2)

closed_df = filtered_df[filtered_df["Stage"].isin(["Closed Won", "Closed Lost"])]

# 1. Win Rate by Country
with col_left:
    st.subheader("Win Rate by Country")
    if len(closed_df) > 0:
        country_stats = closed_df.groupby("Client country", as_index=False).agg(
            closed=("Stage", "count"),
            won=("Stage", lambda x: (x == "Closed Won").sum()),
        )
        country_stats["win_rate"] = round(country_stats["won"] / country_stats["closed"] * 100, 1)
        country_stats = (
            country_stats[country_stats["closed"] >= 5]
            .sort_values("win_rate", ascending=True)
        )
    else:
        country_stats = pd.DataFrame(columns=["Client country", "closed", "won", "win_rate"])

    if not country_stats.empty:
        fig1 = px.bar(
            country_stats, x="win_rate", y="Client country", orientation="h",
            labels={"win_rate": "Win Rate %", "Client country": "Country"},
            text="win_rate",
            color_discrete_sequence=[COLOR_PRIMARY],
        )
        fig1.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig1.update_layout(**CHART_LAYOUT)
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("Not enough data (need ≥ 5 closed deals per country).")

# 2. Win Rate by CRM
with col_right:
    st.subheader("Win Rate by CRM")
    if len(closed_df) > 0:
        crm_stats = closed_df.groupby("Client CRM", as_index=False).agg(
            closed=("Stage", "count"),
            won=("Stage", lambda x: (x == "Closed Won").sum()),
        )
        crm_stats["win_rate"] = round(crm_stats["won"] / crm_stats["closed"] * 100, 1)
        crm_stats = (
            crm_stats[crm_stats["closed"] >= 5]
            .sort_values("win_rate", ascending=True)
        )
    else:
        crm_stats = pd.DataFrame(columns=["Client CRM", "closed", "won", "win_rate"])

    if not crm_stats.empty:
        fig2 = px.bar(
            crm_stats, x="win_rate", y="Client CRM", orientation="h",
            labels={"win_rate": "Win Rate %", "Client CRM": "CRM"},
            text="win_rate",
            color_discrete_sequence=[COLOR_PRIMARY],
        )
        fig2.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig2.update_layout(**CHART_LAYOUT)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Not enough data (need ≥ 5 closed deals per CRM).")

st.divider()

# ── Row 2: Deal Distribution by Stage | Deals by Source ───────────────────────

col_left2, col_right2 = st.columns(2)

# 3. Deal Distribution by Stage
with col_left2:
    st.subheader("Deal Distribution by Stage")
    stage_col = filtered_df["Stage"].fillna("Missing stage").replace("", "Missing stage")
    stage_data = stage_col.value_counts().reset_index()
    stage_data.columns = ["Stage", "Count"]
    fig3 = px.pie(
        stage_data, names="Stage", values="Count",
        color="Stage",
        color_discrete_map=STAGE_COLORS,
    )
    st.plotly_chart(fig3, use_container_width=True)

# 4. Deals by Source
with col_right2:
    st.subheader("Deals by Source")
    source_data = filtered_df["Source"].dropna().value_counts().reset_index()
    source_data.columns = ["Source", "Count"]
    source_data = source_data.sort_values("Count", ascending=True)
    fig4 = px.bar(
        source_data, x="Count", y="Source", orientation="h",
        labels={"Count": "Number of Deals"},
        text="Count",
        color_discrete_sequence=[COLOR_PRIMARY],
    )
    fig4.update_traces(textposition="outside")
    fig4.update_layout(**CHART_LAYOUT)
    st.plotly_chart(fig4, use_container_width=True)

st.divider()

# ── Row 3: Win Rate by PPC Budget (full width) ────────────────────────────────

st.subheader("Win Rate by PPC Budget")

if len(closed_df) > 0:
    ppc_stats = closed_df.groupby("PPC budget USD", observed=False, as_index=False).agg(
        total_closed=("Stage", "count"),
        won=("Stage", lambda x: (x == "Closed Won").sum()),
    )
    ppc_stats["Win Rate %"] = round(ppc_stats["won"] / ppc_stats["total_closed"] * 100, 1)
    ppc_stats["PPC budget USD"] = ppc_stats["PPC budget USD"].astype(str)
    # Filter out ranges with 0 closed deals
    ppc_stats = ppc_stats[ppc_stats["total_closed"] > 0]
    ppc_stats["PPC budget USD"] = pd.Categorical(
        ppc_stats["PPC budget USD"], categories=BUDGET_ORDER, ordered=True
    )
    ppc_stats = ppc_stats.sort_values("PPC budget USD")

    fig5 = px.bar(
        ppc_stats, x="PPC budget USD", y="Win Rate %",
        text="Win Rate %",
        color_discrete_sequence=[COLOR_PRIMARY],
    )
    fig5.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig5.update_layout(**CHART_LAYOUT)
    fig5.update_xaxes(type="category", showgrid=False)
    fig5.update_yaxes(showgrid=False)
    st.plotly_chart(fig5, use_container_width=True)
    st.caption("Only budget ranges with ≥1 closed deal are shown.")
else:
    st.info("No closed deals to calculate PPC budget win rates.")

# ── Row 4: Data Quality Issues (full width) ───────────────────────────────────

st.divider()
st.header("Data Quality Issues")

issues_list = []

# 1. Missing Stage
mask1 = df["Stage"].isna() | (df["Stage"] == "")
if mask1.any():
    temp = df.loc[mask1].copy()
    temp["Issue"] = "Missing Stage"
    issues_list.append(temp)

# 2. Closed deal without Closing Date
mask2 = df["Stage"].isin(["Closed Won", "Closed Lost"]) & (df["Closing Date"].isna())
if mask2.any():
    temp = df.loc[mask2].copy()
    temp["Issue"] = "Closed deal missing Closing Date"
    issues_list.append(temp)

# 3. Missing Client country
mask3 = df["Client country"].isna() | (df["Client country"] == "")
if mask3.any():
    temp = df.loc[mask3].copy()
    temp["Issue"] = "Missing Client country"
    issues_list.append(temp)

# 4. Missing Source
mask4 = df["Source"].isna() | (df["Source"] == "")
if mask4.any():
    temp = df.loc[mask4].copy()
    temp["Issue"] = "Missing Source"
    issues_list.append(temp)

# 5. Unparseable AQL date
mask5 = df["AQL date"].isna()
if mask5.any():
    temp = df.loc[mask5].copy()
    temp["Issue"] = "Invalid or missing AQL date"
    issues_list.append(temp)

if issues_list:
    issues_df = pd.concat(issues_list, ignore_index=True)
    show_cols = ["AQL date", "Source", "Client country", "Stage",
                 "Closing Date", "Issue"]
    show_cols = [c for c in show_cols if c in issues_df.columns]
    st.dataframe(issues_df[show_cols], use_container_width=True, hide_index=True)
    st.caption(f"Total: {len(issues_df)} issues across {issues_df['Issue'].nunique()} categories")
else:
    st.success("No data quality issues found.")

# ── Row 5: RevOps Insights Summary (full width) ───────────────────────────────

st.divider()
st.header("RevOps Insights Summary")

closed_deals = filtered_df[filtered_df["Stage"].isin(["Closed Won", "Closed Lost"])]

if len(closed_deals) == 0:
    st.warning("Not enough closed deals to generate insights.")
else:
    ins_won = len(closed_deals[closed_deals["Stage"] == "Closed Won"])
    ins_lost = len(closed_deals[closed_deals["Stage"] == "Closed Lost"])
    ins_wr = ins_won / (ins_won + ins_lost) * 100

    # Country analysis (>= 5 closed deals)
    country_wr = closed_deals.groupby("Client country", as_index=False).agg(
        won=("Stage", lambda x: (x == "Closed Won").sum()),
        total=("Stage", "count"),
    )
    country_wr["win_rate"] = country_wr["won"] / country_wr["total"] * 100
    country_wr = country_wr[country_wr["total"] >= 5].sort_values("win_rate", ascending=False)

    # CRM: No CRM analysis
    no_crm = closed_deals[closed_deals["Client CRM"] == "No CRM"]
    no_crm_pct = len(filtered_df[filtered_df["Client CRM"] == "No CRM"]) / len(filtered_df) * 100
    no_crm_wr = (len(no_crm[no_crm["Stage"] == "Closed Won"]) / len(no_crm) * 100) if len(no_crm) > 0 else 0

    # Source analysis
    source_counts = filtered_df["Source"].value_counts()
    source_wr = closed_deals.groupby("Source", as_index=False).agg(
        won=("Stage", lambda x: (x == "Closed Won").sum()),
        total=("Stage", "count"),
    )
    source_wr["win_rate"] = source_wr["won"] / source_wr["total"] * 100
    source_wr = source_wr[source_wr["total"] >= 3].sort_values("win_rate", ascending=False)

    # Loss reasons
    loss_reasons = closed_deals[closed_deals["Stage"] == "Closed Lost"]["Loss reason description"].dropna()
    loss_reasons = loss_reasons[loss_reasons != ""]

    # Data quality count (from original df)
    quality_count = sum([
        df["Stage"].isna().sum(),
        (df["Stage"].isin(["Closed Won", "Closed Lost"]) & df["Closing Date"].isna()).sum(),
        df["Client country"].isna().sum(),
        df["Source"].isna().sum(),
    ])

    # Build summary points
    points = []

    points.append(
        f"**Overall win rate is {ins_wr:.1f}%** — out of {ins_won + ins_lost} closed deals, "
        f"{ins_won} were won and {ins_lost} lost."
    )

    if len(country_wr) >= 2:
        best = country_wr.iloc[0]
        worst = country_wr.iloc[-1]
        points.append(
            f"**Best-performing market: {best['Client country']}** "
            f"({best['win_rate']:.0f}% win rate, {int(best['total'])} closed deals). "
            f"**Weakest: {worst['Client country']}** ({worst['win_rate']:.0f}%) — "
            f"review whether ICP and sales approach fit this market."
        )

    points.append(
        f"**{no_crm_pct:.0f}% of all deals have no CRM.** "
        f"Their win rate ({no_crm_wr:.1f}%) is "
        f"{'lower' if no_crm_wr < ins_wr else 'higher'} than average ({ins_wr:.1f}%). "
        f"Requiring CRM info during qualification could improve tracking and conversion."
    )

    if len(source_wr) >= 1:
        top_vol = source_counts.index[0]
        top_vol_count = source_counts.iloc[0]
        best_src = source_wr.iloc[0]
        points.append(
            f"**{top_vol}** brings the most deals ({top_vol_count}), "
            f"but **{best_src['Source']}** has the highest win rate "
            f"({best_src['win_rate']:.0f}%). "
            f"Consider investing more in high-converting sources."
        )

    if len(loss_reasons) > 0:
        top_reason = loss_reasons.value_counts().index[0]
        top_reason_count = loss_reasons.value_counts().iloc[0]
        points.append(
            f"**Top loss reason: \"{top_reason}\"** ({top_reason_count} deals). "
            f"This points to a competitive positioning challenge — "
            f"review pricing, feature differentiation, and objection handling."
        )

    points.append(
        f"**{quality_count} data quality issues detected** in the dataset. "
        f"Missing Stage values and incomplete closing dates hurt pipeline accuracy. "
        f"Enforce mandatory fields in CRM to improve data reliability."
    )

    summary_md = "\n\n".join([f"• {p}" for p in points])
    st.markdown(summary_md)
