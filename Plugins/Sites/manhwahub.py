"""ManhwaHub -- thin wrapper around MadaraBaseAPI."""
from Plugins.Sites.Base.madara_base import MadaraBaseAPI


class ManhwaHubAPI(MadaraBaseAPI):
    base_url = "https://manhwahub.me"
