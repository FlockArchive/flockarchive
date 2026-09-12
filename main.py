import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import httpx
from playwright.async_api import async_playwright

from archiver import capture_url, crawl_all_urls
from config import SEED_URLS, USER_AGENT
from database import (
    init_db, add_url, get_all_urls, get_recent_snapshots,
    get_snapshots_for_url, get_url_by_id, get_snapshot_by_id,
    get_stats, search_urls,
)
from scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("flock-archiver")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    for url in SEED_URLS:
        add_url(url, is_seed=True)
    logger.info(f"Loaded {len(SEED_URLS)} seed URLs")
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Flock Archiver", lifespan=lifespan)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    snapshots = get_recent_snapshots(100)
    stats = get_stats()
    return templates.TemplateResponse(request, "index.html", {
        "snapshots": snapshots,
        **stats,
    })


@app.get("/urls", response_class=HTMLResponse)
async def url_list(request: Request, q: str = Query(default="")):
    q = q.strip()
    urls = search_urls(q) if q else get_all_urls()
    return templates.TemplateResponse(request, "urls.html", {
        "urls": urls,
        "q": q,
    })


@app.post("/submit")
async def submit_url(url: str = Form(...)):
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30.0,
    ) as client, async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        await capture_url(url, client, browser)
        await browser.close()
    return RedirectResponse(url="/", status_code=303)


@app.get("/snapshot/{snapshot_id}", response_class=HTMLResponse)
async def view_snapshot(request: Request, snapshot_id: int):
    snapshot = get_snapshot_by_id(snapshot_id)
    if not snapshot:
        return HTMLResponse("Snapshot not found", status_code=404)

    html_content = ""
    if snapshot["html_path"]:
        html_file = Path(snapshot["html_path"])
        if html_file.exists():
            html_content = html_file.read_text(encoding="utf-8")

    return templates.TemplateResponse(request, "snapshot.html", {
        "snapshot": snapshot,
        "html_content": html_content,
    })


@app.get("/snapshot/{snapshot_id}/raw", response_class=HTMLResponse)
async def raw_snapshot(snapshot_id: int):
    snapshot = get_snapshot_by_id(snapshot_id)
    if not snapshot or not snapshot["html_path"]:
        return HTMLResponse("Not found", status_code=404)
    html_file = Path(snapshot["html_path"])
    if not html_file.exists():
        return HTMLResponse("File missing", status_code=404)
    return HTMLResponse(html_file.read_text(encoding="utf-8"))


@app.get("/screenshot/{snapshot_id}")
async def get_screenshot(snapshot_id: int):
    snapshot = get_snapshot_by_id(snapshot_id)
    if not snapshot or not snapshot["screenshot_path"]:
        return HTMLResponse("Not found", status_code=404)
    screenshot_file = Path(snapshot["screenshot_path"])
    if not screenshot_file.exists():
        return HTMLResponse("File missing", status_code=404)
    return FileResponse(str(screenshot_file), media_type="image/png")


@app.get("/url/{url_id}", response_class=HTMLResponse)
async def url_history(request: Request, url_id: int):
    url_row = get_url_by_id(url_id)
    if not url_row:
        return HTMLResponse("URL not found", status_code=404)
    snapshots = get_snapshots_for_url(url_id)
    return templates.TemplateResponse(request, "url_history.html", {
        "url": url_row,
        "snapshots": snapshots,
    })


@app.post("/crawl-now")
async def trigger_crawl():
    await crawl_all_urls()
    return RedirectResponse(url="/", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8888, reload=True)
