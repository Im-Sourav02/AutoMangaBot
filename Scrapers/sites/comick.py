# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
# Supoort group @rexbotschat

import logging
from typing import List, Dict, Optional
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

class ComickAPI:
    def __init__(self, Config):
        self.Config = Config
        self.api_url = "https://api.comick.dev"
        self.session = None

    async def __aenter__(self):
        self.session = AsyncSession(impersonate="chrome110", verify=False)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def api_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        try:
            url = f"{self.api_url}{endpoint}"
            response = await self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Comick API request failed: {e}")
            return None

    async def search_manga(self, query: str, limit: int = 10) -> List[Dict]:
        try:
            params = {'q': query, 'limit': limit}
            # Note: /search endpoint might be /v1.0/search
            data = await self.api_request('/v1.0/search', params)
            if not data or not isinstance(data, list):
                return []
            
            results = []
            for item in data:
                title = item.get('title')
                hid = item.get('hid')
                if not title or not hid:
                    continue
                
                results.append({
                    'id': hid,
                    'title': title
                })
            return results
        except Exception as e:
            logger.error(f"Failed to search Comick: {e}")
            return []

    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        try:
            data = await self.api_request(f'/comic/{manga_id}')
            if not data or 'comic' not in data:
                return None
            
            comic = data['comic']
            title = comic.get('title', 'Unknown')
            return {
                'id': manga_id,
                'title': title
            }
        except Exception as e:
            logger.error(f"Failed to get Comick info: {e}")
            return None

    async def get_latest_chapters(self, offset: int = 0) -> List[Dict]:
        return []

    async def get_manga_chapters(self, manga_id: str, limit: int = 20, offset: int = 0, languages: list = ['en']) -> List[Dict]:
        try:
            page = (offset // limit) + 1
            params = {
                'lang': ','.join(languages),
                'limit': limit,
                'page': page
            }
            data = await self.api_request(f'/comic/{manga_id}/chapters', params)
            if not data or 'chapters' not in data:
                return []
            
            chapters_data = data['chapters']
            chapters = []
            for item in chapters_data:
                group_name = "Unknown"
                if item.get('group_name') and len(item['group_name']) > 0:
                    group_name = item['group_name'][0]
                
                chapters.append({
                    'id': item.get('hid'),
                    'chapter': item.get('chap', '0'),
                    'title': item.get('title', ''),
                    'group': group_name
                })
            return chapters
        except Exception as e:
            logger.error(f"Failed to get Comick chapters: {e}")
            return []

    async def get_chapter_info(self, chapter_id: str) -> Optional[Dict]:
        try:
            data = await self.api_request(f'/chapter/{chapter_id}')
            if not data or 'chapter' not in data:
                return None
            
            chap_info = data['chapter']
            comic_info = data.get('comic', {})
            return {
                'id': chapter_id,
                'chapter': chap_info.get('chap', '0'),
                'title': chap_info.get('title', ''),
                'manga_title': comic_info.get('title', 'Unknown')
            }
        except Exception as e:
            logger.error(f"Failed to get Comick chapter info: {e}")
            return None

    async def get_chapter_images(self, chapter_id: str) -> Optional[List[str]]:
        try:
            data = await self.api_request(f'/chapter/{chapter_id}')
            if not data or 'chapter' not in data or 'images' not in data['chapter']:
                return None
            
            images = data['chapter']['images']
            image_urls = []
            for img in images:
                url = img.get('url')
                if url:
                    image_urls.append(url)
            return image_urls
        except Exception as e:
            logger.error(f"Failed to get Comick chapter images: {e}")
            return None
