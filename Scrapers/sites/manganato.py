"""
MangaNatoAPI -- Scraper for manganato.com (and chapmanganato.com).
Uses curl_cffi (no CF on MangaNato) with BeautifulSoup parsing.
"""
import re
import logging
from typing import List, Dict, Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_SEARCH = "https://manganato.com/search/story/{}"
BASE_MANGA  = "https://manganato.com/{}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"


async def _get(url: str) -> Optional[str]:
    try:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate="chrome124") as s:
            r = await s.get(url, headers={"User-Agent": UA, "Referer": "https://manganato.com/"}, timeout=15)
            if r.status_code < 400:
                return r.text
    except Exception as e:
        logger.debug(f"manganato _get {url}: {e}")
    return None


class MangaNatoAPI:
    def __init__(self, Config):
        self.Config = Config

    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass

    async def search_manga(self, query: str, limit: int = 10) -> List[Dict]:
        try:
            slug = re.sub(r"[^a-z0-9]", "_", query.lower())
            html = await _get(BASE_SEARCH.format(slug))
            if not html: return []
            soup = BeautifulSoup(html, "lxml")
            results = []
            for a in soup.select(".search-story-item .item-img, .search-story-item a.item-title")[:limit * 3]:
                href = a.get("href", "")
                title_el = a.select_one(".item-title") or a
                title = title_el.get("title") or title_el.get_text(strip=True)
                if not href or not title: continue
                manga_id = href.rstrip("/").split("/")[-1]
                if manga_id and not any(r["id"] == manga_id for r in results):
                    results.append({"id": manga_id, "title": title})
                if len(results) >= limit: break
            return results
        except Exception as e:
            logger.error(f"MangaNato search_manga: {e}")
            return []

    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        try:
            html = await _get(BASE_MANGA.format(manga_id))
            if not html: return None
            soup = BeautifulSoup(html, "lxml")
            title_el = soup.select_one(".story-info-right h1, .panel-story-info h1")
            title = title_el.get_text(strip=True) if title_el else manga_id
            desc_el = soup.select_one("#panel-story-info-description, .panel-story-info-description")
            desc = desc_el.get_text(strip=True)[:500] if desc_el else ""
            cover_el = soup.select_one(".info-image img, .story-info-left img")
            cover = cover_el.get("src", "") if cover_el else ""
            return {"id": manga_id, "title": title, "description": desc, "cover": cover}
        except Exception as e:
            logger.error(f"MangaNato get_manga_info: {e}")
            return None

    async def get_manga_chapters(self, manga_id: str, limit: int = 500,
                                  offset: int = 0, languages=None) -> List[Dict]:
        try:
            html = await _get(BASE_MANGA.format(manga_id))
            if not html: return []
            soup = BeautifulSoup(html, "lxml")
            rows = soup.select(".row-content-chapter li a.chapter-name, .panel-story-chapter-list li a")
            results = []
            for a in rows:
                href = a.get("href", "")
                text = a.get_text(strip=True)
                ch_slug = href.rstrip("/").split("/")[-1]
                m = re.search(r"chapter[_-]?([\d]+(?:[.\-]\d+)?)", ch_slug, re.I)
                chapter_num = m.group(1).replace("-", ".") if m else ch_slug
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
            logger.error(f"MangaNato get_manga_chapters: {e}")
            return []

    async def get_latest_chapters(self, manga_id, limit=20, offset=0):
        return await self.get_manga_chapters(manga_id, limit=limit, offset=offset)

    async def get_chapter_info(self, chapter_id: str) -> Optional[Dict]:
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
            m = re.search(r"([\d]+(?:[.\-]\d+)?)", ch_slug)
            chapter_num = m.group(1).replace("-", ".") if m else ch_slug
            info = await self.get_manga_info(manga_slug)
            return {
                "id": chapter_id, "chapter": chapter_num,
                "title": f"Chapter {chapter_num}",
                "manga_title": (info or {}).get("title", ""),
            }
        except Exception as e:
            logger.error(f"MangaNato get_chapter_info: {e}")
            return None

    async def get_chapter_images(self, chapter_id: str) -> List[str]:
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
            # Chapter URL: https://chapmanganato.com/{manga_id}/{ch_slug}
            url = f"https://chapmanganato.com/{manga_slug}/{ch_slug}"
            html = await _get(url)
            if not html:
                # Fallback to manganato.com domain
                url = f"https://manganato.com/{manga_slug}/{ch_slug}"
                html = await _get(url)
            if not html: return []
            soup = BeautifulSoup(html, "lxml")
            images = []
            for img in soup.select(".container-chapter-reader img"):
                src = (img.get("data-src") or img.get("src") or "").strip()
                if src.startswith("http") and src not in images:
                    images.append(src)
            return images
        except Exception as e:
            logger.error(f"MangaNato get_chapter_images: {e}")
            return []
