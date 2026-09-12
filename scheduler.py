import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from archiver import crawl_all_urls
from config import CRAWL_INTERVAL_HOURS

logger = logging.getLogger("flock-archiver")
scheduler = BackgroundScheduler()


def run_crawl():
    logger.info("Scheduled crawl starting...")
    loop = asyncio.new_event_loop()
    try:
        results = loop.run_until_complete(crawl_all_urls())
        changed = sum(1 for r in results if r.get("changed"))
        errors = sum(1 for r in results if r.get("error"))
        logger.info(f"Crawl complete: {len(results)} URLs, {changed} changed, {errors} errors")
    except Exception as e:
        logger.error(f"Crawl failed: {e}")
    finally:
        loop.close()


def start_scheduler():
    scheduler.add_job(
        run_crawl,
        trigger=IntervalTrigger(hours=CRAWL_INTERVAL_HOURS),
        id="flock_crawl",
        name="Flock Safety crawl",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started — crawling every {CRAWL_INTERVAL_HOURS} hours")


def stop_scheduler():
    scheduler.shutdown(wait=False)
