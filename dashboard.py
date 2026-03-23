"""
GitHub Stats Dashboard
Run with: streamlit run dashboard.py
"""

import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ─── Config ───────────────────────────────────────────────────────────────────

DB_PATH = os.environ.get("DB_PATH", "github_stats.db")

st.set_page_config(
    page_title="GitHub Stats Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .metric-card {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: 700; color: #58a6ff; }
    .metric-label { font-size: 0.85rem; color: #8b949e; margin-top: 4px; }
    .section-header {
        font-size: 1.1rem; font-weight: 600;
        color: #e6edf3; margin: 1rem 0 0.5rem 0;
        border-bottom: 1px solid #21262d; padding-bottom: 6px;
    }
    [data-testid="stSidebar"] { background-color: #0d1117; }
    .stSelectbox label, .stMultiSelect label { color: #8b949e !important; }
</style>
""", unsafe_allow_html=True)

# ─── DB Helpers ───────────────────────────────────────────────────────────────

@st.cache_resource
def get_conn():
    if not os.path.exists(DB_PATH):
        st.error(f"Database not found at `{DB_PATH}`. Run `collect_stats.py` first.")
        st.stop()
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def query(sql, params=()):
    conn = get_conn()
    return pd.read_sql_query(sql, conn, params=params)

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Filters")

    repos_df = query("SELECT repo, stars, language, private FROM repos ORDER BY stars DESC")
    if repos_df.empty:
        st.warning("No data yet. Run the collector first.")
        st.stop()

    all_repos = repos_df["repo"].tolist()
    selected_repos = st.multiselect(
        "Repositories",
        all_repos,
        default=all_repos[:10],
        help="Select repos to include in charts"
    )

    days_back = st.slider("Days of history", 7, 365, 30)
    since_date = (datetime.utcnow() - timedelta(days=days_back)).date().isoformat()

    show_private = st.checkbox("Include private repos", value=True)

    st.markdown("---")
    if st.button("🔄 Refresh Data"):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()

    last_fetch = query("SELECT MAX(fetched_at) as t FROM repos").iloc[0]["t"]
    if last_fetch:
        st.markdown(f"<div style='color:#8b949e;font-size:0.78rem'>Last synced:<br>{last_fetch[:19]} UTC</div>",
                    unsafe_allow_html=True)

# ─── Filter helpers ────────────────────────────────────────────────────────────

if not selected_repos:
    st.info("Select at least one repo from the sidebar.")
    st.stop()

placeholders = ",".join("?" * len(selected_repos))

# ─── Header ───────────────────────────────────────────────────────────────────

st.markdown("# 📊 GitHub Stats Tracker")
st.markdown(f"Tracking **{len(selected_repos)}** repos · last **{days_back}** days")

# ─── KPI Row ──────────────────────────────────────────────────────────────────

kpi_df = query(f"""
    SELECT SUM(stars) as stars, SUM(forks) as forks,
           SUM(open_issues) as issues, SUM(watchers) as watchers
    FROM repos WHERE repo IN ({placeholders})
""", selected_repos)

views_total = query(f"""
    SELECT COALESCE(SUM(views),0) as v, COALESCE(SUM(unique_views),0) as uv
    FROM traffic_views WHERE repo IN ({placeholders}) AND date >= ?
""", selected_repos + [since_date])

clones_total = query(f"""
    SELECT COALESCE(SUM(clones),0) as c, COALESCE(SUM(unique_clones),0) as uc
    FROM traffic_clones WHERE repo IN ({placeholders}) AND date >= ?
""", selected_repos + [since_date])

k = kpi_df.iloc[0]
v = views_total.iloc[0]
c = clones_total.iloc[0]

col1, col2, col3, col4, col5, col6 = st.columns(6)
metrics = [
    ("⭐ Total Stars",   int(k["stars"] or 0),   col1),
    ("🍴 Total Forks",   int(k["forks"] or 0),   col2),
    ("👁️ Views",        int(v["v"]),             col3),
    ("👤 Unique Views",  int(v["uv"]),            col4),
    ("📥 Clones",       int(c["c"]),             col5),
    ("📥 Unique Clones", int(c["uc"]),            col6),
]
for label, value, col in metrics:
    with col:
        st.metric(label, f"{value:,}")

st.divider()

# ─── Traffic Over Time ─────────────────────────────────────────────────────────

st.markdown('<div class="section-header">📈 Traffic Over Time</div>', unsafe_allow_html=True)

views_ts = query(f"""
    SELECT date, SUM(views) as views, SUM(unique_views) as unique_views
    FROM traffic_views WHERE repo IN ({placeholders}) AND date >= ?
    GROUP BY date ORDER BY date
""", selected_repos + [since_date])

clones_ts = query(f"""
    SELECT date, SUM(clones) as clones, SUM(unique_clones) as unique_clones
    FROM traffic_clones WHERE repo IN ({placeholders}) AND date >= ?
    GROUP BY date ORDER BY date
""", selected_repos + [since_date])

if not views_ts.empty or not clones_ts.empty:
    tab1, tab2 = st.tabs(["👁️ Views", "📥 Clones"])

    with tab1:
        if views_ts.empty:
            st.info("No view data for the selected period.")
        else:
            fig = px.area(views_ts, x="date", y=["views", "unique_views"],
                          labels={"value": "Count", "variable": "Metric"},
                          color_discrete_map={"views": "#58a6ff", "unique_views": "#3fb950"},
                          template="plotly_dark")
            fig.update_layout(legend_title_text="", plot_bgcolor="#0d1117",
                              paper_bgcolor="#0d1117", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        if clones_ts.empty:
            st.info("No clone data for the selected period.")
        else:
            fig = px.bar(clones_ts, x="date", y=["clones", "unique_clones"],
                         barmode="group",
                         color_discrete_map={"clones": "#d2a8ff", "unique_clones": "#ffa657"},
                         template="plotly_dark")
            fig.update_layout(legend_title_text="", plot_bgcolor="#0d1117",
                              paper_bgcolor="#0d1117", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No traffic data found. Run the collector first.")

# ─── Per-Repo Breakdown ────────────────────────────────────────────────────────

st.markdown('<div class="section-header">🗂️ Per-Repo Breakdown</div>', unsafe_allow_html=True)

col_left, col_right = st.columns(2)

with col_left:
    repo_views = query(f"""
        SELECT repo, SUM(views) as total_views, SUM(unique_views) as unique_views
        FROM traffic_views WHERE repo IN ({placeholders}) AND date >= ?
        GROUP BY repo ORDER BY total_views DESC LIMIT 15
    """, selected_repos + [since_date])

    if not repo_views.empty:
        repo_views["repo_short"] = repo_views["repo"].str.split("/").str[-1]
        fig = px.bar(repo_views, x="total_views", y="repo_short", orientation="h",
                     title="Top Repos by Views",
                     color="total_views", color_continuous_scale="Blues",
                     template="plotly_dark")
        fig.update_layout(showlegend=False, plot_bgcolor="#0d1117",
                          paper_bgcolor="#0d1117", coloraxis_showscale=False,
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

with col_right:
    repo_stars = query(f"""
        SELECT repo, stars, forks FROM repos
        WHERE repo IN ({placeholders})
        ORDER BY stars DESC LIMIT 15
    """, selected_repos)

    if not repo_stars.empty:
        repo_stars["repo_short"] = repo_stars["repo"].str.split("/").str[-1]
        fig = px.bar(repo_stars, x="stars", y="repo_short", orientation="h",
                     title="Stars by Repo",
                     color="stars", color_continuous_scale="Oranges",
                     template="plotly_dark")
        fig.update_layout(showlegend=False, plot_bgcolor="#0d1117",
                          paper_bgcolor="#0d1117", coloraxis_showscale=False,
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

# ─── Stars History ─────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">⭐ Stars History</div>', unsafe_allow_html=True)

stars_hist = query(f"""
    SELECT date, repo, stars FROM repo_stars_history
    WHERE repo IN ({placeholders}) AND date >= ?
    ORDER BY date
""", selected_repos + [since_date])

if not stars_hist.empty and stars_hist["date"].nunique() > 1:
    stars_hist["repo_short"] = stars_hist["repo"].str.split("/").str[-1]
    fig = px.line(stars_hist, x="date", y="stars", color="repo_short",
                  template="plotly_dark",
                  labels={"stars": "Stars", "repo_short": "Repo"})
    fig.update_layout(plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
                      hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Stars history builds up over multiple days of collection. Check back tomorrow!")

# ─── Referrers & Paths ─────────────────────────────────────────────────────────

st.markdown('<div class="section-header">🔗 Referrers & Popular Paths</div>', unsafe_allow_html=True)

col_a, col_b = st.columns(2)

with col_a:
    refs = query(f"""
        SELECT referrer, SUM(count) as hits, SUM(uniques) as unique_visitors
        FROM referrers WHERE repo IN ({placeholders})
        GROUP BY referrer ORDER BY hits DESC LIMIT 12
    """, selected_repos)

    if not refs.empty:
        fig = px.bar(refs, x="hits", y="referrer", orientation="h",
                     title="Top Referrers",
                     color="hits", color_continuous_scale="Teal",
                     template="plotly_dark")
        fig.update_layout(showlegend=False, plot_bgcolor="#0d1117",
                          paper_bgcolor="#0d1117", coloraxis_showscale=False,
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No referrer data yet.")

with col_b:
    paths = query(f"""
        SELECT path, title, SUM(count) as hits, SUM(uniques) as unique_visitors
        FROM popular_paths WHERE repo IN ({placeholders})
        GROUP BY path ORDER BY hits DESC LIMIT 12
    """, selected_repos)

    if not paths.empty:
        paths["label"] = paths["path"].str[-40:]
        fig = px.bar(paths, x="hits", y="label", orientation="h",
                     title="Most Visited Paths",
                     color="hits", color_continuous_scale="Purples",
                     template="plotly_dark")
        fig.update_layout(showlegend=False, plot_bgcolor="#0d1117",
                          paper_bgcolor="#0d1117", coloraxis_showscale=False,
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No path data yet.")

# ─── Repo Table ────────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">📋 Repo Summary Table</div>', unsafe_allow_html=True)

table_df = query(f"""
    SELECT
        r.repo,
        r.language,
        r.stars,
        r.forks,
        r.open_issues,
        r.size_kb,
        COALESCE(v.views, 0) as views_14d,
        COALESCE(v.uv, 0) as unique_views_14d,
        COALESCE(c.clones, 0) as clones_14d,
        r.url
    FROM repos r
    LEFT JOIN (
        SELECT repo, SUM(views) as views, SUM(unique_views) as uv
        FROM traffic_views WHERE date >= date('now', '-14 days')
        GROUP BY repo
    ) v ON r.repo = v.repo
    LEFT JOIN (
        SELECT repo, SUM(clones) as clones
        FROM traffic_clones WHERE date >= date('now', '-14 days')
        GROUP BY repo
    ) c ON r.repo = c.repo
    WHERE r.repo IN ({placeholders})
    ORDER BY r.stars DESC
""", selected_repos)

if not table_df.empty:
    table_df["repo_name"] = table_df["repo"].str.split("/").str[-1]
    display = table_df[["repo_name", "language", "stars", "forks",
                         "views_14d", "unique_views_14d", "clones_14d", "open_issues"]]
    display.columns = ["Repo", "Language", "⭐ Stars", "🍴 Forks",
                        "👁 Views (14d)", "👤 Uniq Views", "📥 Clones (14d)", "🐛 Issues"]
    st.dataframe(display, use_container_width=True, hide_index=True)

# ─── Language Breakdown ─────────────────────────────────────────────────────────

st.markdown('<div class="section-header">💻 Language Distribution</div>', unsafe_allow_html=True)

lang_df = query(f"""
    SELECT language, COUNT(*) as count, SUM(stars) as total_stars
    FROM repos WHERE repo IN ({placeholders}) AND language IS NOT NULL AND language != 'Unknown'
    GROUP BY language ORDER BY count DESC
""", selected_repos)

if not lang_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        fig = px.pie(lang_df, names="language", values="count",
                     title="Repos by Language", template="plotly_dark",
                     hole=0.4)
        fig.update_layout(plot_bgcolor="#0d1117", paper_bgcolor="#0d1117")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(lang_df, x="language", y="total_stars",
                     title="Stars by Language",
                     color="total_stars", color_continuous_scale="Viridis",
                     template="plotly_dark")
        fig.update_layout(plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
                          coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

# ─── Footer ────────────────────────────────────────────────────────────────────

st.divider()
st.markdown(
    "<div style='text-align:center;color:#8b949e;font-size:0.8rem'>"
    "GitHub Stats Tracker · Data updates daily via GitHub Actions"
    "</div>",
    unsafe_allow_html=True,
)
