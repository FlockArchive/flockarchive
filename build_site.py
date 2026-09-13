#!/usr/bin/env python3
"""Builds static HTML site from archive/index.json for GitHub Pages."""

import json
from datetime import datetime
from pathlib import Path
from html import escape
from urllib.parse import urlparse

SITE_DIR = Path("_site")
INDEX_FILE = Path("archive/index.json")
URLS_FILE = Path("urls.json")


def load_data():
    index = json.loads(INDEX_FILE.read_text()) if INDEX_FILE.exists() else {"snapshots": [], "urls": {}}
    urls = json.loads(URLS_FILE.read_text()) if URLS_FILE.exists() else {"urls": []}
    return index, urls


def fmt_time(iso_str):
    if not iso_str:
        return "Never"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso_str[:19]


DARK_CSS = """
:root { --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #e6edf3;
        --text-dim: #8b949e; --accent: #58a6ff; --green: #3fb950; --red: #f85149;
        --orange: #d29922; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: var(--bg); color: var(--text); line-height: 1.5; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.container { max-width: 1100px; margin: 0 auto; padding: 16px 24px; }
header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 12px 0; }
header .container { display: flex; justify-content: space-between; align-items: center; }
header h1 { font-size: 1.2rem; }
nav a { margin-left: 16px; color: var(--text-dim); font-size: 0.9rem; }
nav a:hover { color: var(--text); }
.stats { display: flex; gap: 16px; margin: 20px 0; flex-wrap: wrap; }
.stat { background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
        padding: 16px 20px; flex: 1; min-width: 140px; }
.stat .value { font-size: 1.8rem; font-weight: 600; }
.stat .label { color: var(--text-dim); font-size: 0.85rem; }
table { width: 100%; border-collapse: collapse; margin: 16px 0; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); }
th { color: var(--text-dim); font-size: 0.85rem; font-weight: 500; }
td { font-size: 0.9rem; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem;
         font-weight: 500; }
.badge-changed { background: rgba(248,81,73,0.15); color: var(--red); }
.badge-ok { background: rgba(63,185,80,0.15); color: var(--green); }
.badge-error { background: rgba(210,153,34,0.15); color: var(--orange); }
.badge-seed { background: rgba(88,166,255,0.15); color: var(--accent); }
.badge-user { background: rgba(63,185,80,0.15); color: var(--green); }
.url-text { max-width: 500px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.search-form { display: flex; gap: 8px; margin: 16px 0; }
.search-form input { flex: 1; padding: 8px 12px; background: var(--surface); border: 1px solid var(--border);
                      border-radius: 6px; color: var(--text); font-size: 0.9rem; }
.submit-section { background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
                  padding: 20px; margin: 20px 0; }
.submit-section h3 { margin-bottom: 12px; font-size: 1rem; }
.submit-form { display: flex; gap: 8px; }
.submit-form input { flex: 1; padding: 8px 12px; background: var(--bg); border: 1px solid var(--border);
                     border-radius: 6px; color: var(--text); font-size: 0.9rem; }
.btn { padding: 8px 16px; background: var(--accent); color: #fff; border: none;
       border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; }
.btn:hover { opacity: 0.9; }
.snapshot-viewer { background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
                   margin: 16px 0; }
.snapshot-viewer iframe { width: 100%; height: 600px; border: none; border-radius: 0 0 6px 6px; }
.snapshot-header { padding: 12px 16px; border-bottom: 1px solid var(--border); display: flex;
                   justify-content: space-between; align-items: center; }
footer { margin-top: 40px; padding: 20px 0; border-top: 1px solid var(--border);
         color: var(--text-dim); font-size: 0.8rem; text-align: center; }
#submit-status { margin-top: 8px; font-size: 0.9rem; }
"""


def page_wrapper(title, content, active=""):
    nav_items = [
        ("index.html", "Dashboard", "dashboard"),
        ("urls.html", "URLs", "urls"),
    ]
    nav_html = ""
    for href, label, key in nav_items:
        cls = ' style="color: var(--text)"' if key == active else ""
        nav_html += f'<a href="{href}"{cls}>{label}</a>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Flock Archive</title>
