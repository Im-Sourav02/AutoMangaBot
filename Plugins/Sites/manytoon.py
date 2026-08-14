"""
ManyToonAPI -- thin wrapper around MadaraBaseAPI.
Base URL: https://manytoon.com
"""
from Plugins.Sites.Base.madara_base import MadaraBaseAPI


class ManyToonAPI(MadaraBaseAPI):
    base_url = "https://manytoon.com"
