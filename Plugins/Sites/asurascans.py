"""
AsuraScansAPI -- Scraper for asuracomic.net.
Uses BeautifulSoup for metadata + Playwright for chapter images (JS reader).
"""
import re
import logging
from typing import List, Dict, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from Plugins.Sites.Base.mangastream_base import (
    MangaStreamBaseAPI, _sync_run, _pw_get_images
)

logger = logging.getLogger(__name__)

BASE_URL = "https://asuracomic.net"


class AsuraScansAPI(MangaStreamBaseAPI):
    base_url = BASE_URL

    SEARCH_SEL = ".grid.grid-cols-2 a, .listupd a, div[class*='grid'] a"
    CHAPTER_SEL = "div[class*='chapters'] a, .eplister li a, ul[class*='chapter'] li a"
    IMAGE_SEL   = ".chapter-image img, .reader-container img, #readerarea img, div[class*='reader'] img"
    TITLE_SEL   = "h1, .entry-title"
    COVER_SEL   = "img[class*='cover'], .thumb img, img[alt*='cover']"

    async def search_manga(self, query: str, limit: int = 10) -> List[Dict]:
        try:
            url = f"{BASE_URL}/series?name={quote_plus(query)}"
            html = await self._fetch(url)
            if not html: return []
            soup = BeautifulSoup(html, "lxml")
            results = []
            for card in soup.select("div[class*='grid'] a[href*='/series/'], .listupd a[href*='/series/']")[:limit * 2]:
                href = card.get("href", "")
                title_el = card.select_one("span[class*='title'], h2, h3, span") or card
                title = title_el.get_text(strip=True)
                if not href or not title: continue
                m = re.search(r"/series/([^/?#]+)", href)
                if m:
                    slug = m.group(1)
                    if not any(r["id"] == slug for r in results):
                        results.append({"id": slug, "title": title})
                if len(results) >= limit: break
            return results
        except Exception as e:
            logger.error(f"AsuraScans search_manga: {e}")
            return []

    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        try:
            url = f"{BASE_URL}/series/{manga_id}"
            html = await self._fetch(url)
            if not html: return None
            soup = BeautifulSoup(html, "lxml")
            title_el = soup.select_one("h1, .entry-title")
            title = title_el.get_text(strip=True) if title_el else manga_id
            desc_el = soup.select_one("div[class*='desc'], p[class*='description']")
            desc = desc_el.get_text(strip=True)[:500] if desc_el else ""
            cover_el = soup.select_one(self.COVER_SEL)
            cover = (cover_el.get("src") or cover_el.get("data-src") or "") if cover_el else ""
            return {"id": manga_id, "title": title, "description": desc, "cover": cover}
        except Exception as e:
            logger.error(f"AsuraScans get_manga_info: {e}")
            return None

    async def get_manga_chapters(self, manga_id: str, limit: int = 500,
                                  offset: int = 0, languages=None) -> List[Dict]:
        try:
            url = f"{BASE_URL}/series/{manga_id}"
            html = await self._fetch(url)
            if not html: return []
            soup = BeautifulSoup(html, "lxml")
            results = []
            for a in soup.select("div[class*='chapter'] a, .eplister a, ul[class*='chapter'] a"):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                m = re.search(r"/chapter/([^/?#]+)", href)
                if not m: continue
                ch_slug = m.group(1)
                num_match = re.search(r"([\d]+(?:[.\-]\d+)?)", text or ch_slug)
                chapter_num = num_match.group(1) if num_match else ch_slug
                results.append({
                    "id": f"{manga_id}|{ch_slug}",
                    "chapter": chapter_num,
                    "title": text or f"Chapter {chapter_num}",
                    "language": "en",
                    "volume": "",
                })
            results.reverse()
            return results[offset: offset + limit]
        except Exception as e:
            logger.error(f"AsuraScans get_manga_chapters: {e}")
            return []

    async def get_chapter_images(self, chapter_id: str) -> List[str]:
        try:
            import asyncio
            manga_slug, ch_slug = chapter_id.split("|", 1)
            url = f"{BASE_URL}/series/{manga_slug}/chapter/{ch_slug}"
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, _sync_run, _pw_get_images, url, self.IMAGE_SEL
            )
        except Exception as e:
            logger.error(f"AsuraScans get_chapter_images: {e}")
            return []
