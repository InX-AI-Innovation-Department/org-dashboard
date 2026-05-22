#!/usr/bin/env python3
"""Fetch GitHub org data and generate per-repo card dashboard."""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError

TOKEN = os.environ["GITHUB_TOKEN"]
ORG = os.environ.get("GITHUB_ORG", "InX-AI-Innovation-Department")
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
DEFAULT_BRANCHES = {"main", "master", "dev", "develop", "staging", "production"}
MERGED_DAYS = 14  # show merged PRs from last N days


def get(path, params=""):
    url = f"https://api.github.com{path}?per_page=100{params}"
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except HTTPError as e:
        print(f"HTTP {e.code} for {url}", file=sys.stderr)
        return [] if e.code != 404 else None
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return []


def ago(iso):
    if not iso:
        return "—"
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    diff = datetime.now(timezone.utc) - dt
    d = diff.days
    h = diff.seconds // 3600
    if d == 0:
        return f"{h} 小时前" if h > 0 else "刚刚"
    if d == 1:
        return "昨天"
    if d < 30:
        return f"{d} 天前"
    if d < 365:
        return f"{d // 30} 个月前"
    return f"{d // 365} 年前"


def fetch_repo(name):
    cutoff = datetime.now(timezone.utc) - timedelta(days=MERGED_DAYS)

    # Active branches (exclude default branches)
    branches_raw = get(f"/repos/{ORG}/{name}/branches")
    active_branches = [
        b["name"] for b in (branches_raw or [])
        if b["name"] not in DEFAULT_BRANCHES
    ]

    # Open PRs
    open_prs = []
    for pr in (get(f"/repos/{ORG}/{name}/pulls", "&state=open&sort=updated") or []):
        open_prs.append({
            "number": pr["number"],
            "title": pr["title"],
            "user": pr["user"]["login"],
            "created_at": pr["created_at"],
            "draft": pr.get("draft", False),
            "url": pr["html_url"],
        })

    # Recently merged PRs
    merged_prs = []
    for pr in (get(f"/repos/{ORG}/{name}/pulls", "&state=closed&sort=updated&direction=desc") or []):
        if not pr.get("merged_at"):
            continue
        merged_at = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
        if merged_at < cutoff:
            break
        merged_prs.append({
            "number": pr["number"],
            "title": pr["title"],
            "user": pr["user"]["login"],
            "merged_at": pr["merged_at"],
            "url": pr["html_url"],
        })

    # Open issues (exclude PRs)
    open_issues = []
    for issue in (get(f"/repos/{ORG}/{name}/issues", "&state=open&sort=updated") or []):
        if "pull_request" not in issue:
            open_issues.append({
                "number": issue["number"],
                "title": issue["title"],
                "user": issue["user"]["login"],
                "created_at": issue["created_at"],
                "url": issue["html_url"],
            })

    # Latest release
    release = get(f"/repos/{ORG}/{name}/releases/latest")
    latest_release = None
    if release and isinstance(release, dict) and release.get("tag_name"):
        latest_release = {
            "tag": release["tag_name"],
            "name": release.get("name") or release["tag_name"],
            "published_at": release.get("published_at", ""),
            "url": release["html_url"],
        }

    return {
        "active_branches": active_branches,
        "open_prs": open_prs,
        "merged_prs": merged_prs,
        "open_issues": open_issues,
        "latest_release": latest_release,
    }


def fetch():
    repos_raw = get(f"/orgs/{ORG}/repos", "&sort=pushed&direction=desc")
    repos = []
    for repo in (repos_raw or []):
        name = repo["name"]
        print(f"  Fetching {name}...", file=sys.stderr)
        data = fetch_repo(name)
        repos.append({
            "name": name,
            "description": repo.get("description") or "",
            "language": repo.get("language") or "",
            "pushed_at": repo.get("pushed_at", ""),
            "html_url": repo["html_url"],
            "default_branch": repo.get("default_branch", "main"),
            **data,
        })

    total_open_prs = sum(len(r["open_prs"]) for r in repos)
    total_open_issues = sum(len(r["open_issues"]) for r in repos)
    total_merged = sum(len(r["merged_prs"]) for r in repos)

    return {
        "org": ORG,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "repos": repos,
        "summary": {
            "repos": len(repos),
            "open_prs": total_open_prs,
            "open_issues": total_open_issues,
            "merged_14d": total_merged,
        },
    }


