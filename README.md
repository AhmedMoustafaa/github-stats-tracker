# 📊 GitHub Stats Tracker

Track, store, and visualize traffic & statistics for **all your GitHub repos** — forever.

GitHub only retains 14 days of traffic data. This project fetches it daily and stores it permanently in a SQLite database, then visualizes everything in a Streamlit dashboard.

---

## Features

- **Views, unique visitors, clones** per repo per day
- **Stars history** over time
- **Top referrers** (where traffic comes from)
- **Popular content paths**
- **Language distribution** across repos
- Beautiful dark-mode Plotly dashboard
- Automated daily collection via GitHub Actions (free)

---

## Project Structure

```
github-stats-tracker/
├── collect_stats.py          # Fetches data from GitHub API → SQLite
├── dashboard.py              # Streamlit dashboard
├── requirements.txt
├── .env.example              # Environment variable template
├── .gitignore
└── .github/
    └── workflows/
        └── collect-stats.yml # Daily GitHub Actions cron job
```

---

## 🚀 Deployment Guide

### Step 1 — Create a GitHub Personal Access Token

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Click **Generate new token (classic)**
3. Give it a name like `stats-tracker`
4. Check the **`repo`** scope (full control of private repos — needed for traffic data)
5. Set expiration to **1 year** (or no expiration)
6. Click **Generate token** and copy it — you won't see it again

---

### Step 2 — Set Up the Repo

```bash
# Clone or fork this repo
git clone https://github.com/YOUR_USERNAME/github-stats-tracker.git
cd github-stats-tracker

# Install dependencies
pip install -r requirements.txt

# Copy and fill in the env file
cp .env.example .env
# Edit .env with your token and username
```

---

### Step 3 — Run the Collector Locally (First Time)

```bash
# Load env variables
export $(cat .env | xargs)

# Run the collector
python collect_stats.py
```

This creates `github_stats.db` with all your repo data.
Run it again tomorrow to start accumulating history.

---

### Step 4 — View the Dashboard Locally

```bash
streamlit run dashboard.py
```

Open http://localhost:8501 in your browser.

---

### Step 5 — Automate with GitHub Actions (Daily Collection)

1. Push this repo to GitHub (the DB will be committed back automatically each day):

```bash
git add .
git commit -m "init: github stats tracker"
git push origin main
```

2. Go to your repo on GitHub → **Settings → Secrets and variables → Actions**

3. Add two **Repository secrets**:
   - `STATS_TOKEN` → your Personal Access Token from Step 1
   - `GH_USERNAME` → your GitHub username (e.g. `ahmed`)

4. Go to **Actions** tab → find **"Collect GitHub Stats"** → click **"Run workflow"** to test it manually

5. From now on, it runs automatically every day at 6:00 AM UTC. The updated `github_stats.db` is committed back to the repo automatically.

---

### Step 6 — Deploy the Dashboard (Optional)

#### Option A: Streamlit Community Cloud (Free, Recommended)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app** → select your repo → set **Main file path** to `dashboard.py`
3. In **Advanced settings → Secrets**, add:
   ```toml
   GITHUB_TOKEN = "ghp_..."
   GITHUB_USERNAME = "your_username"
   DB_PATH = "github_stats.db"
   ```
4. Click **Deploy** — your dashboard will be live at a public URL

> The dashboard reads `github_stats.db` directly from the repo, which GitHub Actions updates daily.

#### Option B: Run Locally Always

Just run `streamlit run dashboard.py` whenever you want to check your stats.

#### Option C: Self-host on a VPS / Railway / Render

Set the environment variables and run:
```bash
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0
```

---

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GITHUB_TOKEN` | Personal Access Token with `repo` scope | ✅ |
| `GITHUB_USERNAME` | Your GitHub username | Optional (auto-detected) |
| `DB_PATH` | Path to the SQLite database | Optional (default: `github_stats.db`) |

---

## FAQ

**Why does traffic data only go back 14 days on first run?**
GitHub's API only returns the last 14 days of traffic. After running daily, you'll accumulate unlimited history.

**Why are some repos missing traffic data?**
Traffic endpoints require **push access**. Forked repos or org repos you don't own will be skipped gracefully.

**Can I track org repos too?**
Yes — change `get_all_repos` in `collect_stats.py` to use `/orgs/{org}/repos` instead of `/users/{username}/repos`.
