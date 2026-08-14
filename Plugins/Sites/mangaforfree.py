"""
MangaForFreeAPI -- thin wrapper around MadaraBaseAPI.
Base URL: https://mangaforfree.net
"""
from Plugins.Sites.Base.madara_base import MadaraBaseAPI


class MangaForFreeAPI(MadaraBaseAPI):
    base_url = "https://mangaforfree.net"
