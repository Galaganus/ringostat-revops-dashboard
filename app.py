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
}

_FALLBACK_COLORS = px.colors.qualitative.Set2

def get_stage_color_map(stages):
    """Return color map for given stages, with fallback for unknown ones."""
    result = {}
    fallback_idx = 0
    for s in stages:
        if s in STAGE_COLORS:
            result[s] = STAGE_COLORS[s]
        else:
            result[s] = _FALLBACK_COLORS[fallback_idx % len(_FALLBACK_COLORS)]
            fallback_idx += 1
    return result

CHART_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=40, t=40, b=0),
    yaxis=dict(showgrid=False),
    xaxis=dict(showgrid=False),
)

import re

def sort_budget_key(val):
    """Sort budget ranges numerically by their lower bound."""
    val = str(val).strip()
    if val == "Unknown":
        return (1, float("inf"))
    nums = re.findall(r"[\d]+", val)
    if nums:
        return (0, float(nums[0]))
    return (1, 0)

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
            if val == 0:
                return "No PPC"
            return str(int(val))
        s = str(val).strip()
        return s if s else "Unknown"

    raw["PPC budget USD"] = raw["PPC budget USD"].apply(normalize_budget)
    budget_vals = sorted(raw["PPC budget USD"].dropna().unique(), key=sort_budget_key)
    raw["PPC budget USD"] = pd.Categorical(raw["PPC budget USD"],
                                           categories=budget_vals, ordered=True)
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

# Sidebar options
show_zero_wr = st.sidebar.checkbox("Show 0% win rate segments", value=False)

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

# Compute stats for both charts first to determine shared height
if len(closed_df) > 0:
    country_stats = closed_df.groupby("Client country", as_index=False).agg(
        closed=("Stage", "count"),
        won=("Stage", lambda x: (x == "Closed Won").sum()),
    )
    country_stats["win_rate"] = round(country_stats["won"] / country_stats["closed"] * 100, 1)
    if not show_zero_wr:
        country_stats = country_stats[country_stats["win_rate"] > 0]
    country_stats = country_stats.sort_values("win_rate", ascending=True)
    country_stats["Client country"] = country_stats["Client country"].apply(
        lambda x: (x[:18] + "…") if len(str(x)) > 20 else x
    )

    crm_stats = closed_df.groupby("Client CRM", as_index=False).agg(
        closed=("Stage", "count"),
        won=("Stage", lambda x: (x == "Closed Won").sum()),
    )
    crm_stats["win_rate"] = round(crm_stats["won"] / crm_stats["closed"] * 100, 1)
    if not show_zero_wr:
        crm_stats = crm_stats[crm_stats["win_rate"] > 0]
    crm_stats = crm_stats.sort_values("win_rate", ascending=True)
    crm_stats["Client CRM"] = crm_stats["Client CRM"].apply(
        lambda x: (x[:18] + "…") if len(str(x)) > 20 else x
    )
else:
    country_stats = pd.DataFrame(columns=["Client country", "closed", "won", "win_rate"])
    crm_stats = pd.DataFrame(columns=["Client CRM", "closed", "won", "win_rate"])

# Shared height: enough for labels but capped to avoid excessive scrolling
wr_bar_count = max(len(country_stats), len(crm_stats), 1)
wr_chart_height = max(300, min(500, wr_bar_count * 30))

# 1. Win Rate by Country
with col_left:
    st.subheader("Win Rate by Country")
    if not country_stats.empty:
        country_stats["label"] = (
            country_stats["win_rate"].apply(lambda x: f"{x:.1f}%")
            + " (n=" + country_stats["closed"].astype(int).astype(str) + ")"
        )
        fig1 = px.bar(
            country_stats, x="win_rate", y="Client country", orientation="h",
            labels={"win_rate": "Win Rate %", "Client country": "Country"},
            text="label",
            color_discrete_sequence=[COLOR_PRIMARY],
        )
        fig1.update_traces(textposition="outside")
        fig1.update_layout(**CHART_LAYOUT, height=wr_chart_height)
        fig1.update_yaxes(tickfont=dict(size=10))
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("No closed deals for this filter selection.")

