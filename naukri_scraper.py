import asyncio
import re
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from playwright.async_api import async_playwright, Browser
from playwright_stealth import Stealth

# Single browser instance shared across requests — much faster than launching per request.
_browser: Optional[Browser] = None
_playwright_ctx = None
_stealth_ctx = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _browser, _playwright_ctx, _stealth_ctx
    _stealth_ctx = Stealth().use_async(async_playwright())
    _playwright_ctx = await _stealth_ctx.__aenter__()
    _browser = await _playwright_ctx.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )
    yield
    await _browser.close()
    await _stealth_ctx.__aexit__(None, None, None)


app = FastAPI(title="Naukri Job Scraper", version="1.0.0", lifespan=lifespan)


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[,\s]+", "-", text)
    text = re.sub(r"[^a-z0-9-]", "", text)
    return text.strip("-")


def _build_url(keywords: str, location: str, page: int) -> str:
    kw_slug = _slugify(keywords)
    loc_slug = _slugify(location)
    base = f"https://www.naukri.com/{kw_slug}-jobs-in-{loc_slug}"
    if page > 1:
        base = f"{base}-{page}"
    # sort=f → freshness (latest jobs first)
    return f"{base}?k={keywords}&l={location}&sort=f"


async def _scrape_page(url: str) -> list[dict]:
    ctx = await _browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_selector(".srp-jobtuple-wrapper", timeout=15000)
        except Exception:
            # No results or page blocked
            html = await page.content()
            if "Access Denied" in html:
                raise HTTPException(status_code=502, detail="Naukri blocked the request")
            return []

        jobs = await page.evaluate(
            """
            () => Array.from(document.querySelectorAll('.srp-jobtuple-wrapper')).map(card => {
                const q = (sel) => card.querySelector(sel);
                const text = (sel) => { const el = q(sel); return el ? el.innerText.trim() : ''; };
                const attr = (sel, a) => { const el = q(sel); return el ? el.getAttribute(a) : ''; };
                const titleEl = q('a.title');
                return {
                    title: titleEl ? titleEl.innerText.trim() : '',
                    url: titleEl ? titleEl.getAttribute('href') : '',
                    company: text('a.comp-name'),
                    company_url: attr('a.comp-name', 'href'),
                    experience: text('.expwdth'),
                    location: text('.locWdth'),
                    salary: text('.sal-wrap span') || text('.sal'),
                    description: text('.job-desc'),
                    skills: Array.from(card.querySelectorAll('.tags-gt li')).map(li => li.innerText.trim()),
                    posted: text('.job-post-day'),
                    rating: text('.rating .main-2'),
                    reviews: text('.review'),
                };
            })
            """
        )
        return jobs
    finally:
        await ctx.close()


@app.get("/jobs")
async def get_jobs(
    keywords: str = Query(..., description="Tech stack, e.g. 'python' or 'python fastapi'"),
    location: str = Query(..., description="City, e.g. 'bangalore' or 'remote'"),
    pages: int = Query(1, ge=1, le=10, description="Pages to scrape (~20 jobs each)"),
):
    """Fetch latest jobs from Naukri sorted by freshness."""
    if _browser is None:
        raise HTTPException(status_code=503, detail="Browser not initialized")

    # Scrape pages in parallel
    urls = [_build_url(keywords, location, p) for p in range(1, pages + 1)]
    results = await asyncio.gather(*(_scrape_page(u) for u in urls), return_exceptions=True)

    all_jobs = []
    errors = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            errors.append({"page": i + 1, "error": str(r)})
        else:
            all_jobs.extend(r)

    return {
        "count": len(all_jobs),
        "keywords": keywords,
        "location": location,
        "pages_scraped": pages,
        "errors": errors,
        "jobs": all_jobs,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "browser_ready": _browser is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
