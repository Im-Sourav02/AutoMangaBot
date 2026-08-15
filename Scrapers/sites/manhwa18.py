"""
Manhwa18API -- thin wrapper around MadaraBaseAPI.
Base URL: https://manhwa18.cc
"""
from Scrapers.base.madara_base import MadaraBaseAPI


class Manhwa18API(MadaraBaseAPI):
    base_url = "https://manhwa18.cc"