# 2. Win Rate by CRM
with col_right:
    st.subheader("Win Rate by CRM")
    if not crm_stats.empty:
        crm_stats["label"] = (
            crm_stats["win_rate"].apply(lambda x: f"{x:.1f}%")
            + " (n=" + crm_stats["closed"].astype(int).astype(str) + ")"
        )
        fig2 = px.bar(
            crm_stats, x="win_rate", y="Client CRM", orientation="h",
            labels={"win_rate": "Win Rate %", "Client CRM": "CRM"},
            text="label",
            color_discrete_sequence=[COLOR_PRIMARY],
        )
        fig2.update_traces(textposition="outside")
        fig2.update_layout(**CHART_LAYOUT, height=wr_chart_height)
        fig2.update_yaxes(tickfont=dict(size=10))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No closed deals for this filter selection.")

st.divider()

# ── Row 2: Deal Distribution by Stage | Deals by Source ───────────────────────

col_left2, col_right2 = st.columns(2)

# 3. Deal Distribution by Stage
with col_left2:
    st.subheader("Deal Distribution by Stage")
    stage_data = filtered_df["Stage"].value_counts().reset_index()
    stage_data.columns = ["Stage", "Count"]
    fig3 = px.pie(
        stage_data, names="Stage", values="Count",
        color="Stage",
        color_discrete_map=get_stage_color_map(stage_data["Stage"].unique()),
    )
    fig3.update_layout(
        legend=dict(
            font=dict(size=13),
            x=1.0,
            y=0.5,
            xanchor="left",
            yanchor="middle",
        ),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig3, use_container_width=True)

