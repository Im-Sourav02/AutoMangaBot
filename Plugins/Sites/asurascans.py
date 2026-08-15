"""
AsuraScansAPI — Scraper for asuracomic.net
Strategy (layered, fastest-first):
  1. curl_cffi → parse chapter page HTML for a JSON blob embedded in a
     <script> tag (Next.js __NEXT_DATA__ or window.__data__). This avoids
     Playwright entirely when the CDN URLs are present in the HTML.
  2. If no images found in HTML, fall back to Playwright (JS render).

CDN headers: all image download requests MUST send
  Referer: https://asuracomic.net/
  User-Agent: <browser UA>
to avoid 403s from the cdn.asurascans.com CDN.
"""
import asyncio
import json
import logging
import re
from typing import List, Dict, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://asuracomic.net"
CDN_HOST = "cdn.asurascans.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
# These headers must accompany every image download request to avoid CDN 403s
CDN_HEADERS = {
    "User-Agent": UA,
    "Referer":    BASE_URL + "/",
    "Origin":     BASE_URL,
}


async def _cffi_get(url: str, extra_headers: dict = None) -> Optional[str]:
    """Fetch a page via curl_cffi (Chrome TLS fingerprint, bypasses basic CF)."""
    try:
        from curl_cffi.requests import AsyncSession
        headers = {"User-Agent": UA, "Referer": BASE_URL + "/"}
        if extra_headers:
            headers.update(extra_headers)
        async with AsyncSession(impersonate="chrome124") as s:
            r = await s.get(url, headers=headers, timeout=25)
            if r.status_code < 400 and "just a moment" not in r.text.lower():
                return r.text
    except Exception as e:
        logger.debug(f"Asura _cffi_get {url}: {e}")
    return None


def _extract_images_from_html(html: str) -> List[str]:
    """
    Try to pull image URLs directly out of the page HTML without JS execution.
    Asura embeds chapter data in either:
      a) window.__data__ = {...}  script tag
      b) __NEXT_DATA__           script tag
      c) <img> tags inside .reader-area / #readerarea
    Returns a de-duped list of CDN image URLs.
    """
    images: List[str] = []

    # --- Strategy A: window.__data__ / inline JSON blobs ---
    for pattern in [
        r'window\.__data__\s*=\s*(\{.*?\});',
        r'"images"\s*:\s*(\[.*?\])',
        r'"pages"\s*:\s*(\[.*?\])',
        r'"chapter_images"\s*:\s*(\[.*?\])',
    ]:
        for m in re.finditer(pattern, html, re.S):
            try:
                blob = json.loads(m.group(1))
                if isinstance(blob, list):
                    for item in blob:
                        url = item if isinstance(item, str) else (
                            item.get("url") or item.get("src") or item.get("image") or "")
                        if url and ("asurascans" in url or url.startswith("http")):
                            images.append(url)
                elif isinstance(blob, dict):
                    for v in blob.values():
                        if isinstance(v, str) and ("asurascans" in v or v.startswith("http")):
                            images.append(v)
            except Exception:
                continue
        if images:
            break

    # --- Strategy B: __NEXT_DATA__ ---
    if not images:
        nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if nd:
            try:
                data = json.loads(nd.group(1))
                raw = json.dumps(data)
                # Pull every URL that looks like a chapter image
                for url in re.findall(r'https://[^\s"\'\\]+(?:\.jpg|\.webp|\.png|\.jpeg)', raw):
                    if CDN_HOST in url or "asura" in url.lower():
                        images.append(url)
            except Exception:
                pass

    # --- Strategy C: raw img tags in the reader area ---
    if not images:
        soup = BeautifulSoup(html, "lxml")
        for sel in [
            ".reader-area img", "#readerarea img",
            "div[class*='reader'] img", ".chapter-image img",
        ]:
            for img in soup.select(sel):
                src = (img.get("data-src") or img.get("src") or "").strip()
                if src.startswith("http"):
                    images.append(src)
            if images:
                break

    # De-duplicate preserving order
    seen: set = set()
    out: List[str] = []
    for url in images:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


