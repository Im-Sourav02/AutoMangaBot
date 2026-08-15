"""
TheBlankAPI — Scraper for theblank.net (and beta/redesign domains).

CF Bypass: Camoufox (Firefox anti-detect browser) extracts cf_clearance cookie
once per session, then all subsequent requests use fast curl_cffi with the
injected cookie. No paid CAPTCHA services required.

Chapter ID format: "{manga_slug}|{chapter_slug}"
"""

import asyncio
import logging
import re
import time
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from Scrapers.base.madara_base import (
    _cffi_get, _cffi_post, _get_clearance, _camoufox_bypass,
    _sync_camoufox_bypass, _clearance_cache, _is_cf_block,
    _win_policy, UA,
)

logger = logging.getLogger(__name__)

_DOMAINS = [
    "https://theblank.net",
    "https://beta.theblank.net",
]


# ── CF clearance helper ────────────────────────────────────────────────────────

async def _theblank_fetch(url: str) -> Optional[str]:
    """
    4-tier fetch cascade for TheBlank's strict CF protection:
      1. curl_cffi (fast)
      2. curl_cffi + cached cf_clearance
      3. Camoufox clearance extraction → retry curl_cffi
      4. Direct Camoufox page (last resort)
    """
    base = _DOMAINS[0]
    domain = urlparse(base).netloc

    # Tier 1
    html = await _cffi_get(url)
    if html:
        return html

    # Tier 2: cached clearance
    cached = _clearance_cache.get(domain)
    if cached:
        cf_cl, ua, exp = cached
        if time.time() < exp:
            html = await _cffi_get(url, cf_clearance=cf_cl, ua_override=ua)
            if html:
                return html

    # Tier 3: fresh Camoufox clearance
    logger.info(f"TheBlank: getting CF clearance via Camoufox for {url}")
    cf_cl, ua = await _get_clearance(base)
    if cf_cl:
        html = await _cffi_get(url, cf_clearance=cf_cl, ua_override=ua)
        if html:
            return html

    # Tier 4: direct Camoufox
    logger.info(f"TheBlank: direct Camoufox load for {url}")
    loop = asyncio.get_event_loop()
    _, _, html = await loop.run_in_executor(None, _sync_camoufox_bypass, url)
    return html


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ── Chapter image extraction via Camoufox ─────────────────────────────────────

def _sync_extract_images(url: str, cf_clearance: str, ua: str) -> List[str]:
    """
    Blocking: launch Camoufox, inject cf_clearance cookie, navigate to the
    chapter reader, then extract image URLs via JS evaluation.
    Runs in executor thread — never blocks the Pyrogram event loop.
    """
    _win_policy()
    return asyncio.run(_async_extract_images(url, cf_clearance, ua))


