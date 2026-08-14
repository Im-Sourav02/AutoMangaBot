"""
Manhwa18API -- thin wrapper around MadaraBaseAPI.
Base URL: https://manhwa18.cc
"""
from Plugins.Sites.Base.madara_base import MadaraBaseAPI


class Manhwa18API(MadaraBaseAPI):
    base_url = "https://manhwa18.cc"
