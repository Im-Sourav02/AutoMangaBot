"""
Scrapers package — all web scraping engines.
Exports the SITES registry and get_api_class() helper so that
Services (monitor_task) can resolve an API class by source name
without importing from Handlers (breaking the circular dep).
"""
from Scrapers.sites.mangadex import MangaDexAPI
from Scrapers.sites.mangaforest import MangaForestAPI
from Scrapers.sites.mangakakalot import MangakakalotAPI
from Scrapers.sites.allmanga import AllMangaAPI
from Scrapers.sites.comick import ComickAPI
from Scrapers.sites.atsumaru import AtsumaruAPI
from Scrapers.sites.omegascans import OmegaScansAPI

from Scrapers.sites.toonily import ToonilyAPI
from Scrapers.sites.manhwaread import ManhwaReadAPI
from Scrapers.sites.hentai20 import Hentai20API
from Scrapers.sites.manga18fx import Manga18fxAPI
from Scrapers.sites.manga18club import Manga18clubAPI
from Scrapers.sites.manhwa18 import Manhwa18API

from Scrapers.sites.manhwahub import ManhwaHubAPI
from Scrapers.sites.manytoon import ManyToonAPI
from Scrapers.sites.hiperdex import HiperdexAPI
from Scrapers.sites.mangaforfree import MangaForFreeAPI
from Scrapers.sites.mangadistrict import MangaDistrictAPI
from Scrapers.sites.manganato import MangaNatoAPI
from Scrapers.sites.asurascans import AsuraScansAPI
from Scrapers.sites.vortexscans import VortexScansAPI
from Scrapers.sites.toongod import ToonGodAPI

SITES = {
    "MangaDex":      MangaDexAPI,
    "MangaForest":   MangaForestAPI,
    "Mangakakalot":  MangakakalotAPI,
    "AllManga":      AllMangaAPI,
    "Comick":        ComickAPI,
    "Atsumaru":      AtsumaruAPI,
    "OmegaScans":    OmegaScansAPI,

    "WebCentral":    None,          # filled below
    "Toonily":       ToonilyAPI,
    "ManhwaRead":    ManhwaReadAPI,
    "Hentai20":      Hentai20API,
    "Manga18fx":     Manga18fxAPI,
    "Manga18Club":   Manga18clubAPI,
    "Manhwa18":      Manhwa18API,

    "ManhwaHub":     ManhwaHubAPI,
    "ManyToon":      ManyToonAPI,
    "Hiperdex":      HiperdexAPI,
    "MangaForFree":  MangaForFreeAPI,
    "MangaDistrict": MangaDistrictAPI,
    "MangaNato":     MangaNatoAPI,
    "AsuraScans":    AsuraScansAPI,
    "VortexScans":   VortexScansAPI,
    "ToonGod":       ToonGodAPI,
}

try:
    from Scrapers.sites.webcentral import WebCentralAPI
    SITES["WebCentral"] = WebCentralAPI
except ImportError:
    pass


def get_api_class(source: str):
    """Resolve an API class by source name (case-insensitive)."""
    cls = SITES.get(source)
    if cls is not None:
        return cls
    for key, val in SITES.items():
        if key.lower() == source.lower():
            return val
    return None
