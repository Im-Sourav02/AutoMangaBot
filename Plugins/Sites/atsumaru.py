import logging
import urllib.parse
import re
from typing import List, Dict, Optional
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

class AtsumaruAPI:
    def __init__(self, Config):
        self.Config = Config
        self.base_url = "https://atsu.moe"
        self.api_url = "https://atsu.moe/api"
        self.session = None

    async def __aenter__(self):
        self.session = AsyncSession(impersonate="chrome110", verify=False)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": self.base_url,
        })
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def search_manga(self, query: str, limit: int = 10) -> List[Dict]:
        """Search using Atsumaru's Typesense API."""
        try:
            encoded_query = urllib.parse.quote_plus(query)
            search_url = f"{self.base_url}/collections/manga/documents/search?filter_by=&q={encoded_query}&limit={limit}&query_by=title%2CenglishTitle%2CotherNames%2Cauthors&query_by_weights=4%2C3%2C2%2C1&include_fields=id%2Ctitle%2CenglishTitle%2Cposter%2CposterSmall%2CposterMedium%2Ctype%2CisAdult%2Cstatus%2Cyear&num_typos=4%2C3%2C2%2C1"
            
            response = await self.session.get(search_url)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for hit in data.get("hits", []):
                doc = hit.get("document", {})
                if doc:
                    manga_id = doc.get("id")
                    title = doc.get("title") or doc.get("englishTitle")
                    if manga_id and title:
                        results.append({
                            'id': manga_id,
                            'title': title
                        })
            
            return results
        except Exception as e:
            logger.error(f"Atsumaru search failed: {e}")
            return []

    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        try:
            url = f"{self.api_url}/manga/page"
            response = await self.session.get(url, params={"id": manga_id})
            response.raise_for_status()
            data = response.json()
            
            manga_page = data.get("mangaPage", {})
            title = manga_page.get("title", "")
            desc = manga_page.get("description", "")
            
            cover = ""
            poster = manga_page.get("poster")
            if isinstance(poster, dict):
                cover = poster.get("image", "")
            elif isinstance(poster, str):
                cover = poster
                
            if cover:
                cover = f"{self.base_url}/static/{cover}"
                
            return {
                'id': manga_id,
                'title': title,
                'description': desc,
                'cover': cover
            }
        except Exception as e:
            logger.error(f"Failed to get Atsumaru manga info: {e}")
            return None

    async def get_latest_chapters(self, manga_id: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        return await self.get_manga_chapters(manga_id, limit=limit, offset=offset)

    async def get_manga_chapters(self, manga_id: str, limit: int = 500, offset: int = 0, languages: List[str] = ['en']) -> List[Dict]:
        try:
            url = f"{self.api_url}/manga/allChapters"
            response = await self.session.get(url, params={"mangaId": manga_id})
            response.raise_for_status()
            data = response.json()
            
            chapters = data.get("chapters", [])
            results = []
            
            for ch in chapters:
                # Format to match existing structure
                title = ch.get("title", "")
                number = ch.get("number", "")
                
                results.append({
                    'id': f'{manga_id}|{ch.get("id")}',
                    'chapter': str(number),
                    'title': title,
                    'language': 'en',
                    'volume': ch.get("volume", "")
                })
                
            results.reverse()
            return results[offset:offset+limit]
        except Exception as e:
            logger.error(f"Failed to get Atsumaru chapters: {e}")
            return []

    async def get_chapter_info(self, chapter_id: str) -> Optional[Dict]:
        try:
            manga_id, real_chap_id = chapter_id.split('|')
            
            # Fetch real chapter info from allChapters list
            url = f"{self.api_url}/manga/allChapters"
            response = await self.session.get(url, params={"mangaId": manga_id})
            response.raise_for_status()
            data = response.json()
            chapters = data.get("chapters", [])
            
            chapter_num = ""
            chapter_title = ""
            for ch in chapters:
                if ch.get("id") == real_chap_id:
                    chapter_num = str(ch.get("number", ""))
                    chapter_title = ch.get("title") or f"Chapter {chapter_num}"
                    break
            
            # Fetch manga title
            manga_info = await self.get_manga_info(manga_id)
            manga_title = manga_info['title'] if manga_info else ""
            
            return {
                'id': chapter_id,
                'title': chapter_title,
                'chapter': chapter_num,
                'manga_title': manga_title
            }
        except Exception as e:
            logger.error(f"Failed to get Atsumaru chapter info: {e}")
            return None

    async def get_chapter_images(self, chapter_id: str) -> List[str]:
        try:
            manga_id, real_chap_id = chapter_id.split('|')
            url = f"{self.api_url}/read/chapter"
            response = await self.session.get(url, params={"mangaId": manga_id, "chapterId": real_chap_id})
            response.raise_for_status()
            
            data = response.json()
            read_chapter = data.get("readChapter", {})
            pages = read_chapter.get("pages", [])
            
            # Extract image paths and add base URL
            image_urls = []
            for p in pages:
                image_path = p.get("image", "")
                if image_path:
                    image_urls.append(f"{self.base_url}{image_path}")
                    
            return image_urls
        except Exception as e:
            logger.error(f"Failed to get Atsumaru images: {e}")
            return []
