"""Toonily -- thin wrapper around MadaraBaseAPI."""
from Scrapers.base.madara_base import MadaraBaseAPI


class ToonilyAPI(MadaraBaseAPI):
    base_url   = "https://toonily.com"
    manga_path = "webtoon"  # Toonily uses /webtoon/ not /manga/
