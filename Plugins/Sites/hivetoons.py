"""
HiveToonsAPI — Scraper for hivetoons.org
Architecture: Custom Next.js SPA with SSR.
Key findings from network inspection:
- /series page returns ALL 204 series (search param is ignored server-side)
  → We do client-side fuzzy matching on slugs and card titles
- Series page chapters: /series/<slug>/chapter-<N> (hyphenated, no /chapter/<id>)
- No private API needed — all data is in SSR HTML
"""
import asyncio
import json
import logging
import re
from typing import List, Dict, Optional
from urllib.parse import quote

from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
import difflib

logger = logging.getLogger(__name__)

SITE_BASE = "https://hivetoons.org"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
BASE_HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": SITE_BASE + "/",
}


def _fuzzy_match(query: str, candidates: List[Dict], key: str = "title", threshold: float = 0.3) -> List[Dict]:
    """Rank candidates by fuzzy similarity to query."""
    q = query.lower()
    scored = []
    for c in candidates:
        name = c.get(key, c.get("id", "")).lower()
        # Direct substring match scores highest
        if q in name or q in c.get("id", "").lower():
            scored.append((1.0, c))
        else:
            ratio = difflib.SequenceMatcher(None, q, name).ratio()
            if ratio >= threshold:
                scored.append((ratio, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored]


class HiveToonsAPI:
    def __init__(self, Config):
        self.Config = Config
        self._session: Optional[AsyncSession] = None
        self._series_cache: Optional[List[Dict]] = None  # cache the full series list

    async def __aenter__(self):
        self._session = AsyncSession(impersonate="chrome124", verify=False)
        return self

    async def __aexit__(self, *_):
        if self._session:
            await self._session.close()

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    async def _get_html(self, path: str) -> Optional[str]:
        try:
            url = f"{SITE_BASE}{path}"
            r = await self._session.get(url, headers=BASE_HEADERS, timeout=20)
            if r.status_code < 400:
                return r.text
            logger.debug(f"HiveToons _get_html {path} → {r.status_code}")
        except Exception as e:
            logger.error(f"HiveToons _get_html {path}: {e}")
        return None

    async def _get_all_series(self) -> List[Dict]:
        """Fetch all series from the /series listing page and cache them."""
        if self._series_cache is not None:
            return self._series_cache
        html = await self._get_html("/series")
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        results: List[Dict] = []
        seen: set = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Match only /series/<slug> (not /series/<slug>/chapter-...)
            m = re.match(r"^/series/([^/?#/]+)$", href)
            if not m:
                continue
            slug = m.group(1)
            if slug in seen:
                continue
            seen.add(slug)
            # Try to find the title from sibling/child elements
            title_el = a.find(["h3", "h2", "h4"])
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or title.lower() in ("manhwa", "manga", "manhua"):
                title = slug.replace("-", " ").title()
            results.append({"id": slug, "title": title})
        self._series_cache = results
        return results

    @staticmethod
    def _slug(url_or_slug: str) -> str:
        m = re.search(r"/series/([^/?#/]+)", url_or_slug)
        return m.group(1) if m else url_or_slug.rstrip("/").split("/")[-1]

    # ------------------------------------------------------------------ #
    #  Stage 1 — Search
    # ------------------------------------------------------------------ #
    async def search_manga(self, query: str, limit: int = 10) -> List[Dict]:
        try:
            all_series = await self._get_all_series()
            matched = _fuzzy_match(query, all_series, threshold=0.3)
            return matched[:limit]
        except Exception as e:
            logger.error(f"HiveToons search_manga: {e}")
            return []

    # ------------------------------------------------------------------ #
    #  Stage 2 — Manga Info
    # ------------------------------------------------------------------ #
    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        try:
            slug = self._slug(manga_id)
            html = await self._get_html(f"/series/{slug}")
            if not html:
                return None
            soup = BeautifulSoup(html, "lxml")

            title = slug.replace("-", " ").title()
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True).split("|")[0].replace("- Hive Toon", "").strip()

            cover = ""
            for img in soup.find_all("img"):
                src = img.get("src", "") or img.get("data-src", "")
                if src and src.startswith("http") and "logo" not in src.lower() and "favicon" not in src.lower() and "banner" not in src.lower() and "example.com" not in src.lower():
                    cover = src
                    break

            desc = ""
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 30:
                    desc = text[:500]
                    break

            return {"id": slug, "title": title, "description": desc, "cover": cover}
        except Exception as e:
            logger.error(f"HiveToons get_manga_info: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Stage 3 — Chapter List
    # Chapter URLs: /series/<slug>/chapter-<N>
    # ------------------------------------------------------------------ #
    async def get_manga_chapters(self, manga_id: str, limit: int = 500,
                                  offset: int = 0, languages=None) -> List[Dict]:
        try:
            slug = self._slug(manga_id)
            html = await self._get_html(f"/series/{slug}")
            if not html:
                return []

            soup = BeautifulSoup(html, "lxml")
            results: List[Dict] = []
            seen: set = set()

            chapter_pattern = re.compile(
                rf"^/series/{re.escape(slug)}/(chapter-[\w-]+)$"
            )
            for a in soup.find_all("a", href=True):
                href = a["href"]
                m = chapter_pattern.match(href)
                if not m:
                    continue
                ch_id = m.group(1)
                if ch_id in seen:
                    continue
                seen.add(ch_id)
                num_parts = re.findall(r"\d+", ch_id)
                chapter_num = ".".join(num_parts) if num_parts else ch_id
                text = a.get_text(strip=True) or f"Chapter {chapter_num}"
                results.append({
                    "id":       f"{slug}|{ch_id}",
                    "chapter":  chapter_num,
                    "title":    text,
                    "language": "en",
                    "volume":   "",
                })

            def ch_sort_key(c: Dict):
                try:
                    return float(c["chapter"])
                except ValueError:
                    return 0.0

            results.sort(key=ch_sort_key)
            return results[offset: offset + limit]
        except Exception as e:
            logger.error(f"HiveToons get_manga_chapters: {e}")
            return []

    async def get_latest_chapters(self, manga_id: str, limit: int = 20,
                                   offset: int = 0) -> List[Dict]:
        return await self.get_manga_chapters(manga_id, limit=limit, offset=offset)

    # ------------------------------------------------------------------ #
    #  Stage 3b — Chapter Info
    # ------------------------------------------------------------------ #
    async def get_chapter_info(self, chapter_id: str) -> Optional[Dict]:
        try:
            manga_slug, ch_id = chapter_id.split("|", 1)
            num_parts = re.findall(r"\d+", ch_id)
            ch_num = ".".join(num_parts) if num_parts else ch_id
            info = await self.get_manga_info(manga_slug)
            return {
                "id":          chapter_id,
                "chapter":     ch_num,
                "title":       f"Chapter {ch_num}",
                "manga_title": (info or {}).get("title", manga_slug),
            }
        except Exception as e:
            logger.error(f"HiveToons get_chapter_info: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Stage 4 — Chapter Images
    # URL: /series/<slug>/chapter-<N>
    # ------------------------------------------------------------------ #
    async def get_chapter_images(self, chapter_id: str) -> List[str]:
        try:
            manga_slug, ch_id = chapter_id.split("|", 1)
            html = await self._get_html(f"/series/{manga_slug}/{ch_id}")
            if not html:
                return []

            images: List[str] = []

            for pattern in [
                r'"images"\s*:\s*(\[.*?\])',
                r'"pages"\s*:\s*(\[.*?\])',
                r'"imageUrls"\s*:\s*(\[.*?\])',
                r'"urls"\s*:\s*(\[.*?\])',
                r'"chapter_images"\s*:\s*(\[.*?\])',
            ]:
                for m in re.finditer(pattern, html, re.S):
                    try:
                        blob = json.loads(m.group(1))
                        for item in blob:
                            url = item if isinstance(item, str) else (
                                item.get("url") or item.get("src") or item.get("image") or "")
                            if url and url.startswith("http") and "hivetoon" in url.lower():
                                images.append(url)
                    except Exception:
                        continue
                if images:
                    break

            if not images:
                soup = BeautifulSoup(html, "lxml")
                for sc in soup.find_all("script"):
                    t = sc.get_text()
                    if not t:
                        continue
                    urls = re.findall(r'https://[^\s"\'\\<>]+\.(?:jpg|jpeg|webp|png)', t)
                    for url in urls:
                        if "logo" not in url.lower() and "favicon" not in url.lower() and "banner" not in url.lower() and "example.com" not in url.lower():
                            images.append(url)
                    if images:
                        break

            if not images:
                soup = BeautifulSoup(html, "lxml")
                for img in soup.find_all("img"):
                    src = img.get("data-src") or img.get("src") or ""
                    if src.startswith("http") and any(ext in src for ext in [".jpg", ".jpeg", ".webp", ".png"]):
                        if "logo" not in src.lower() and "banner" not in src.lower() and "example.com" not in src.lower():
                            images.append(src)

            seen: set = set()
            out: List[str] = []
            for url in images:
                if url not in seen:
                    seen.add(url)
                    out.append(url)

            if out:
                logger.info(f"HiveToons: {len(out)} images for {chapter_id}")
            else:
                logger.warning(f"HiveToons: no images found for {chapter_id}")
            return out
        except Exception as e:
            logger.error(f"HiveToons get_chapter_images: {e}")
            return []
