"""
Hentai20API -- thin wrapper around MadaraBaseAPI.
Base URL: https://hentai20.io
"""
from Plugins.Sites.Base.madara_base import MadaraBaseAPI


class Hentai20API(MadaraBaseAPI):
    base_url = "https://hentai20.io"
