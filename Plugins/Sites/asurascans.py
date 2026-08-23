"""
AsuraScansAPI — Scraper for asuracomic.net

API base: https://api.asurascans.com/api
Key findings (verified by live probing 2026-08-16):
  - Search param:  ?search=<query>   (NOT ?name= or ?title= — those are silently ignored)
  - Chapter list:  /series/{slug}/chapters?page=<n>  (paginated, no last_page in meta)
  - Chapter imgs:  /series/{slug}/chapters/{ch_uuid}  → data.chapter.pages[n].url
  - Locked check:  item["is_locked"] (NOT item["price"])
"""
import logging
from typing import List, Dict, Optional
from urllib.parse import quote_plus
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

API_URL  = "https://api.asurascans.com/api"
BASE_URL = "https://asuracomic.net"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer":  BASE_URL + "/",
    "Origin":   BASE_URL,
    "Accept":   "application/json",
}


class AsuraScansAPI:
    def __init__(self, config=None):
        self.config   = config
        self.base_url = BASE_URL
        self.session  = None

    async def __aenter__(self):
        self.session = AsyncSession(impersonate="chrome124", verify=False)
        self.session.headers.update(_HEADERS)
        return self

    async def __aexit__(self, *_):
        if self.session:
            await self.session.close()

    # ── internal helper ────────────────────────────────────────────────────────
    async def _get(self, url: str) -> Optional[dict]:
        try:
            r = await self.session.get(url, timeout=25)
            if r.status_code < 400:
                return r.json()
        except Exception as e:
            logger.debug(f"AsuraScans GET {url}: {e}")
        return None

    # ── search ─────────────────────────────────────────────────────────────────
    async def search_manga(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search via the official API.

        IMPORTANT: the correct query param is **?search=**, NOT ?name= or ?title=.
        Using ?name= returns the full series listing (all 339 titles) regardless
        of the value — verified by live API probing.
        """
        encoded = quote_plus(query)
        url = f"{API_URL}/series?page=1&search={encoded}"
        data = await self._get(url)

        results: List[Dict] = []
        if not data or "data" not in data:
            logger.warning(f"AsuraScans search returned no data for query={query!r}")
            return results

        items = data.get("data") or []

        # ── Validation: if the API ignored our param it returns 339 results ──
        # A genuine search for a specific title should return far fewer items.
        # If we get a suspiciously large "unfiltered" list, fall back to
        # client-side fuzzy filtering so we never hand random manga to the user.
        total = data.get("meta", {}).get("total", len(items))
        query_lc = query.lower()

        if total > 50:
            # Looks like the API ignored the search param — filter client-side
            logger.warning(
                f"AsuraScans search for {query!r} returned {total} results "
                f"(looks unfiltered). Applying client-side fuzzy filter."
            )
            items = [
                it for it in items
                if query_lc in it.get("title", "").lower()
                or any(query_lc in alt.lower() for alt in it.get("alt_titles", []))
            ]

        for item in items:
            results.append({
                "id":    item["slug"],
                "title": item["title"],
                "cover": item.get("cover", ""),
            })

        return results[:limit]

    # ── manga info ─────────────────────────────────────────────────────────────
    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        """manga_id is the series slug, e.g. 'the-greatest-estate-developer'"""
        data = await self._get(f"{API_URL}/series/{manga_id}")
        if not data:
            return None

        # API wraps the series object under the "series" key
        s = data.get("series") or data.get("data")
        if not s:
            return None

        return {
            "id":          s.get("slug", manga_id),
            "title":       s.get("title", ""),
            "description": s.get("description", ""),
            "cover":       s.get("cover", ""),
            "status":      s.get("status", ""),
            "_chapter_count": s.get("chapter_count", 0),
        }

    # ── chapters ───────────────────────────────────────────────────────────────
    async def get_manga_chapters(
        self, manga_id: str, limit: int = 100, offset: int = 0, languages=None
    ) -> List[Dict]:
        """
        Fetch chapter list from the paginated API endpoint.
        Chapters are returned newest-first by the API; we reverse to oldest-first.
        """
        chapters: List[Dict] = []
        page = 1

        while True:
            data = await self._get(
                f"{API_URL}/series/{manga_id}/chapters?page={page}"
            )
            if not data or not data.get("data"):
                break

            for ch in data["data"]:
                # Skip locked / premium chapters
                if ch.get("is_locked") or ch.get("is_premium"):
                    continue

                num = ch.get("number", "0")
                chapters.append({
                    # ID encodes both slugs so we can fetch images later
                    "id":       f"{manga_id}|{ch['slug']}",
                    "chapter":  str(num),
                    "title":    ch.get("title", "") or "",
                    "language": "en",
                    "volume":   "",
                })

            # The chapters endpoint has no last_page — stop when we get fewer
            # than a full page (API returns 20 per page)
            if len(data["data"]) < 20:
                break
            page += 1

        # Reverse so index 0 = Chapter 1 (ascending order)
        chapters.reverse()
        return chapters[offset: offset + limit]

    async def get_latest_chapters(
        self, manga_id: str, limit: int = 20, offset: int = 0
    ) -> List[Dict]:
        return await self.get_manga_chapters(manga_id, limit=limit, offset=offset)

    # ── chapter images ─────────────────────────────────────────────────────────
    async def get_chapter_images(self, chapter_id: str) -> List[str]:
        """
        chapter_id format: "{series_slug}|{chapter_uuid_or_slug}"
        Images live at data.chapter.pages[n].url  (each page is a dict)
        """
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
        except ValueError:
            logger.error(f"AsuraScans get_chapter_images: bad chapter_id {chapter_id!r}")
            return []

        data = await self._get(
            f"{API_URL}/series/{manga_slug}/chapters/{ch_slug}"
        )
        if not data or "data" not in data:
            return []

        chapter_obj = data["data"].get("chapter", {})
        pages = chapter_obj.get("pages", [])

        # Each page is {"url": "https://cdn.asurascans.com/..."}
        images = []
        for p in pages:
            if isinstance(p, dict):
                url = p.get("url", "")
            else:
                url = str(p)
            if url:
                images.append(url)

        return images

    # ── chapter info ───────────────────────────────────────────────────────────
    async def get_chapter_info(self, chapter_id: str) -> Optional[Dict]:
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
        except ValueError:
            return None

        data = await self._get(
            f"{API_URL}/series/{manga_slug}/chapters/{ch_slug}"
        )
        if not data or "data" not in data:
            return None

        ch = data["data"].get("chapter", {})
        series = data["data"].get("series", {})

        return {
            "id":          chapter_id,
            "chapter":     str(ch.get("number", "0")),
            "title":       ch.get("title") or f"Chapter {ch.get('number', '')}",
            "manga_title": series.get("title", ""),
        }
