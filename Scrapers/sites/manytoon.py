"""
ManyToonAPI -- thin wrapper around MadaraBaseAPI.
Base URL: https://manytoon.com
"""
from Scrapers.base.madara_base import MadaraBaseAPI


class ManyToonAPI(MadaraBaseAPI):
    base_url = "https://manytoon.com"