# 4. Deals by Source
with col_right2:
    st.subheader("Deals by Source")
    source_df = filtered_df[filtered_df["Source"].notna()].copy()

    def stage_group(stage):
        if stage == "Closed Won":
            return "Won"
        if stage == "Closed Lost":
            return "Lost"
        return "Open"

    source_df["Status"] = source_df["Stage"].apply(stage_group)
    source_agg = (
        source_df.groupby(["Source", "Status"], as_index=False)
        .size()
        .rename(columns={"size": "Count"})
    )
    # Sort sources by total deals
    source_order = (
        source_agg.groupby("Source")["Count"].sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    source_agg["Source"] = pd.Categorical(
        source_agg["Source"], categories=source_order, ordered=True
    )

    STATUS_COLORS = {"Won": COLOR_WON, "Lost": COLOR_LOST, "Open": COLOR_NEUTRAL}

    fig4 = px.bar(
    source_agg, x="Count", y="Source", orientation="h",
    color="Status",
    color_discrete_map=STATUS_COLORS,
    category_orders={"Source": source_order, "Status": ["Won", "Lost", "Open"]},
    labels={"Count": "Number of Deals"},
    )
    fig4.update_traces(textposition="none")

    # Add total count as text outside the stacked bar
    source_totals = source_agg.groupby("Source")["Count"].sum()
    for source_name in source_order:
        total = source_totals.get(source_name, 0)
        fig4.add_annotation(
            x=total, y=source_name,
            text=str(total),
            showarrow=False, xanchor="left", xshift=5,
            font=dict(size=11),
        )

    fig4.update_layout(**CHART_LAYOUT, barmode="stack",
                        legend=dict(orientation="h", y=1.02, x=0.5,
                                    xanchor="center", yanchor="bottom"))
    st.plotly_chart(fig4, use_container_width=True)

st.divider()

# ── Row 3: Win Rate by PPC Budget (full width) ────────────────────────────────

st.subheader("Win Rate by PPC Budget")

if len(closed_df) > 0:
    ppc_stats = closed_df.groupby("PPC budget USD", observed=True, as_index=False).agg(
        total_closed=("Stage", "count"),
        won=("Stage", lambda x: (x == "Closed Won").sum()),
    )
    ppc_stats["Win Rate %"] = round(ppc_stats["won"] / ppc_stats["total_closed"] * 100, 1)
    ppc_stats["PPC budget USD"] = ppc_stats["PPC budget USD"].astype(str)
    ppc_stats = ppc_stats[ppc_stats["won"] > 0].copy()
    budget_categories = list(df["PPC budget USD"].cat.categories.astype(str))
    order_map = {v: i for i, v in enumerate(budget_categories)}
    ppc_stats["_order"] = ppc_stats["PPC budget USD"].map(order_map)
    ppc_stats = ppc_stats.sort_values("_order").drop(columns="_order")

    if not ppc_stats.empty:
        ppc_stats["label"] = (
            ppc_stats["Win Rate %"].apply(lambda x: f"{x:.1f}%")
            + " (n=" + ppc_stats["total_closed"].astype(int).astype(str) + ")"
        )

        fig5 = px.bar(
            ppc_stats, x="PPC budget USD", y="Win Rate %",
            text="label",
            color_discrete_sequence=[COLOR_PRIMARY],
        )
        fig5.update_traces(texttemplate="%{text}", textposition="outside")
        fig5.update_layout(**CHART_LAYOUT)
        fig5.update_xaxes(type="category", showgrid=False)
        fig5.update_yaxes(showgrid=False)

        st.plotly_chart(fig5, use_container_width=True)
        st.caption("Win rate shown with number of closed deals (n) per budget range.")

        # Show 0% win rate segments as text below chart
        zero_wr = closed_df.groupby("PPC budget USD", observed=True, as_index=False).agg(
            total_closed=("Stage", "count"),
            won=("Stage", lambda x: (x == "Closed Won").sum()),
        )
        zero_wr = zero_wr[zero_wr["won"] == 0]
        if not zero_wr.empty:
            zero_labels = [
                f"{row['PPC budget USD']} (n={int(row['total_closed'])})"
                for _, row in zero_wr.iterrows()
            ]
            st.caption(f"0% win rate: {', '.join(zero_labels)}")
    else:
        st.info("No won deals in any PPC budget range for this filter selection.")
else:
    st.info("No closed deals to calculate PPC budget win rates.")

# ── Data Quality checks (shared logic) ────────────────────────────────────────

def find_data_quality_issues(data: pd.DataFrame) -> pd.DataFrame:
    """Run universal data quality checks on any deals DataFrame.
    Returns a DataFrame with an 'Issue' column describing each problem found.
    Only includes objectively verifiable data errors.
    """
    results = []

    # ── Missing values in key columns ────────────────────────────────────
    key_cols = ["Stage", "Client country", "Source", "Client CRM"]
    for col in key_cols:
        if col not in data.columns:
            continue
        mask = data[col].isna() | (data[col].astype(str).str.strip() == "")
        if mask.any():
            temp = data.loc[mask].copy()
            temp["Issue"] = f"Missing {col}"
            results.append(temp)

    # ── Closing Date before AQL date (impossible chronology) ─────────────
    if "Closing Date" in data.columns and "AQL date" in data.columns:
        cd = pd.to_datetime(data["Closing Date"], format="mixed", errors="coerce") \
            if data["Closing Date"].dtype != "datetime64[ns]" else data["Closing Date"]
        ad = pd.to_datetime(data["AQL date"], format="mixed", errors="coerce") \
            if data["AQL date"].dtype != "datetime64[ns]" else data["AQL date"]
        mask = cd.notna() & ad.notna() & (cd < ad)
        if mask.any():
            temp = data.loc[mask].copy()
            temp["Issue"] = "Closing Date is before AQL date"
            results.append(temp)

    # ── Stage-date consistency ───────────────────────────────────────────
    if "Stage" in data.columns and "Closing Date" in data.columns:
        cd = pd.to_datetime(data["Closing Date"], format="mixed", errors="coerce") \
            if data["Closing Date"].dtype != "datetime64[ns]" else data["Closing Date"]

        # Closed deal without Closing Date
        mask = data["Stage"].isin(["Closed Won", "Closed Lost"]) & cd.isna()
        if mask.any():
            temp = data.loc[mask].copy()
            temp["Issue"] = "Closed deal missing Closing Date"
            results.append(temp)

        # Non-closed deal has Closing Date
        mask = (~data["Stage"].isin(["Closed Won", "Closed Lost"])) & cd.notna()
        if mask.any():
            temp = data.loc[mask].copy()
            temp["Issue"] = "Non-closed deal has Closing Date"
            results.append(temp)

    # ── Missing loss reason on lost deals ────────────────────────────────
    if "Loss reason description" in data.columns and "Stage" in data.columns:
        mask = (data["Stage"] == "Closed Lost") & (
            data["Loss reason description"].isna()
            | (data["Loss reason description"].astype(str).str.strip() == "")
        )
        if mask.any():
            temp = data.loc[mask].copy()
            temp["Issue"] = "Closed Lost without loss reason"
            results.append(temp)

    if results:
        return pd.concat(results, ignore_index=True)
    return pd.DataFrame()


# ── Row 4: Data Quality Issues (full width) ───────────────────────────────────

st.divider()
st.header("Data Quality Issues")

all_issues_df = find_data_quality_issues(df)

if not all_issues_df.empty:
    show_cols = [c for c in
                 ["AQL date", "Source", "Client country", "Client CRM",
                  "Stage", "Closing Date", "Loss reason description", "Issue"]
                 if c in all_issues_df.columns]
    st.dataframe(all_issues_df[show_cols], use_container_width=True, hide_index=True)
    issue_summary = all_issues_df["Issue"].value_counts()
    st.caption(f"Total: {len(all_issues_df)} issues across {len(issue_summary)} categories")
else:
    st.success("No data quality issues found.")

# ── Row 5: RevOps Insights Summary (full width) ───────────────────────────────

st.divider()
st.header("RevOps Insights Summary")

closed_deals = closed_df

if len(closed_deals) < 2:
    st.warning("Not enough closed deals to generate meaningful insights.")
else:
    total_deals = len(filtered_df)
    won_count = (closed_deals["Stage"] == "Closed Won").sum()
    lost_count = (closed_deals["Stage"] == "Closed Lost").sum()
    overall_wr = won_count / len(closed_deals) * 100

    # ── Helpers ──────────────────────────────────────────────────────
    def top_bottom(group_col, min_sample=3):
        """Get best and worst segments by win rate for a given column."""
        if group_col not in filtered_df.columns:
            return None, None
        seg = closed_deals.groupby(group_col, as_index=False).agg(
            won=("Stage", lambda x: (x == "Closed Won").sum()),
            total=("Stage", "count"),
        )
        seg["wr"] = (seg["won"] / seg["total"] * 100).round(1)
        seg = seg[seg["total"] >= min_sample].sort_values("wr", ascending=False)
        if len(seg) < 2:
            return None, None
        return seg.iloc[0], seg.iloc[-1]

    insights = []

    # ── 1. Win rate overview (always shown) ──────────────────────────
    insights.append(
        f"**Win rate: {overall_wr:.1f}%** "
        f"({won_count}W / {lost_count}L out of {total_deals} total deals)"
    )

    # ── 2. Bottleneck: where open deals accumulate ───────────────────
    open_deals = filtered_df[~filtered_df["Stage"].isin(["Closed Won", "Closed Lost"])]
    if len(open_deals) > 0:
        top_stage = open_deals["Stage"].value_counts()
        biggest = top_stage.index[0]
        biggest_pct = top_stage.iloc[0] / len(open_deals) * 100
        insights.append(
            f"**Bottleneck: {biggest}** — "
            f"{top_stage.iloc[0]} of {len(open_deals)} open deals "
            f"({biggest_pct:.0f}%) are stuck at this stage"
        )

    # ── 3. Best & worst by country ───────────────────────────────────
    best_c, worst_c = top_bottom("Client country")
    if best_c is not None and worst_c is not None:
        insights.append(
            f"**Best market: {best_c['Client country']}** "
            f"({best_c['wr']:.0f}% WR, n={int(best_c['total'])}), "
            f"**worst: {worst_c['Client country']}** "
            f"({worst_c['wr']:.0f}% WR, n={int(worst_c['total'])})"
        )

    # ── 4. CRM impact ───────────────────────────────────────────────
    if "Client CRM" in filtered_df.columns:
        no_crm_deals = filtered_df[filtered_df["Client CRM"] == "No CRM"]
        no_crm_closed = closed_deals[closed_deals["Client CRM"] == "No CRM"]
        has_crm_closed = closed_deals[closed_deals["Client CRM"] != "No CRM"]

        no_crm_pct = len(no_crm_deals) / total_deals * 100 if total_deals > 0 else 0

        if len(no_crm_closed) >= 3 and len(has_crm_closed) >= 3:
            no_crm_wr = (no_crm_closed["Stage"] == "Closed Won").sum() / len(no_crm_closed) * 100
            has_crm_wr = (has_crm_closed["Stage"] == "Closed Won").sum() / len(has_crm_closed) * 100
            diff = has_crm_wr - no_crm_wr
            direction = "higher" if diff > 0 else "lower"
            insights.append(
                f"**{no_crm_pct:.0f}% of deals have no CRM** — "
                f"deals with CRM convert {abs(diff):.1f}pp {direction} "
                f"({has_crm_wr:.1f}% vs {no_crm_wr:.1f}%)"
            )

    # ── 5. Source efficiency ─────────────────────────────────────────
    best_s, worst_s = top_bottom("Source")
    if best_s is not None:
        top_volume_source = filtered_df["Source"].value_counts().index[0]
        top_volume_count = filtered_df["Source"].value_counts().iloc[0]
        if best_s["Source"] != top_volume_source:
            insights.append(
                f"**Highest volume: {top_volume_source}** ({top_volume_count} deals), "
                f"**highest conversion: {best_s['Source']}** "
                f"({best_s['wr']:.0f}% WR, n={int(best_s['total'])})"
            )
        else:
            insights.append(
                f"**Top source: {best_s['Source']}** — "
                f"both highest volume ({top_volume_count}) and best WR ({best_s['wr']:.0f}%)"
            )

    # ── 6. Why deals are lost ────────────────────────────────────────
    if "Loss reason description" in closed_deals.columns:
        reasons = closed_deals.loc[
            closed_deals["Stage"] == "Closed Lost",
            "Loss reason description"
        ].dropna()
        reasons = reasons[reasons.astype(str).str.strip() != ""]
        if len(reasons) > 0:
            top_reason = reasons.value_counts().index[0]
            top_reason_n = reasons.value_counts().iloc[0]
            documented_pct = len(reasons) / lost_count * 100
            insights.append(
                f"**#1 loss reason: \"{top_reason}\"** ({top_reason_n} deals, "
                f"{top_reason_n/lost_count*100:.0f}% of losses). "
                f"Loss reasons documented for {documented_pct:.0f}% of lost deals"
            )
        elif lost_count > 0:
            insights.append(
                f"**No loss reasons documented** across {lost_count} lost deals — "
                f"this is a data gap that limits analysis"
            )

    # ── 7. Trend: win rate over time ─────────────────────────────────
    if "AQL date" in closed_deals.columns:
        monthly = closed_deals.set_index("AQL date").resample("M").agg(
            won=("Stage", lambda x: (x == "Closed Won").sum()),
            total=("Stage", "count"),
        )
        monthly["wr"] = (monthly["won"] / monthly["total"] * 100).round(1)
        monthly = monthly[monthly["total"] >= 3]
        if len(monthly) >= 3:
            first_half = monthly["wr"].iloc[: len(monthly) // 2].mean()
            second_half = monthly["wr"].iloc[len(monthly) // 2 :].mean()
            diff = second_half - first_half
            direction = "improving" if diff > 0 else "declining"
            insights.append(
                f"**Win rate is {direction}**: "
                f"averaged {first_half:.1f}% in earlier months vs "
                f"{second_half:.1f}% in recent months ({diff:+.1f}pp shift)"
            )

    # ── 8. Data quality note ─────────────────────────────────────────
    dq_count = len(all_issues_df) if not all_issues_df.empty else 0
    if dq_count > 0:
        top_issue = all_issues_df["Issue"].value_counts()
        top_issue_name = top_issue.index[0]
        top_issue_n = top_issue.iloc[0]
        insights.append(
            f"**{dq_count} data quality issues found** — "
            f"most common: \"{top_issue_name}\" ({top_issue_n} cases). "
            f"See Data Quality table above"
        )

    # ── Render as clean table-like format ────────────────────────────
    for point in insights:
        st.markdown(f"→ {point}")
