import asyncio
import hashlib
import logging
import re
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, Browser

from config import SNAPSHOTS_DIR, SCREENSHOTS_DIR, USER_AGENT
from database import add_snapshot, get_latest_snapshot, add_url, get_all_urls

logger = logging.getLogger("flock-archiver")

MAX_CONCURRENT = 4


def normalize_html(html: str) -> str:
    html = re.sub(r'nonce="[^"]*"', '', html)
    html = re.sub(r'data-timestamp="[^"]*"', '', html)
    html = re.sub(r'csrf[_-]token[^"]*"[^"]*"', '', html)
    return html


def compute_hash(html: str) -> str:
    normalized = normalize_html(html)
    return hashlib.sha256(normalized.encode()).hexdigest()


async def take_screenshot(url: str, output_path: Path, browser: Browser) -> None:
    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 720},
    )
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path=str(output_path), full_page=True)
    finally:
        await context.close()


async def _fetch_with_browser(url: str, browser: Browser) -> str:
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


async def capture_url(url: str, client: httpx.AsyncClient, browser: Browser | None = None) -> dict:
    url_id = add_url(url)
    result = {"url": url, "url_id": url_id, "error": None, "changed": False}

    try:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403 and browser:
            logger.info(f"Got 403, falling back to browser for {url}")
            try:
                html = await _fetch_with_browser(url, browser)
            except Exception as be:
                logger.error(f"Browser fallback also failed for {url}: {be}")
                result["error"] = str(be)
                add_snapshot(url_id, None, None, "", False, error=str(be))
                return result
        else:
            logger.error(f"Failed to fetch {url}: {e}")
            result["error"] = str(e)
            add_snapshot(url_id, None, None, "", False, error=str(e))
            return result
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        result["error"] = str(e)
        add_snapshot(url_id, None, None, "", False, error=str(e))
        return result

    html_hash = compute_hash(html)
    previous = get_latest_snapshot(url_id)
    changed = previous is not None and previous["html_hash"] != html_hash

    html_file = SNAPSHOTS_DIR / f"pending_{url_id}_{html_hash[:8]}.html"
    html_file.write_text(html, encoding="utf-8")

    screenshot_path = None
    screenshot_file = SCREENSHOTS_DIR / f"pending_{url_id}_{html_hash[:8]}.png"
    if browser:
        try:
            await take_screenshot(url, screenshot_file, browser)
            screenshot_path = str(screenshot_file)
        except Exception as e:
            logger.warning(f"Screenshot failed for {url}: {e}")

    snapshot_id = add_snapshot(
        url_id, str(html_file), screenshot_path, html_hash, changed,
    )

    final_html = SNAPSHOTS_DIR / f"{snapshot_id}.html"
    html_file.rename(final_html)

    final_screenshot = None
    if screenshot_path:
        final_ss = SCREENSHOTS_DIR / f"{snapshot_id}.png"
        screenshot_file.rename(final_ss)
        final_screenshot = str(final_ss)

    from database import get_db
    with get_db() as db:
        db.execute(
            "UPDATE snapshots SET html_path = ?, screenshot_path = ? WHERE id = ?",
            (str(final_html), final_screenshot, snapshot_id),
        )

    result["snapshot_id"] = snapshot_id
    result["changed"] = changed
    result["html_hash"] = html_hash
    return result


async def crawl_all_urls():
    urls = get_all_urls()
    results = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30.0,
    ) as client, async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def _capture(url_row):
            async with semaphore:
                result = await capture_url(url_row["url"], client, browser)
                logger.info(f"Captured {url_row['url']} — changed: {result['changed']}")
                return result

        results = await asyncio.gather(*[_capture(u) for u in urls])
        await browser.close()

    return list(results)