async def _pw_get_images_asura(url: str) -> List[str]:
    """Playwright fallback: render the page and grab CDN image URLs."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled"],
            )
            ctx = await browser.new_context(
                user_agent=UA,
                viewport={"width": 1280, "height": 720},
                extra_http_headers={"Referer": BASE_URL + "/"},
            )
            page = await ctx.new_page()
            await page.goto(url, wait_until="networkidle", timeout=45000)
            # Wait for CF challenge if present
            for _ in range(8):
                title = (await page.title()).lower()
                if "just a moment" not in title and "cloudflare" not in title:
                    break
                await asyncio.sleep(3)
            # Wait for first image
            try:
                await page.wait_for_selector("img[src*='asurascans']", timeout=15000)
            except Exception:
                await asyncio.sleep(5)
            images = await page.evaluate("""
            () => {
                const imgs = [...document.querySelectorAll('img')];
                return imgs
                    .map(i => i.getAttribute('data-src') || i.getAttribute('data-lazy-src') || i.src || '')
                    .filter(s => s.startsWith('http') &&
                                 (s.includes('asurascans') || s.includes('asuracomic') || s.includes('.webp') || s.includes('.jpg'))
                                 && !s.includes('logo') && !s.includes('favicon'));
            }
            """)
            await browser.close()
            return images or []
    except Exception as e:
        logger.error(f"Asura Playwright fallback failed: {e}")
        return []


class AsuraScansAPI:
    """
    Asura Scans scraper with a layered image-extraction strategy:
    HTML script-tag extraction → Playwright fallback.
    """

    def __init__(self, Config):
        self.Config = Config
        # Expose CDN headers so Downloader can use them for image fetching
        self.download_headers = CDN_HEADERS

    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass

    # ------------------------------------------------------------------ #
    async def search_manga(self, query: str, limit: int = 10) -> List[Dict]:
        try:
            url = f"{BASE_URL}/series?name={quote_plus(query)}"
            html = await _cffi_get(url)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            results: List[Dict] = []
            for card in soup.select(
                "div[class*='grid'] a[href*='/series/'], "
                ".listupd a[href*='/series/'], "
                "a[href*='/series/']"
            )[:limit * 2]:
                href = card.get("href", "")
                title_el = card.select_one("span[class*='title'], h2, h3, span") or card
                title = title_el.get_text(strip=True)
                if not href or not title:
                    continue
                m = re.search(r"/series/([^/?#]+)", href)
                if m:
                    slug = m.group(1)
                    if not any(r["id"] == slug for r in results):
                        results.append({"id": slug, "title": title})
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            logger.error(f"AsuraScans search_manga: {e}")
            return []

    # ------------------------------------------------------------------ #
    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        try:
            url = f"{BASE_URL}/series/{manga_id}"
            html = await _cffi_get(url)
            if not html:
                return None
            soup = BeautifulSoup(html, "lxml")
            title_el = soup.select_one("h1, .entry-title")
            title = title_el.get_text(strip=True) if title_el else manga_id
            desc_el = soup.select_one("div[class*='desc'], p[class*='description']")
            desc = desc_el.get_text(strip=True)[:500] if desc_el else ""
            cover_el = soup.select_one("img[class*='cover'], .thumb img, img[alt*='cover']")
            cover = (cover_el.get("src") or cover_el.get("data-src") or "") if cover_el else ""
            return {"id": manga_id, "title": title, "description": desc, "cover": cover}
        except Exception as e:
            logger.error(f"AsuraScans get_manga_info: {e}")
            return None

    # ------------------------------------------------------------------ #
    async def get_manga_chapters(self, manga_id: str, limit: int = 500,
                                  offset: int = 0, languages=None) -> List[Dict]:
        try:
            url = f"{BASE_URL}/series/{manga_id}"
            html = await _cffi_get(url)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            results: List[Dict] = []
            for a in soup.select("div[class*='chapter'] a, .eplister a, ul[class*='chapter'] a"):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                m = re.search(r"/chapter/([^/?#]+)", href)
                if not m:
                    continue
                ch_slug = m.group(1)
                num_match = re.search(r"([\d]+(?:[.\-]\d+)?)", text or ch_slug)
                chapter_num = num_match.group(1) if num_match else ch_slug
                results.append({
                    "id":       f"{manga_id}|{ch_slug}",
                    "chapter":  chapter_num,
                    "title":    text or f"Chapter {chapter_num}",
                    "language": "en",
                    "volume":   "",
                })
            results.reverse()
            return results[offset: offset + limit]
        except Exception as e:
            logger.error(f"AsuraScans get_manga_chapters: {e}")
            return []

    async def get_latest_chapters(self, manga_id: str, limit: int = 20,
                                   offset: int = 0) -> List[Dict]:
        return await self.get_manga_chapters(manga_id, limit=limit, offset=offset)

    # ------------------------------------------------------------------ #
    async def get_chapter_info(self, chapter_id: str) -> Optional[Dict]:
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
            num_match = re.search(r"([\d]+(?:[.\-]\d+)?)", ch_slug)
            chapter_num = num_match.group(1).replace("-", ".") if num_match else ch_slug
            info = await self.get_manga_info(manga_slug)
            return {
                "id":          chapter_id,
                "chapter":     chapter_num,
                "title":       f"Chapter {chapter_num}",
                "manga_title": (info or {}).get("title", manga_slug),
            }
        except Exception as e:
            logger.error(f"AsuraScans get_chapter_info: {e}")
            return None

    # ------------------------------------------------------------------ #
    async def get_chapter_images(self, chapter_id: str) -> List[str]:
        """
        Layered extraction:
          1. curl_cffi HTML + script-tag JSON parsing (fast, no browser)
          2. Playwright (JS render) if step 1 yields nothing
        All returned URLs are from cdn.asurascans.com and require CDN_HEADERS
        to download successfully (the Downloader class should use them).
        """
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
            url = f"{BASE_URL}/series/{manga_slug}/chapter/{ch_slug}"

            # --- Step 1: HTML extraction ---
            html = await _cffi_get(url)
            if html:
                images = _extract_images_from_html(html)
                if images:
                    logger.info(f"AsuraScans: extracted {len(images)} images from HTML (no Playwright)")
                    return images

            # --- Step 2: Playwright fallback ---
            logger.info(f"AsuraScans: HTML extraction yielded nothing, using Playwright for {url}")
            loop = asyncio.get_event_loop()
            images = await loop.run_in_executor(None, asyncio.run, _pw_get_images_asura(url))
            if images:
                return images

            logger.warning(f"AsuraScans: no images found for {chapter_id}")
            return []
        except Exception as e:
            logger.error(f"AsuraScans get_chapter_images: {e}")
            return []
