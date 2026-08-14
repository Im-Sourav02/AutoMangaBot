"""ManhwaClub -- thin wrapper around MadaraBaseAPI."""
from Plugins.Sites.Base.madara_base import MadaraBaseAPI


class ManhwaClubAPI(MadaraBaseAPI):
    base_url = "https://manhwaclub.com"