async def _async_extract_images(url: str, cf_clearance: str, ua: str) -> List[str]:
    """
    Async: open the reader page in Camoufox with cf_clearance injected,
    wait for the manga images to load, then extract all image URLs.
    """
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError:
        logger.error("camoufox not installed. Run: pip install camoufox && python -m camoufox fetch")
        return []

    async with AsyncCamoufox(headless=True) as browser:
        ctx = browser  # AsyncCamoufox IS the context
        page = await browser.new_page()
        try:
            # Inject the cf_clearance cookie before navigating
            domain = urlparse(url).netloc
            if cf_clearance:
                await page.context.add_cookies([{
                    "name": "cf_clearance",
                    "value": cf_clearance,
                    "domain": domain,
                    "path": "/",
                }])

            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # Wait for CF to clear (Camoufox should handle it natively)
            iframe_clicked = False
            for _ in range(10):
                title = (await page.title()).lower()
                body  = await page.evaluate("() => document.body?.innerText?.toLowerCase() || ''")
                is_cf = (
                    "just a moment" in title or "cloudflare" in title
                    or "security verification" in body or "verify you are human" in body
                )
                if not is_cf:
                    break
                if not iframe_clicked and ("verify you are human" in body or "security verification" in body):
                    iframe_clicked = True
                    try:
                        for frame in page.frames:
                            if "challenges.cloudflare.com" in (frame.url or ""):
                                await frame.evaluate(
                                    "() => { const cb = document.querySelector('input[type=checkbox]'); if (cb) cb.click(); }"
                                )
                                break
                        cf_frame = page.frame_locator("iframe[src*='challenges.cloudflare.com']")
                        cb = cf_frame.locator("input[type='checkbox']")
                        if await cb.count() > 0:
                            await cb.click(delay=120)
                    except Exception:
                        pass
                await asyncio.sleep(3)

            # Wait for images to appear in the reader
            try:
                await page.wait_for_selector(
                    ".reading-content img, #readerarea img, .chapter-content img",
                    timeout=15000
                )
            except Exception:
                pass

            # Check VIP / paywall
            body_text = await page.evaluate("() => document.body?.innerText || ''")
            if any(k in body_text.lower() for k in ["vip chapter", "premium chapter", "subscribe to read", "login to read"]):
                logger.warning(f"TheBlank: VIP/premium chapter, skipping {url}")
                return []

            # Extract image URLs via JS
            images = await page.evaluate("""
            () => {
                const selectors = [
                    '.reading-content img',
                    '#readerarea img',
                    '.chapter-content img',
                    'div.text-left img',
                    '.page-break img',
                ];
                const seen = new Set();
                const imgs = [];
                for (const sel of selectors) {
                    document.querySelectorAll(sel).forEach(img => {
                        const src = img.dataset.src || img.dataset.lazySrc || img.src || '';
                        if (src.startsWith('http') && !seen.has(src)) {
                            seen.add(src);
                            imgs.push(src);
                        }
                    });
                    if (imgs.length > 0) break;
                }
                return imgs;
            }
            """)

            # Update the clearance cache with the freshly-obtained cookie
            fresh_cookies = await page.context.cookies()
            new_cf_cl = next((c["value"] for c in fresh_cookies if c["name"] == "cf_clearance"), "")
            if new_cf_cl:
                _clearance_cache[domain] = (new_cf_cl, ua, time.time() + 1500)

            logger.info(f"TheBlank: extracted {len(images)} images from {url}")
            return images

        except Exception as e:
            logger.error(f"TheBlank _async_extract_images {url}: {e}")
            return []
        finally:
            await page.close()


# ── TheBlankAPI class ──────────────────────────────────────────────────────────

