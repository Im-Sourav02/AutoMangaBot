import os

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8868692794:AAHvcc1--EXje3xKTNUjtqg0_PC6OEwfYGA")
    USER_ID = int(os.getenv("USER_ID", "8546921170"))
    API_ID = int(os.getenv("API_ID", "39921734"))
    API_HASH = os.getenv("API_HASH", "4c7e427657fbe098c10d8e2eb05ba198")
    DB_NAME = os.getenv("DB_NAME", "AutoMangaBot")
    DB_URL = os.getenv("DB_URL", "mongodb+srv://souravagarwal14092007:szXRs8g7fErCnn4@cluster0.xlsbf3o.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
    MAX_CHAPTERS_PER_CHECK = int(os.getenv("MAX_CHAPTERS", "5"))
    DOWNLOAD_DIR = "downloads"
    STATE_FILE = "bot_state.json"
    CACHE_FILE = "manga_ids_cache.json"
    API_BASE = "https://api.mangadex.org"
    WEB_BASE = "https://mangadex.org"
    LOOKBACK_HOURS = 24
    MAX_IMAGE_SIZE = 10 * 1024 * 1024
    MAX_PDF_SIZE = 50 * 1024 * 1024
    USE_DATABASE = os.getenv("USE_DATABASE", "True").lower() == "True"
    
    PORT = int(os.getenv("PORT", "8080"))
    TG_BOT_WORKERS = int(os.getenv("TG_BOT_WORKERS", "4"))

    PICS = [
        "https://ibb.co/VYSPzSDH","https://ibb.co/rGTqCwBV","https://ibb.co/r2QZ0T0q","https://ibb.co/67kGFzC5","https://ibb.co/gZh6qysN","https://ibb.co/0ysjvb0t","https://ibb.co/7dGbyPvk"
    ]

    DEFAULT_FILENAME_FORMAT = "⌯ [𝖢{chapter_num}] {manga_title} @Manhwa_Infinix"