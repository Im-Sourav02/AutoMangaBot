"""
MangaDistrictAPI -- thin wrapper around MadaraBaseAPI.
Base URL: https://mangadistrict.com
"""
from Scrapers.base.madara_base import MadaraBaseAPI


class MangaDistrictAPI(MadaraBaseAPI):
    base_url = "https://mangadistrict.com"
