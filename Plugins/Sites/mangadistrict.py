"""
MangaDistrictAPI -- thin wrapper around MadaraBaseAPI.
Base URL: https://mangadistrict.com
"""
from Plugins.Sites.Base.madara_base import MadaraBaseAPI


class MangaDistrictAPI(MadaraBaseAPI):
    base_url = "https://mangadistrict.com"
