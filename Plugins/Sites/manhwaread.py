"""
ManhwaReadAPI -- thin wrapper around MadaraBaseAPI.
Base URL: https://manhwaread.net
"""
from Plugins.Sites.Base.madara_base import MadaraBaseAPI


class ManhwaReadAPI(MadaraBaseAPI):
    base_url = "https://manhwaread.net"
