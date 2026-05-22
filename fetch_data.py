#!/usr/bin/env python3
"""Fetch GitHub org data and generate index.html for GitHub Pages."""

import json
import os
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

TOKEN = os.environ["GITHUB_TOKEN"]
ORG = os.environ.get("GITHUB_ORG", "InX-AI-Innovation-Department")
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def get(path, params=""):
    url = f"https://api.github.com{path}?per_page=100{params}"
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req) as r:
            return json.loads(r.read())
    except HTTPError as e:
        print(f"HTTP {e.code} for {url}", file=sys.stderr)
        return []


def fetch():
    repos_raw = get(f"/orgs/{ORG}/repos", "&sort=pushed&direction=desc")
    repos = []
    all_prs = []
    all_issues = []
    contributors = {}

    for repo in repos_raw:
        name = repo["name"]
        repos.append({
            "name": name,
            "description": repo.get("description") or "",
            "language": repo.get("language") or "—",
            "pushed_at": repo.get("pushed_at", ""),
            "open_issues_count": repo.get("open_issues_count", 0),
            "html_url": repo["html_url"],
        })

        # PRs
        prs = get(f"/repos/{ORG}/{name}/pulls", "&state=open")
        for pr in prs:
            all_prs.append({
                "repo": name,
                "number": pr["number"],
                "title": pr["title"],
                "user": pr["user"]["login"],
                "created_at": pr["created_at"],
                "html_url": pr["html_url"],
                "draft": pr.get("draft", False),
            })

        # Issues (exclude PRs)
        issues_raw = get(f"/repos/{ORG}/{name}/issues", "&state=open")
        for issue in issues_raw:
            if "pull_request" not in issue:
                all_issues.append({
                    "repo": name,
                    "number": issue["number"],
                    "title": issue["title"],
                    "user": issue["user"]["login"],
                    "created_at": issue["created_at"],
                    "html_url": issue["html_url"],
                })

        # Contributors (top 10 per repo)
        contribs = get(f"/repos/{ORG}/{name}/stats/contributors")
        if isinstance(contribs, list):
            for c in contribs:
                login = c.get("author", {}).get("login", "unknown")
                total = c.get("total", 0)
                contributors[login] = contributors.get(login, 0) + total

    top_contributors = sorted(contributors.items(), key=lambda x: -x[1])[:10]

    return {
        "org": ORG,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "repos": repos,
        "open_prs": all_prs,
        "open_issues": all_issues,
        "contributors": [{"login": k, "commits": v} for k, v in top_contributors],
    }


