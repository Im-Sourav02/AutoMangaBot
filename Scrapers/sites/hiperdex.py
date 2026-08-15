"""
HiperdexAPI -- thin wrapper around MadaraBaseAPI.
Base URL: https://hiperdex.com
"""
from Scrapers.base.madara_base import MadaraBaseAPI


class HiperdexAPI(MadaraBaseAPI):
    base_url = "https://hiperdex.com"
