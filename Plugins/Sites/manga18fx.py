"""
Manga18fxAPI -- thin wrapper around MadaraBaseAPI.
Base URL: https://manga18fx.com
"""
from Plugins.Sites.Base.madara_base import MadaraBaseAPI


class Manga18fxAPI(MadaraBaseAPI):
    base_url = "https://manga18fx.com"
