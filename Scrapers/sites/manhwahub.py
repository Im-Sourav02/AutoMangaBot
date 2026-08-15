"""ManhwaHub -- thin wrapper around MadaraBaseAPI."""
from Scrapers.base.madara_base import MadaraBaseAPI


class ManhwaHubAPI(MadaraBaseAPI):
    base_url = "https://manhwahub.me"
