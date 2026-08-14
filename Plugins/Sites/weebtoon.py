"""
WebtoonScan -- DISABLED (domain is dead as of 2025).
Left as a stub so imports don't break. Returns empty results.
"""
from Plugins.Sites.Base.madara_base import MadaraBaseAPI


class WebtoonScanAPI(MadaraBaseAPI):
    base_url = ""  # disabled

    async def search_manga(self, *a, **kw):
        return []

    async def get_manga_info(self, *a, **kw):
        return None

    async def get_manga_chapters(self, *a, **kw):
        return []

    async def get_chapter_images(self, *a, **kw):
        return []
