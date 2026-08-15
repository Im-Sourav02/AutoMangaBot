"""ToonGod -- thin wrapper around MadaraBaseAPI."""
from Scrapers.base.madara_base import MadaraBaseAPI


class ToonGodAPI(MadaraBaseAPI):
    base_url = "https://www.toongod.org"
    manga_path = "webtoon"