def render_html(data):
    repos_json = json.dumps(data["repos"])
    prs_json = json.dumps(data["open_prs"])
    issues_json = json.dumps(data["open_issues"])
    contribs_json = json.dumps(data["contributors"])

    def ago(iso):
        if not iso:
            return "—"
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - dt
        d = diff.days
        if d == 0:
            return "今天"
        if d == 1:
            return "昨天"
        if d < 30:
            return f"{d} 天前"
        if d < 365:
            return f"{d // 30} 个月前"
        return f"{d // 365} 年前"

    pr_rows = ""
    for pr in data["open_prs"]:
        draft = ' <span style="color:#888;font-size:11px">[draft]</span>' if pr["draft"] else ""
        pr_rows += f"""<tr>
          <td><a href="{pr['html_url']}" target="_blank">{pr['repo']}#{pr['number']}</a></td>
          <td>{pr['title'][:60]}{draft}</td>
          <td>{pr['user']}</td>
          <td>{ago(pr['created_at'])}</td>
        </tr>"""

    issue_rows = ""
    for issue in data["open_issues"]:
        issue_rows += f"""<tr>
          <td><a href="{issue['html_url']}" target="_blank">{issue['repo']}#{issue['number']}</a></td>
          <td>{issue['title'][:60]}</td>
          <td>{issue['user']}</td>
          <td>{ago(issue['created_at'])}</td>
        </tr>"""

    repo_rows = ""
    for repo in data["repos"]:
        repo_rows += f"""<tr>
          <td><a href="{repo['html_url']}" target="_blank">{repo['name']}</a></td>
          <td>{repo['description'][:50] if repo['description'] else '—'}</td>
          <td>{repo['language']}</td>
          <td>{repo['open_issues_count']}</td>
          <td>{ago(repo['pushed_at'])}</td>
        </tr>"""

    contrib_bars = ""
    max_c = data["contributors"][0]["commits"] if data["contributors"] else 1
    for c in data["contributors"]:
        pct = int(c["commits"] / max_c * 100)
        contrib_bars += f"""<div class="contrib-row">
          <span class="contrib-name">{c['login']}</span>
          <div class="contrib-bar-wrap">
            <div class="contrib-bar" style="width:{pct}%"></div>
          </div>
          <span class="contrib-count">{c['commits']}</span>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{data['org']} — Org Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #0d1117; color: #c9d1d9; font-size: 14px; }}
  header {{ background: #161b22; border-bottom: 1px solid #30363d;
            padding: 16px 24px; display: flex; align-items: center; gap: 12px; }}
  header h1 {{ font-size: 18px; color: #e6edf3; }}
  header .updated {{ margin-left: auto; color: #8b949e; font-size: 12px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
  .stat-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                padding: 16px; text-align: center; }}
  .stat-card .num {{ font-size: 32px; font-weight: 700; color: #58a6ff; }}
  .stat-card .label {{ color: #8b949e; margin-top: 4px; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
  .card h2 {{ font-size: 14px; color: #e6edf3; margin-bottom: 12px;
              border-bottom: 1px solid #30363d; padding-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; color: #8b949e; font-weight: 500;
        padding: 6px 8px; border-bottom: 1px solid #21262d; }}
  td {{ padding: 8px; border-bottom: 1px solid #21262d; color: #c9d1d9;
        max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  td a {{ color: #58a6ff; text-decoration: none; }}
  td a:hover {{ text-decoration: underline; }}
  tr:last-child td {{ border-bottom: none; }}
  .contrib-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
  .contrib-name {{ width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .contrib-bar-wrap {{ flex: 1; background: #21262d; border-radius: 4px; height: 12px; overflow: hidden; }}
  .contrib-bar {{ background: #238636; height: 100%; border-radius: 4px; transition: width 0.3s; }}
  .contrib-count {{ width: 50px; text-align: right; color: #8b949e; }}
  .empty {{ color: #8b949e; font-style: italic; padding: 12px 0; }}
  @media (max-width: 768px) {{
    .stats {{ grid-template-columns: repeat(2, 1fr); }}
    .grid-2 {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<header>
  <svg width="24" height="24" viewBox="0 0 16 16" fill="#58a6ff">
    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
      0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
      -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66
      .07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15
      -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0
      1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82
      1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01
      1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
  </svg>
  <h1>{data['org']} Org Dashboard</h1>
  <span class="updated">更新于 {data['updated_at']}</span>
</header>

<div class="container">
  <div class="stats">
    <div class="stat-card">
      <div class="num">{len(data['repos'])}</div>
      <div class="label">Repositories</div>
    </div>
    <div class="stat-card">
      <div class="num">{len(data['open_prs'])}</div>
      <div class="label">Open PRs</div>
    </div>
    <div class="stat-card">
      <div class="num">{len(data['open_issues'])}</div>
      <div class="label">Open Issues</div>
    </div>
    <div class="stat-card">
      <div class="num">{len(data['contributors'])}</div>
      <div class="label">Contributors</div>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h2>Open PRs ({len(data['open_prs'])})</h2>
      {'<p class="empty">暂无待处理 PR</p>' if not data['open_prs'] else f'''<table>
        <thead><tr><th>PR</th><th>标题</th><th>作者</th><th>创建</th></tr></thead>
        <tbody>{pr_rows}</tbody>
      </table>'''}
    </div>
    <div class="card">
      <h2>Open Issues ({len(data['open_issues'])})</h2>
      {'<p class="empty">暂无待处理 Issue</p>' if not data['open_issues'] else f'''<table>
        <thead><tr><th>Issue</th><th>标题</th><th>作者</th><th>创建</th></tr></thead>
        <tbody>{issue_rows}</tbody>
      </table>'''}
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h2>Repositories ({len(data['repos'])})</h2>
      <table>
        <thead><tr><th>名称</th><th>描述</th><th>语言</th><th>Issues</th><th>更新</th></tr></thead>
        <tbody>{repo_rows}</tbody>
      </table>
    </div>
    <div class="card">
      <h2>Top Contributors (按 commit 数)</h2>
      {contrib_bars if contrib_bars else '<p class="empty">暂无数据</p>'}
    </div>
  </div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    print("Fetching org data...", file=sys.stderr)
    data = fetch()
    html = render_html(data)
    with open("index.html", "w") as f:
        f.write(html)
    print(f"Done: {len(data['repos'])} repos, {len(data['open_prs'])} PRs, {len(data['open_issues'])} issues", file=sys.stderr)