def render_repo_card(repo):
    name = repo["name"]
    desc = repo["description"]
    lang = repo["language"]
    pushed = ago(repo["pushed_at"])
    url = repo["html_url"]

    # Header badge colors by language
    lang_colors = {
        "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#2b7489",
        "HTML": "#e34c26", "Go": "#00ADD8", "Rust": "#dea584",
        "Java": "#b07219", "CSS": "#563d7c", "Shell": "#89e051",
    }
    lang_color = lang_colors.get(lang, "#8b949e")

    # Active branches
    branches_html = ""
    if repo["active_branches"]:
        items = "".join(
            f'<span class="branch-tag">{b}</span>'
            for b in repo["active_branches"][:6]
        )
        extra = f'<span class="branch-more">+{len(repo["active_branches"]) - 6} more</span>' if len(repo["active_branches"]) > 6 else ""
        branches_html = f'<div class="section-content branches">{items}{extra}</div>'
    else:
        branches_html = '<div class="section-content empty">无活跃功能分支</div>'

    # Open PRs
    if repo["open_prs"]:
        rows = ""
        for pr in repo["open_prs"][:5]:
            draft = ' <span class="draft-badge">draft</span>' if pr["draft"] else ""
            rows += f'''<div class="item-row">
              <a href="{pr['url']}" target="_blank" class="item-link">
                <span class="item-num">#{pr['number']}</span>
                <span class="item-title">{pr['title'][:55]}{draft}</span>
              </a>
              <span class="item-meta">{pr['user']} · {ago(pr['created_at'])}</span>
            </div>'''
        extra_note = f'<div class="more-note">还有 {len(repo["open_prs"]) - 5} 个 PR...</div>' if len(repo["open_prs"]) > 5 else ""
        open_prs_html = f'<div class="section-content">{rows}{extra_note}</div>'
    else:
        open_prs_html = '<div class="section-content empty">无进行中 PR</div>'

    # Merged PRs (changelog)
    if repo["merged_prs"]:
        rows = ""
        for pr in repo["merged_prs"][:6]:
            rows += f'''<div class="item-row">
              <a href="{pr['url']}" target="_blank" class="item-link">
                <span class="item-num">#{pr['number']}</span>
                <span class="item-title">{pr['title'][:55]}</span>
              </a>
              <span class="item-meta">{pr['user']} · {ago(pr['merged_at'])}</span>
            </div>'''
        extra_note = f'<div class="more-note">还有 {len(repo["merged_prs"]) - 6} 个...</div>' if len(repo["merged_prs"]) > 6 else ""
        merged_html = f'<div class="section-content">{rows}{extra_note}</div>'
    else:
        merged_html = f'<div class="section-content empty">近 {MERGED_DAYS} 天暂无合并</div>'

    # Open Issues
    if repo["open_issues"]:
        rows = ""
        for issue in repo["open_issues"][:5]:
            rows += f'''<div class="item-row">
              <a href="{issue['url']}" target="_blank" class="item-link">
                <span class="item-num">#{issue['number']}</span>
                <span class="item-title">{issue['title'][:55]}</span>
              </a>
              <span class="item-meta">{issue['user']} · {ago(issue['created_at'])}</span>
            </div>'''
        extra_note = f'<div class="more-note">还有 {len(repo["open_issues"]) - 5} 个...</div>' if len(repo["open_issues"]) > 5 else ""
        issues_html = f'<div class="section-content">{rows}{extra_note}</div>'
    else:
        issues_html = '<div class="section-content empty">无待处理 Issue</div>'

    # Latest Release
    if repo["latest_release"]:
        r = repo["latest_release"]
        release_html = f'''<div class="section-content">
          <a href="{r['url']}" target="_blank" class="release-tag">🚀 {r['tag']}</a>
          <span class="item-meta" style="margin-left:8px">{ago(r['published_at'])}</span>
        </div>'''
    else:
        release_html = '<div class="section-content empty">暂无 Release</div>'

    lang_badge = f'<span class="lang-dot" style="background:{lang_color}"></span><span class="lang-name">{lang}</span>' if lang else ""

    return f'''<div class="repo-card">
  <div class="card-header">
    <div class="card-title-row">
      <a href="{url}" target="_blank" class="repo-name">{name}</a>
      {lang_badge}
    </div>
    {f'<div class="repo-desc">{desc}</div>' if desc else ''}
    <div class="repo-meta">最后推送 {pushed}</div>
  </div>

  <div class="card-section">
    <div class="section-title">
      <span class="section-icon">⑂</span> 活跃分支
      <span class="count-badge">{len(repo["active_branches"])}</span>
    </div>
    {branches_html}
  </div>

  <div class="card-section">
    <div class="section-title">
      <span class="section-icon">⟳</span> 进行中
      <span class="count-badge {'badge-warn' if len(repo['open_prs']) > 3 else ''}">{len(repo["open_prs"])}</span>
    </div>
    {open_prs_html}
  </div>

  <div class="card-section">
    <div class="section-title">
      <span class="section-icon">✓</span> 近 {MERGED_DAYS} 天完成
      <span class="count-badge badge-green">{len(repo["merged_prs"])}</span>
    </div>
    {merged_html}
  </div>

  <div class="card-section">
    <div class="section-title">
      <span class="section-icon">◎</span> Issues
      <span class="count-badge {'badge-warn' if len(repo['open_issues']) > 5 else ''}">{len(repo["open_issues"])}</span>
    </div>
    {issues_html}
  </div>

  <div class="card-section">
    <div class="section-title">
      <span class="section-icon">↑</span> 最新 Release
    </div>
    {release_html}
  </div>
</div>'''


