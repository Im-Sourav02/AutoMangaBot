"""
VortexScansAPI -- Thin wrapper for vortexscans.org (MangaStream theme).
"""
from Plugins.Sites.Base.mangastream_base import MangaStreamBaseAPI


class VortexScansAPI(MangaStreamBaseAPI):
    base_url = "https://vortexscans.org"
    SEARCH_SEL  = ".bsx a, .listupd .bs a"
    CHAPTER_SEL = ".eplister li a, #chapterlist li a"
    IMAGE_SEL   = "#readerarea img, .reader-area img"
