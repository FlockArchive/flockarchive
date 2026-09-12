import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
DB_PATH = DATA_DIR / "flock_archive.db"

SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

CRAWL_INTERVAL_HOURS = int(os.environ.get("CRAWL_INTERVAL_HOURS", "6"))

SEED_URLS = [
    # Core pages
    "https://www.flocksafety.com/",
    "https://www.flocksafety.com/about",
    "https://www.flocksafety.com/pricing",
    "https://www.flocksafety.com/contact",
    "https://www.flocksafety.com/what-is-flock",
    "https://www.flocksafety.com/faq",
    # Products
    "https://www.flocksafety.com/products",
    "https://www.flocksafety.com/products/license-plate-readers",
    "https://www.flocksafety.com/products/lpr-cameras",
    "https://www.flocksafety.com/products/video-cameras",
    "https://www.flocksafety.com/products/gunshot-detection",
    "https://www.flocksafety.com/products/mobile-security-trailer",
    "https://www.flocksafety.com/products/flock-os",
    "https://www.flocksafety.com/products/flock911",
    "https://www.flocksafety.com/products/flock-safety-platform",
    "https://www.flocksafety.com/products/flock-dfr",
    "https://www.flocksafety.com/products/flock-aerodome-drone-as-automated-security",
    "https://www.flocksafety.com/products/national-lpr-network",
    "https://www.flocksafety.com/products/investigations-manager",
    "https://www.flocksafety.com/products/flock-freeform",
    "https://www.flocksafety.com/products/freeform-search",
    # Trust & legal (high-value for FOIA/oversight work)
    "https://www.flocksafety.com/trust",
    "https://www.flocksafety.com/trust/data-privacy",
    "https://www.flocksafety.com/trust/rights-safeguards",
    "https://www.flocksafety.com/trust/law-enforcement-access",
    "https://www.flocksafety.com/trust/myths-facts",
    "https://www.flocksafety.com/trust/compliance-tools",
    "https://www.flocksafety.com/legal",
    "https://www.flocksafety.com/legal/terms-and-conditions",
    "https://www.flocksafety.com/legal/terms-of-service",
    "https://www.flocksafety.com/legal/privacy-policy",
    "https://www.flocksafety.com/legal/privacy-notice",
    "https://www.flocksafety.com/legal/lpr-policy",
    "https://www.flocksafety.com/legal/flock-evidence-policy",
    "https://www.flocksafety.com/legal/data-ownership",
    "https://www.flocksafety.com/legal/vulnerability-disclosure-policy",
    # Content
    "https://www.flocksafety.com/blog",
    "https://www.flocksafety.com/press-center",
    "https://www.flocksafety.com/customers",
    "https://www.flocksafety.com/resources",
    # Subdomains
    "https://transparency.flocksafety.com/",
    "https://status.flocksafety.com/",
    "https://help.flocksafety.com/",
    "https://docs.flocksafety.com/",
    "https://security.flocksafety.com/",
    "https://trust.flocksafety.com/",
]

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
