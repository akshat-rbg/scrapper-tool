from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import async_playwright, Browser
from playwright_stealth import Stealth

_browser: Optional[Browser] = None
_playwright_ctx = None
_stealth_ctx = None

UA = (
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
  "AppleWebKit/537.36 (KHTML, like Gecko) "
  "Chrome/124.0.0.0 Safari/537.36"
)


@asynccontextmanager
async def lifespan(app):
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


def get_browser() -> Optional[Browser]:
  return _browser
