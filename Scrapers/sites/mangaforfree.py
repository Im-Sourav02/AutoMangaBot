"""
MangaForFreeAPI -- thin wrapper around MadaraBaseAPI.
Base URL: https://mangaforfree.net
"""
from Scrapers.base.madara_base import MadaraBaseAPI


class MangaForFreeAPI(MadaraBaseAPI):
    base_url = "https://mangaforfree.net"