class TheBlankAPI:
    """
    Scraper for theblank.net.

    - Search / manga info / chapters: curl_cffi + cf_clearance cookie (fast)
    - Chapter images: Camoufox with injected cf_clearance (needs JS reader)
    """

    def __init__(self, Config=None):
        self.Config = Config
        self.base_url = _DOMAINS[0]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    # ── helpers ────────────────────────────────────────────────────────────────

    def _slug_from_url(self, url: str) -> Optional[str]:
        url = url.rstrip("/")
        for path in ("manga", "series", "manhwa", "webtoon"):
            m = re.search(rf"/{re.escape(path)}/([^/?#]+)$", url)
            if m:
                return m.group(1)
        m = re.search(r"/([^/?#]+)$", url)
        return m.group(1) if m else None

    def _chapter_slug_from_url(self, url: str) -> Optional[str]:
        url = url.rstrip("/")
        for path in ("manga", "series", "manhwa", "webtoon"):
            m = re.search(rf"/{re.escape(path)}/[^/]+/([^/?#]+)$", url)
            if m:
                return m.group(1)
        m = re.search(r"/([^/?#]+)$", url)
        return m.group(1) if m else None

    def _get_clearance_sync(self) -> Tuple[str, str]:
        """Return cached clearance or empty strings."""
        domain = urlparse(self.base_url).netloc
        cached = _clearance_cache.get(domain)
        if cached:
            cf_cl, ua, exp = cached
            if time.time() < exp:
                return cf_cl, ua
        return "", ""

    # ── search ─────────────────────────────────────────────────────────────────

    async def search_manga(self, query: str, limit: int = 10) -> List[Dict]:
        try:
            url = f"{self.base_url}/?s={quote_plus(query)}&post_type=wp-manga"
            html = await _theblank_fetch(url)
            if not html:
                return []
            soup = _soup(html)
            results = []
            for a in soup.select(
                ".post-title h3 a, .post-title h5 a, article .post-title a, .c-image-hover a"
            )[:limit * 2]:
                href = a.get("href", "")
                title = a.get_text(strip=True)
                if not href or not title:
                    continue
                slug = self._slug_from_url(href)
                if slug and not any(r["id"] == slug for r in results):
                    results.append({"id": slug, "title": title})
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            logger.error(f"TheBlank search_manga: {e}")
            return []

    # ── manga info ─────────────────────────────────────────────────────────────

    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/manga/{manga_id}/"
            html = await _theblank_fetch(url)
            if not html:
                return None
            soup = _soup(html)
            title_el = (soup.select_one(".post-title h1") or
                        soup.select_one(".manga-title") or soup.select_one("h1"))
            title = title_el.get_text(strip=True) if title_el else manga_id
            desc_el = soup.select_one(".summary__content, .description-summary, .manga-excerpt")
            desc = desc_el.get_text(strip=True)[:500] if desc_el else ""
            cover_el = soup.select_one(".summary_image img, .manga-thumbnail img, .tab-summary img")
            cover = ""
            if cover_el:
                cover = (cover_el.get("data-src") or cover_el.get("data-lazy-src")
                         or cover_el.get("src") or "")
            return {"id": manga_id, "title": title, "description": desc, "cover": cover}
        except Exception as e:
            logger.error(f"TheBlank get_manga_info: {e}")
            return None

    # ── chapter list ───────────────────────────────────────────────────────────

    async def get_manga_chapters(self, manga_id: str, limit: int = 500,
                                  offset: int = 0, languages=None) -> List[Dict]:
        try:
            url = f"{self.base_url}/manga/{manga_id}/"
            html = await _theblank_fetch(url)
            if not html:
                return []
            soup = _soup(html)
            rows = soup.select(".wp-manga-chapter, li.wp-manga-chapter")
            results = []
            for row in rows:
                a = row.select_one("a")
                if not a:
                    continue
                href = a.get("href", "")
                ch_slug = self._chapter_slug_from_url(href)
                if not ch_slug:
                    continue
                m = re.search(r"chapter[_-]?([\d]+(?:[.\-]\d+)?)", ch_slug, re.I)
                chapter_num = m.group(1).replace("-", ".") if m else ch_slug
                results.append({
                    "id": f"{manga_id}|{ch_slug}",
                    "chapter": chapter_num,
                    "title": f"Chapter {chapter_num}",
                    "language": "en",
                    "volume": "",
                })
            results.reverse()
            return results[offset: offset + limit]
        except Exception as e:
            logger.error(f"TheBlank get_manga_chapters: {e}")
            return []

    async def get_latest_chapters(self, manga_id: str, limit: int = 20, offset: int = 0):
        return await self.get_manga_chapters(manga_id, limit=limit, offset=offset)

    # ── chapter info ───────────────────────────────────────────────────────────

    async def get_chapter_info(self, chapter_id: str) -> Optional[Dict]:
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
            m = re.search(r"chapter[_-]?([\d]+(?:[.\-]\d+)?)", ch_slug, re.I)
            chapter_num = m.group(1).replace("-", ".") if m else ch_slug
            info = await self.get_manga_info(manga_slug)
            return {
                "id": chapter_id,
                "chapter": chapter_num,
                "title": f"Chapter {chapter_num}",
                "manga_title": (info or {}).get("title", ""),
            }
        except Exception as e:
            logger.error(f"TheBlank get_chapter_info: {e}")
            return None

    # ── chapter images ─────────────────────────────────────────────────────────

    async def get_chapter_images(self, chapter_id: str) -> List[str]:
        """
        Extract reader images using Camoufox with cf_clearance injected.
        Runs in executor → never blocks the Pyrogram event loop.
        """
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
            url = f"{self.base_url}/manga/{manga_slug}/{ch_slug}/"

            # Get cached clearance (avoid Camoufox re-login when already unlocked)
            cf_cl, ua = self._get_clearance_sync()

            loop = asyncio.get_event_loop()
            images = await loop.run_in_executor(
                None, _sync_extract_images, url, cf_cl, ua
            )
            return images
        except Exception as e:
            logger.error(f"TheBlank get_chapter_images: {e}")
            return []
