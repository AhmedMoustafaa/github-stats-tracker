"""
GitHub Stats Collector
Fetches traffic + repo stats for all your repos and stores them in SQLite.
Run daily (via GitHub Actions or cron) to build up historical data.
"""

import os
import sqlite3
import requests
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "")   # leave blank to auto-detect
DB_PATH = os.environ.get("DB_PATH", "github_stats.db")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

# ─── Database Setup ────────────────────────────────────────────────────────────

def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS repos (
            repo        TEXT PRIMARY KEY,
            owner       TEXT,
            description TEXT,
            url         TEXT,
            stars       INTEGER DEFAULT 0,
            forks       INTEGER DEFAULT 0,
            watchers    INTEGER DEFAULT 0,
            open_issues INTEGER DEFAULT 0,
            size_kb     INTEGER DEFAULT 0,
            language    TEXT,
            private     INTEGER DEFAULT 0,
            updated_at  TEXT,
            fetched_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS traffic_views (
            repo         TEXT,
            date         TEXT,
            views        INTEGER DEFAULT 0,
            unique_views INTEGER DEFAULT 0,
            fetched_at   TEXT,
            PRIMARY KEY (repo, date)
        );

        CREATE TABLE IF NOT EXISTS traffic_clones (
            repo          TEXT,
            date          TEXT,
            clones        INTEGER DEFAULT 0,
            unique_clones INTEGER DEFAULT 0,
            fetched_at    TEXT,
            PRIMARY KEY (repo, date)
        );

        CREATE TABLE IF NOT EXISTS referrers (
            repo        TEXT,
            referrer    TEXT,
            count       INTEGER DEFAULT 0,
            uniques     INTEGER DEFAULT 0,
            fetched_at  TEXT,
            PRIMARY KEY (repo, referrer, fetched_at)
        );

        CREATE TABLE IF NOT EXISTS popular_paths (
            repo       TEXT,
            path       TEXT,
            title      TEXT,
            count      INTEGER DEFAULT 0,
            uniques    INTEGER DEFAULT 0,
            fetched_at TEXT,
            PRIMARY KEY (repo, path, fetched_at)
        );

        CREATE TABLE IF NOT EXISTS repo_stars_history (
            repo       TEXT,
            date       TEXT,
            stars      INTEGER DEFAULT 0,
            fetched_at TEXT,
            PRIMARY KEY (repo, date)
        );
    """)
    conn.commit()
    log.info("Database initialized.")

# ─── GitHub API Helpers ────────────────────────────────────────────────────────

def gh_get(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 204:
            return None
        if r.status_code == 403:
            log.warning(f"403 Forbidden: {url} — skipping (no push access?)")
            return None
        if r.status_code == 409:
            log.warning(f"409 Conflict (empty repo?): {url} — skipping")
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.error(f"Request failed: {url} → {e}")
        return None

def get_authenticated_user():
    data = gh_get("https://api.github.com/user")
    return data["login"] if data else None

def get_all_repos(username):
    repos, page = [], 1
    while True:
        batch = gh_get(
            f"https://api.github.com/users/{username}/repos",
            params={"per_page": 100, "page": page, "type": "owner"},
        )
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    log.info(f"Found {len(repos)} repos for {username}")
    return repos

# ─── Collectors ────────────────────────────────────────────────────────────────

def collect_repo_info(conn, repo):
    now = datetime.now(timezone.utc).isoformat()
    full_name = repo["full_name"]
    conn.execute("""
        INSERT OR REPLACE INTO repos
        (repo, owner, description, url, stars, forks, watchers,
         open_issues, size_kb, language, private, updated_at, fetched_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        full_name,
        repo["owner"]["login"],
        repo.get("description") or "",
        repo.get("html_url", ""),
        repo.get("stargazers_count", 0),
        repo.get("forks_count", 0),
        repo.get("watchers_count", 0),
        repo.get("open_issues_count", 0),
        repo.get("size", 0),
        repo.get("language") or "Unknown",
        1 if repo.get("private") else 0,
        repo.get("updated_at", ""),
        now,
    ))

    # Record stars history snapshot
    today = datetime.now(timezone.utc).date().isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO repo_stars_history (repo, date, stars, fetched_at)
        VALUES (?,?,?,?)
    """, (full_name, today, repo.get("stargazers_count", 0), now))
    conn.commit()

def collect_traffic_views(conn, owner, repo_name, full_name):
    data = gh_get(f"https://api.github.com/repos/{owner}/{repo_name}/traffic/views")
    if not data:
        return
    now = datetime.now(timezone.utc).isoformat()
    for day in data.get("views", []):
        conn.execute("""
            INSERT OR REPLACE INTO traffic_views
            (repo, date, views, unique_views, fetched_at)
            VALUES (?,?,?,?,?)
        """, (full_name, day["timestamp"][:10], day["count"], day["uniques"], now))
    conn.commit()

def collect_traffic_clones(conn, owner, repo_name, full_name):
    data = gh_get(f"https://api.github.com/repos/{owner}/{repo_name}/traffic/clones")
    if not data:
        return
    now = datetime.now(timezone.utc).isoformat()
    for day in data.get("clones", []):
        conn.execute("""
            INSERT OR REPLACE INTO traffic_clones
            (repo, date, clones, unique_clones, fetched_at)
            VALUES (?,?,?,?,?)
        """, (full_name, day["timestamp"][:10], day["count"], day["uniques"], now))
    conn.commit()

def collect_referrers(conn, owner, repo_name, full_name):
    data = gh_get(f"https://api.github.com/repos/{owner}/{repo_name}/traffic/popular/referrers")
    if not data:
        return
    now = datetime.now(timezone.utc).isoformat()
    for ref in data:
        conn.execute("""
            INSERT OR REPLACE INTO referrers
            (repo, referrer, count, uniques, fetched_at)
            VALUES (?,?,?,?,?)
        """, (full_name, ref["referrer"], ref["count"], ref["uniques"], now))
    conn.commit()

def collect_popular_paths(conn, owner, repo_name, full_name):
    data = gh_get(f"https://api.github.com/repos/{owner}/{repo_name}/traffic/popular/paths")
    if not data:
        return
    now = datetime.now(timezone.utc).isoformat()
    for p in data:
        conn.execute("""
            INSERT OR REPLACE INTO popular_paths
            (repo, path, title, count, uniques, fetched_at)
            VALUES (?,?,?,?,?,?)
        """, (full_name, p["path"], p.get("title", ""), p["count"], p["uniques"], now))
    conn.commit()

# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable is not set.")

    username = GITHUB_USERNAME or get_authenticated_user()
    if not username:
        raise ValueError("Could not determine GitHub username.")
    log.info(f"Collecting stats for: {username}")

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    repos = get_all_repos(username)
    for i, repo in enumerate(repos, 1):
        full_name = repo["full_name"]
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        log.info(f"[{i}/{len(repos)}] Processing {full_name}")

        collect_repo_info(conn, repo)
        collect_traffic_views(conn, owner, repo_name, full_name)
        collect_traffic_clones(conn, owner, repo_name, full_name)
        collect_referrers(conn, owner, repo_name, full_name)
        collect_popular_paths(conn, owner, repo_name, full_name)

    conn.close()
    log.info("✅ Collection complete.")

if __name__ == "__main__":
    main()