<style>{DARK_CSS}</style>
</head>
<body>
<header><div class="container">
<h1>Flock Archive</h1>
<nav>{nav_html}</nav>
</div></header>
<div class="container">
{content}
</div>
<footer><div class="container">
Flock Archive — Preserving public accountability records<br>
Flock Safety blocks the Wayback Machine from archiving their sites. We don't.
</div></footer>
</body>
</html>"""


def build_index_page(index, urls_data):
    url_count = len(urls_data["urls"])
    snapshot_count = len(index["snapshots"])
    changed_count = sum(1 for s in index["snapshots"] if s.get("changed"))

    recent = sorted(index["snapshots"], key=lambda s: s.get("timestamp", ""), reverse=True)[:50]

    rows = ""
    for s in recent:
        url = escape(s["url"])
        ts = fmt_time(s.get("timestamp"))
        if s.get("error"):
            badge = '<span class="badge badge-error">ERROR</span>'
        elif s.get("changed"):
            badge = '<span class="badge badge-changed">CHANGED</span>'
        else:
            badge = '<span class="badge badge-ok">OK</span>'

        snapshot_link = ""
        if s.get("html_path"):
            snapshot_link = f'<a href="{s["html_path"]}">View</a>'

        rows += f"""<tr>
            <td class="url-text">{url}</td>
            <td>{ts}</td>
            <td>{badge}</td>
            <td>{snapshot_link}</td>
        </tr>"""

    content = f"""
    <div class="stats">
        <div class="stat"><div class="value">{url_count}</div><div class="label">Tracked URLs</div></div>
        <div class="stat"><div class="value">{snapshot_count}</div><div class="label">Total Snapshots</div></div>
        <div class="stat"><div class="value">{changed_count}</div><div class="label">Changes Detected</div></div>
    </div>

    <div class="submit-section">
        <h3>Submit a URL for Archival</h3>
        <div class="submit-form">
            <input type="text" id="submit-url" placeholder="https://www.flocksafety.com/...">
            <button class="btn" onclick="submitUrl()">Archive It</button>
        </div>
        <div id="submit-status"></div>
    </div>

    <h2 style="margin: 20px 0 8px; font-size: 1.1rem;">Recent Snapshots</h2>
    <table>
    <thead><tr><th>URL</th><th>Captured</th><th>Status</th><th>View</th></tr></thead>
    <tbody>{rows}</tbody>
    </table>

    <script>
    async function submitUrl() {{
        const url = document.getElementById('submit-url').value.trim();
        const status = document.getElementById('submit-status');
        if (!url) {{ status.textContent = 'Please enter a URL.'; return; }}
        try {{
            const u = new URL(url.startsWith('http') ? url : 'https://' + url);
            if (!u.hostname.endsWith('flocksafety.com')) {{
                status.textContent = 'Only flocksafety.com URLs are accepted.';
                return;
            }}
        }} catch {{ status.textContent = 'Invalid URL.'; return; }}
        status.textContent = 'Submitting...';
        try {{
            const resp = await fetch('https://flockarchivesubmit.cloudflare-hamper588.workers.dev', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ url: url }})
            }});
            const data = await resp.json();
            if (data.ok) {{
                status.innerHTML = '<span style="color: var(--green)">URL submitted! It will be archived on the next crawl.</span>';
                document.getElementById('submit-url').value = '';
            }} else {{
                status.innerHTML = '<span style="color: var(--red)">' + (data.error || 'Error submitting. Try again.') + '</span>';
            }}
        }} catch(e) {{
            status.innerHTML = '<span style="color: var(--red)">Network error. Try again later.</span>';
        }}
    }}
    </script>
    """
    return page_wrapper("Dashboard", content, "dashboard")


def build_urls_page(index, urls_data):
    rows = ""
    for entry in urls_data["urls"]:
        url = entry["url"]
        url_info = index["urls"].get(url, {})
        url_esc = escape(url)
        last_checked = fmt_time(url_info.get("last_checked"))
        url_type = entry.get("type", "seed")
        badge_cls = "badge-seed" if url_type == "seed" else "badge-user"

        url_path = url_info.get("path", url_to_path(url))
        history_link = f'<a href="url/{url_path}.html">History</a>' if url_info else ""

        rows += f"""<tr>
            <td class="url-text"><a href="{url_esc}" target="_blank" rel="noopener">{url_esc}</a></td>
            <td>{last_checked}</td>
            <td><span class="badge {badge_cls}">{url_type.upper()}</span></td>
            <td>{history_link}</td>
        </tr>"""

    content = f"""
    <h2 style="margin-bottom: 8px; font-size: 1.1rem;">Tracked URLs ({len(urls_data['urls'])})</h2>
    <div class="search-form">
        <input type="text" id="url-search" placeholder="Filter URLs..." oninput="filterUrls()">
    </div>
    <table id="url-table">
    <thead><tr><th>URL</th><th>Last Checked</th><th>Type</th><th>History</th></tr></thead>
    <tbody>{rows}</tbody>
    </table>

    <script>
    function filterUrls() {{
        const q = document.getElementById('url-search').value.toLowerCase();
        const rows = document.querySelectorAll('#url-table tbody tr');
        rows.forEach(row => {{
            const url = row.cells[0].textContent.toLowerCase();
            row.style.display = url.includes(q) ? '' : 'none';
        }});
    }}
    </script>
    """
    return page_wrapper("Tracked URLs", content, "urls")


def url_to_path(url):
    parsed = urlparse(url)
    host = parsed.hostname or "unknown"
    path = parsed.path.strip("/").replace("/", "_") or "index"
    return f"{host}/{path}"


def build_url_history_pages(index):
    by_url = {}
    for s in index["snapshots"]:
        by_url.setdefault(s["url"], []).append(s)

    for url, snapshots in by_url.items():
        snapshots.sort(key=lambda s: s.get("timestamp", ""), reverse=True)
        url_path = url_to_path(url)
        url_esc = escape(url)

        rows = ""
        for s in snapshots:
            ts = fmt_time(s.get("timestamp"))
            if s.get("error"):
                badge = '<span class="badge badge-error">ERROR</span>'
            elif s.get("changed"):
                badge = '<span class="badge badge-changed">CHANGED</span>'
            else:
                badge = '<span class="badge badge-ok">OK</span>'

            view = ""
            if s.get("html_path"):
                view = f'<a href="../{s["html_path"]}">HTML</a>'
            if s.get("screenshot_path"):
                view += f' | <a href="../{s["screenshot_path"]}">Screenshot</a>'

            error_text = f' — {escape(s["error"])}' if s.get("error") else ""
            rows += f"<tr><td>{ts}</td><td>{badge}{error_text}</td><td>{(s.get('hash') or '')[:12]}</td><td>{view}</td></tr>"

        content = f"""
        <h2 style="margin-bottom: 4px; font-size: 1.1rem;">History</h2>
        <p style="color: var(--text-dim); margin-bottom: 16px; word-break: break-all;">
            <a href="{url_esc}" target="_blank" rel="noopener">{url_esc}</a>
        </p>
        <table>
        <thead><tr><th>Captured</th><th>Status</th><th>Hash</th><th>View</th></tr></thead>
        <tbody>{rows}</tbody>
        </table>
        <p style="margin-top: 16px;"><a href="../urls.html">&larr; All URLs</a></p>
        """

        out = SITE_DIR / "url" / f"{url_path}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page_wrapper(f"History — {url_esc}", content))


def main():
    SITE_DIR.mkdir(exist_ok=True)
    index, urls_data = load_data()

    (SITE_DIR / "index.html").write_text(build_index_page(index, urls_data))
    (SITE_DIR / "urls.html").write_text(build_urls_page(index, urls_data))
    build_url_history_pages(index)

    archive_src = Path("archive")
    if archive_src.exists():
        import shutil
        archive_dst = SITE_DIR / "archive"
        if archive_dst.exists():
            shutil.rmtree(archive_dst)
        shutil.copytree(archive_src, archive_dst)

    print(f"Built site → {SITE_DIR}/")
    print(f"  {len(urls_data['urls'])} URLs, {len(index['snapshots'])} snapshots")


if __name__ == "__main__":
    main()
