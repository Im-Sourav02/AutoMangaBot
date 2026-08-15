"""
ManhwaReadAPI -- thin wrapper around MadaraBaseAPI.
Base URL: https://manhwaread.net
"""
from Scrapers.base.madara_base import MadaraBaseAPI


class ManhwaReadAPI(MadaraBaseAPI):
    base_url = "https://manhwaread.net"
