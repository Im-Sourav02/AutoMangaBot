"""
MangaStreamBaseAPI — Generic base for MangaStream / ReaperScans-style sites.

These sites (Asura Scans, Vortex Scans) typically use a Next.js or custom
React reader instead of Madara. Images are loaded via JS so Playwright is
required for chapter image extraction.

Subclass and set:
    base_url = "https://asuracomic.net"
"""

import asyncio
import logging
import re
import sys
from typing import List, Dict, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _win_policy():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def _sync_run(coro_factory, *args):
    _win_policy()
    return asyncio.run(coro_factory(*args))


async def _make_pw_page(pw, headless=True):
    try:
        from playwright_stealth.stealth import Stealth
        _stealth = Stealth()
    except Exception:
        _stealth = None
    browser = await pw.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox", 
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--single-process",
            "--no-zygote",
            "--disable-background-networking",
            "--disable-blink-features=AutomationControlled"
        ],
    )
    ctx = await browser.new_context(
        user_agent=UA, viewport={"width": 1280, "height": 720},
        locale="en-US", java_script_enabled=True, ignore_https_errors=True,
    )
    page = await ctx.new_page()
    if _stealth:
        await _stealth.apply_stealth_async(page)
    return browser, page


async def _pw_get_html(url: str) -> Optional[str]:
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser, page = await _make_pw_page(pw)
        try:
            await page.goto(url, wait_until="networkidle", timeout=45000)
            for _ in range(6):
                title = (await page.title()).lower()
                if "just a moment" not in title and "cloudflare" not in title:
                    break
                await asyncio.sleep(3)
            return await page.content()
        except Exception as e:
            logger.warning(f"_pw_get_html {url}: {e}")
            return None
        finally:
            await browser.close()


async def _pw_get_images(url: str, image_selector: str) -> List[str]:
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser, page = await _make_pw_page(pw)
        try:
            await page.goto(url, wait_until="networkidle", timeout=45000)
            for _ in range(6):
                title = (await page.title()).lower()
                if "just a moment" not in title and "cloudflare" not in title:
                    break
                await asyncio.sleep(3)
            # Wait for images to load
            try:
                await page.wait_for_selector(image_selector, timeout=15000)
            except Exception:
                await asyncio.sleep(5)
            images = await page.evaluate(f"""
            () => {{
                const imgs = [...document.querySelectorAll({repr(image_selector)})];
                return imgs
                    .map(img => (img.getAttribute('data-src') || img.getAttribute('data-lazy-src') || img.src || '').trim())
                    .filter(src => src.startsWith('http'));
            }}
            """)
            return images
        except Exception as e:
            logger.warning(f"_pw_get_images {url}: {e}")
            return []
        finally:
            await browser.close()


class MangaStreamBaseAPI:
    """
    Generic base for MangaStream / ReaperScans / Asura-style sites.
    Uses curl_cffi for metadata and Playwright for chapter image extraction.
    """

    base_url: str = ""

    # Override these selectors per site if needed
    SEARCH_SEL   = ".bsx a, .listupd .bs a, .utao .uta a"
    CHAPTER_SEL  = ".eplister li a, #chapterlist li a, .clstyle li a"
    IMAGE_SEL    = ".reader-area img, #readerarea img, .reading-content img"
    TITLE_SEL    = "h1.entry-title, .entry-title, h1"
    DESC_SEL     = ".entry-content[itemprop='description'], .entry-content p"
    COVER_SEL    = ".thumb img, .thumbook img, .infomanga img"

    def __init__(self, Config):
        self.Config = Config

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def _fetch(self, url: str) -> Optional[str]:
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as s:
                r = await s.get(url, headers={"User-Agent": UA}, timeout=20)
                if r.status_code < 400 and "just a moment" not in r.text.lower():
                    return r.text
        except Exception:
            pass
        # Playwright fallback
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_run, _pw_get_html, url)

    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    async def search_manga(self, query: str, limit: int = 10) -> List[Dict]:
        try:
            url = f"{self.base_url}/?s={quote_plus(query)}"
            html = await self._fetch(url)
            if not html:
                return []
            soup = self._soup(html)
            results = []
            for a in soup.select(self.SEARCH_SEL)[:limit * 2]:
                href = a.get("href", "")
                title_el = a.select_one(".tt, .bigor .tt, h2, h3") or a
                title = title_el.get_text(strip=True)
                if not href or not title:
                    continue
                slug = href.rstrip("/").split("/")[-1]
                if slug and not any(r["id"] == slug for r in results):
                    results.append({"id": slug, "title": title})
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            logger.error(f"{self.__class__.__name__} search_manga: {e}")
            return []

    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/manga/{manga_id}/"
            html = await self._fetch(url)
            if not html:
                return None
            soup = self._soup(html)
            title_el = soup.select_one(self.TITLE_SEL)
            title = title_el.get_text(strip=True) if title_el else manga_id
            desc_el = soup.select_one(self.DESC_SEL)
            desc = desc_el.get_text(strip=True)[:500] if desc_el else ""
            cover_el = soup.select_one(self.COVER_SEL)
            cover = ""
            if cover_el:
                cover = cover_el.get("data-src") or cover_el.get("src") or ""
            return {"id": manga_id, "title": title, "description": desc, "cover": cover}
        except Exception as e:
            logger.error(f"{self.__class__.__name__} get_manga_info: {e}")
            return None

    async def get_manga_chapters(self, manga_id: str, limit: int = 500,
                                  offset: int = 0, languages=None) -> List[Dict]:
        try:
            url = f"{self.base_url}/manga/{manga_id}/"
            html = await self._fetch(url)
            if not html:
                return []
            soup = self._soup(html)
            rows = soup.select(self.CHAPTER_SEL)
            results = []
            for row in rows:
                href = row.get("href", "")
                text = row.get_text(strip=True)
                ch_slug = href.rstrip("/").split("/")[-1]
                num_match = re.search(r"([\d]+(?:[.\-]\d+)?)", text)
                chapter_num = num_match.group(1) if num_match else ch_slug
                results.append({
                    "id": f"{manga_id}|{ch_slug}",
                    "chapter": chapter_num,
                    "title": text,
                    "language": "en",
                    "volume": "",
                })
            results.reverse()
            return results[offset: offset + limit]
        except Exception as e:
            logger.error(f"{self.__class__.__name__} get_manga_chapters: {e}")
            return []

    async def get_latest_chapters(self, manga_id: str, limit: int = 20,
                                   offset: int = 0) -> List[Dict]:
        return await self.get_manga_chapters(manga_id, limit=limit, offset=offset)

    async def get_chapter_info(self, chapter_id: str) -> Optional[Dict]:
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
            num_match = re.search(r"([\d]+(?:[.\-]\d+)?)", ch_slug)
            chapter_num = num_match.group(1).replace("-", ".") if num_match else ch_slug
            info = await self.get_manga_info(manga_slug)
            return {
                "id": chapter_id, "chapter": chapter_num,
                "title": f"Chapter {chapter_num}",
                "manga_title": (info or {}).get("title", ""),
            }
        except Exception as e:
            logger.error(f"{self.__class__.__name__} get_chapter_info: {e}")
            return None

    async def get_chapter_images(self, chapter_id: str) -> List[str]:
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
            url = f"{self.base_url}/{manga_slug}/{ch_slug}/"
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, _sync_run, _pw_get_images, url, self.IMAGE_SEL
            )
        except Exception as e:
            logger.error(f"{self.__class__.__name__} get_chapter_images: {e}")
            return []
