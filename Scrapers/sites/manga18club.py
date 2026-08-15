"""
Manga18clubAPI -- thin wrapper around MadaraBaseAPI.
Base URL: https://manga18.club
"""
from Scrapers.base.madara_base import MadaraBaseAPI


class Manga18clubAPI(MadaraBaseAPI):
    base_url = "https://manga18.club"
