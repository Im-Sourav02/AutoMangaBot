"""ManhwaClub -- thin wrapper around MadaraBaseAPI."""
from Scrapers.base.madara_base import MadaraBaseAPI


class ManhwaClubAPI(MadaraBaseAPI):
    base_url = "https://manhwaclub.com"
