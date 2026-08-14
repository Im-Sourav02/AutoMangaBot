"""Toonily -- thin wrapper around MadaraBaseAPI."""
from Plugins.Sites.Base.madara_base import MadaraBaseAPI


class ToonilyAPI(MadaraBaseAPI):
    base_url   = "https://toonily.com"
    manga_path = "webtoon"  # Toonily uses /webtoon/ not /manga/