def render_html(data):
    s = data["summary"]
    cards = "\n".join(render_repo_card(r) for r in data["repos"])

    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{data['org']} — Dev Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #0d1117; color: #c9d1d9; font-size: 13px; line-height: 1.5; }}

  /* Header */
  header {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 14px 24px;
            display: flex; align-items: center; gap: 12px; }}
  header h1 {{ font-size: 16px; color: #e6edf3; font-weight: 600; }}
  .updated {{ margin-left: auto; color: #8b949e; font-size: 11px; }}

  /* Summary bar */
  .summary {{ display: flex; gap: 24px; padding: 14px 24px;
              background: #161b22; border-bottom: 1px solid #30363d; }}
  .summary-item {{ display: flex; align-items: center; gap: 6px; color: #8b949e; font-size: 12px; }}
  .summary-item strong {{ color: #e6edf3; font-size: 15px; }}

  /* Grid */
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
           gap: 16px; padding: 20px 24px; max-width: 1400px; margin: 0 auto; }}

  /* Repo Card */
  .repo-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px;
                overflow: hidden; display: flex; flex-direction: column; }}
  .card-header {{ padding: 14px 16px 12px; border-bottom: 1px solid #21262d; }}
  .card-title-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
  .repo-name {{ color: #58a6ff; font-size: 14px; font-weight: 600;
                text-decoration: none; }}
  .repo-name:hover {{ text-decoration: underline; }}
  .lang-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block;
               margin-left: auto; flex-shrink: 0; }}
  .lang-name {{ color: #8b949e; font-size: 11px; }}
  .repo-desc {{ color: #8b949e; font-size: 12px; margin-top: 2px;
                overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .repo-meta {{ color: #484f58; font-size: 11px; margin-top: 4px; }}

  /* Sections */
  .card-section {{ padding: 10px 16px; border-bottom: 1px solid #21262d; }}
  .card-section:last-child {{ border-bottom: none; }}
  .section-title {{ display: flex; align-items: center; gap: 5px;
                    color: #8b949e; font-size: 11px; font-weight: 600;
                    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
  .section-icon {{ font-size: 13px; }}
  .count-badge {{ margin-left: auto; background: #21262d; color: #8b949e;
                  border-radius: 10px; padding: 1px 7px; font-size: 11px; font-weight: 600; }}
  .count-badge.badge-green {{ background: #1a3a1f; color: #3fb950; }}
  .count-badge.badge-warn {{ background: #3a1f1a; color: #f78166; }}
  .section-content {{ }}
  .section-content.empty {{ color: #484f58; font-style: italic; font-size: 12px; padding: 2px 0; }}

  /* Items */
  .item-row {{ display: flex; align-items: baseline; justify-content: space-between;
               gap: 8px; padding: 3px 0; border-bottom: 1px solid #21262d; }}
  .item-row:last-of-type {{ border-bottom: none; }}
  .item-link {{ display: flex; align-items: baseline; gap: 6px;
                color: #c9d1d9; text-decoration: none; min-width: 0; flex: 1; }}
  .item-link:hover .item-title {{ color: #58a6ff; }}
  .item-num {{ color: #484f58; font-size: 11px; flex-shrink: 0; }}
  .item-title {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
                 font-size: 12px; }}
  .item-meta {{ color: #484f58; font-size: 11px; white-space: nowrap; flex-shrink: 0; }}
  .more-note {{ color: #484f58; font-size: 11px; padding-top: 4px; }}
  .draft-badge {{ background: #21262d; color: #8b949e; border-radius: 4px;
                  padding: 0 4px; font-size: 10px; }}

  /* Branches */
  .branches {{ display: flex; flex-wrap: wrap; gap: 4px; }}
  .branch-tag {{ background: #1c2128; border: 1px solid #30363d; color: #8b949e;
                 border-radius: 12px; padding: 1px 8px; font-size: 11px;
                 font-family: monospace; }}
  .branch-more {{ color: #484f58; font-size: 11px; align-self: center; }}

  /* Release */
  .release-tag {{ background: #1a3a1f; color: #3fb950; border-radius: 12px;
                  padding: 2px 10px; font-size: 12px; text-decoration: none; }}
  .release-tag:hover {{ background: #213d25; }}

  @media (max-width: 600px) {{
    .grid {{ grid-template-columns: 1fr; padding: 12px; }}
    .summary {{ flex-wrap: wrap; gap: 12px; }}
  }}
</style>
</head>
<body>

<header>
  <svg width="20" height="20" viewBox="0 0 16 16" fill="#58a6ff">
    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
      0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
      -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66
      .07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15
      -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0
      1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82
      1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01
      1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
  </svg>
  <h1>{data['org']} Dev Dashboard</h1>
  <span class="updated">更新于 {data['updated_at']}</span>
</header>

<div class="summary">
  <div class="summary-item"><strong>{s['repos']}</strong> Repos</div>
  <div class="summary-item"><strong>{s['open_prs']}</strong> 进行中 PRs</div>
  <div class="summary-item"><strong>{s['merged_14d']}</strong> 近 {MERGED_DAYS} 天已合并</div>
  <div class="summary-item"><strong>{s['open_issues']}</strong> Open Issues</div>
</div>

<div class="grid">
{cards}
</div>

</body>
</html>'''


if __name__ == "__main__":
    print("Fetching org data...", file=sys.stderr)
    data = fetch()
    html = render_html(data)
    with open("index.html", "w") as f:
        f.write(html)
    s = data["summary"]
    print(
        f"Done: {s['repos']} repos, {s['open_prs']} open PRs, "
        f"{s['merged_14d']} merged (14d), {s['open_issues']} issues",
        file=sys.stderr,
    )
