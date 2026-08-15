"""
AsuraScansAPI — Scraper for asuracomic.net using their new REST API
"""
import logging
from typing import List, Dict, Optional
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

API_URL = "https://api.asurascans.com/api"
BASE_URL = "https://asuracomic.net"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# CDN headers for downloading images
CDN_HEADERS = {
    "User-Agent": UA,
    "Referer": BASE_URL + "/",
    "Origin": BASE_URL,
}

class AsuraScansAPI:
    def __init__(self, config=None):
        self.config = config
        self.base_url = BASE_URL
        self.session = None

    async def __aenter__(self):
        self.session = AsyncSession(impersonate="chrome124", verify=False)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _get_json(self, url: str) -> Optional[dict]:
        try:
            r = await self.session.get(url, headers={"User-Agent": UA, "Referer": BASE_URL + "/"}, timeout=25)
            if r.status_code < 400:
                return r.json()
        except Exception as e:
            logger.debug(f"Asura API Error {url}: {e}")
        return None

    async def search_manga(self, query: str, limit: int = 50) -> List[Dict]:
        """Search using the API."""
        url = f"{API_URL}/series?page=1&name={query}"
        data = await self._get_json(url)
        results = []
        if data and "data" in data:
            for item in data["data"]:
                results.append({
                    "id": item["slug"],
                    "title": item["title"]
                })
        return results[:limit]

    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        """Get series info using API."""
        url = f"{API_URL}/series/{manga_id}"
        data = await self._get_json(url)
        if data and "series" in data:
            s = data["series"]
            return {
                "id": s["slug"],
                "title": s["title"],
                "description": s.get("description", ""),
                "cover": s.get("cover", ""),
            }
        return None

    async def get_manga_chapters(self, manga_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get chapters using API."""
        url = f"{API_URL}/series/{manga_id}/chapters"
        data = await self._get_json(url)
        chapters = []
        if data and "data" in data:
            for ch in data["data"]:
                chapters.append({
                    # We store both manga_id and chapter slug in the ID so we can fetch it later
                    # since the endpoint requires both: /api/series/{manga_id}/chapters/{chapter_slug}
                    "id": f"{manga_id}|{ch['slug']}",
                    "chapter": str(ch.get("number", "0")),
                    "title": ch.get("title", ""),
                })
        # Note: API might not support limit/offset directly for chapters, so we slice the result
        return chapters[offset:offset+limit]

    async def get_chapter_images(self, chapter_id: str) -> List[str]:
        """Get images using API."""
        try:
            # The chapter_id is packed as "manga_slug|chapter_slug"
            manga_slug, ch_slug = chapter_id.split("|", 1)
        except ValueError:
            return []
            
        url = f"{API_URL}/series/{manga_slug}/chapters/{ch_slug}"
        data = await self._get_json(url)
        images = []
        if data and "data" in data and "chapter" in data["data"]:
            for page in data["data"]["chapter"].get("pages", []):
                images.append(page["url"])
        return images

    async def get_chapter_info(self, chapter_id: str) -> Optional[Dict]:
        """Get info for a specific chapter."""
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
        except ValueError:
            return None
            
        url = f"{API_URL}/series/{manga_slug}/chapters/{ch_slug}"
        data = await self._get_json(url)
        if data and "data" in data and "chapter" in data["data"]:
            ch = data["data"]["chapter"]
            return {
                "id": chapter_id,
                "chapter": str(ch.get("number", "0")),
                "title": ch.get("title", ""),
            }
        return None
