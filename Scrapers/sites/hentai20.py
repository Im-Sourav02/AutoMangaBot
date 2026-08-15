"""
Hentai20API -- thin wrapper around MadaraBaseAPI.
Base URL: https://hentai20.io
"""
from Scrapers.base.madara_base import MadaraBaseAPI


class Hentai20API(MadaraBaseAPI):
    base_url = "https://hentai20.io"
