#!/usr/bin/env python3
"""GitHub Actions crawler — snapshots Flock Safety pages on demand."""

import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright

ARCHIVE_DIR = Path("archive")
INDEX_FILE = Path("archive/index.json")
URLS_FILE = Path("urls.json")
SCREENSHOTS_DIR = Path("archive/screenshots")

ALLOWED_DOMAINS = {"flocksafety.com"}

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MAX_CONCURRENT = 4


def is_flock_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        return any(host == d or host.endswith(f".{d}") for d in ALLOWED_DOMAINS)
    except Exception:
        return False


def normalize_html(html: str) -> str:
    html = re.sub(r'nonce="[^"]*"', '', html)
    html = re.sub(r'data-timestamp="[^"]*"', '', html)
    html = re.sub(r'csrf[_-]token[^"]*"[^"]*"', '', html)
    return html


def compute_hash(html: str) -> str:
    return hashlib.sha256(normalize_html(html).encode()).hexdigest()


def url_to_path(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "unknown"
    path = parsed.path.strip("/").replace("/", "_") or "index"
    return f"{host}/{path}"


def load_index() -> dict:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return {"snapshots": [], "urls": {}}


def save_index(index: dict):
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2))


def add_to_urls_json(url: str):
    data = json.loads(URLS_FILE.read_text())
    existing = [e["url"] for e in data["urls"]]
    if url not in existing:
        data["urls"].append({"url": url, "type": "user"})
        URLS_FILE.write_text(json.dumps(data, indent=2))
        print(f"  Added {url} to urls.json")


async def fetch_with_browser(url: str, browser) -> str:
    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 720},
    )
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="load", timeout=45000)
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    try:
        await page.wait_for_timeout(5000)
        return await page.content()
    finally:
        await context.close()


async def take_screenshot(url: str, output_path: Path, browser) -> bool:
    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 720},
    )
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(output_path), full_page=True)
        return True
    except Exception as e:
        print(f"  Screenshot failed: {e}")
        return False
    finally:
        await context.close()


async def crawl_url(url: str, client: httpx.AsyncClient, browser, index: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    result = {"url": url, "timestamp": now, "error": None, "changed": False}
    url_key = url_to_path(url)

    try:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            print(f"  403 → browser fallback for {url}")
            try:
                html = await fetch_with_browser(url, browser)
            except Exception as be:
                result["error"] = str(be)
                return result
        else:
            result["error"] = f"HTTP {e.response.status_code}"
            return result
    except Exception as e:
        result["error"] = str(e)
        return result

    html_hash = compute_hash(html)
    prev_hash = index["urls"].get(url, {}).get("hash")
    changed = prev_hash is not None and prev_hash != html_hash
    result["changed"] = changed

    snapshot_dir = ARCHIVE_DIR / url_key
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    html_file = snapshot_dir / f"{ts_slug}.html"
    html_file.write_text(html, encoding="utf-8")
    result["html_path"] = str(html_file)
    result["hash"] = html_hash

    ss_file = SCREENSHOTS_DIR / url_key / f"{ts_slug}.png"
    if await take_screenshot(url, ss_file, browser):
        result["screenshot_path"] = str(ss_file)

    index["urls"][url] = {
        "hash": html_hash,
        "last_checked": now,
        "last_changed": now if changed else index["urls"].get(url, {}).get("last_changed", now),
        "path": url_key,
        "type": index["urls"].get(url, {}).get("type", "user"),
    }

    return result


async def snapshot_single(url: str):
    if not url.startswith("http"):
        url = "https://" + url
    if not is_flock_url(url):
        print(f"Rejected: {url} is not a flocksafety.com domain")
        sys.exit(1)

    print(f"Snapshotting {url}")
    index = load_index()
    add_to_urls_json(url)

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30.0,
    ) as client, async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        result = await crawl_url(url, client, browser, index)
        await browser.close()

    index["snapshots"].append({
        "url": result["url"],
        "timestamp": result["timestamp"],
        "html_path": result.get("html_path"),
        "screenshot_path": result.get("screenshot_path"),
        "hash": result.get("hash"),
        "changed": result["changed"],
        "error": result["error"],
    })
    save_index(index)

    status = "CHANGED" if result["changed"] else ("ERROR" if result["error"] else "OK")
    print(f"[{status}] {url}")
    if result.get("error"):
        print(f"  Error: {result['error']}")


async def crawl_all():
    urls_data = json.loads(URLS_FILE.read_text())
    urls = [e["url"] for e in urls_data["urls"] if is_flock_url(e["url"])]
    print(f"Crawling {len(urls)} URLs...")

    index = load_index()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30.0,
    ) as client, async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def _crawl(url):
            async with semaphore:
                print(f"  Fetching {url}")
                result = await crawl_url(url, client, browser, index)
                status = "CHANGED" if result["changed"] else ("ERROR" if result["error"] else "OK")
                print(f"  [{status}] {url}")
                return result

        results = await asyncio.gather(*[_crawl(u) for u in urls])
        await browser.close()

    for r in results:
        index["snapshots"].append({
            "url": r["url"],
            "timestamp": r["timestamp"],
            "html_path": r.get("html_path"),
            "screenshot_path": r.get("screenshot_path"),
            "hash": r.get("hash"),
            "changed": r["changed"],
            "error": r["error"],
        })

    save_index(index)

    changed = sum(1 for r in results if r["changed"])
    errors = sum(1 for r in results if r["error"])
    print(f"\nDone: {len(results)} crawled, {changed} changed, {errors} errors")


def main():
    parser = argparse.ArgumentParser(description="Flock Safety archiver")
    parser.add_argument("--url", help="Snapshot a single URL")
    args = parser.parse_args()

    if args.url:
        asyncio.run(snapshot_single(args.url))
    else:
        asyncio.run(crawl_all())


if __name__ == "__main__":
    main()
