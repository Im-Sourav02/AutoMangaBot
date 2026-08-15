import logging
import asyncio
import re
from typing import List, Dict, Optional
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

OMEGA_BASE = "https://omegascans.org"
OMEGA_API  = "https://api.omegascans.org"
MEDIA_HOST = "media.omegascans.org"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": OMEGA_BASE,
    "Referer": OMEGA_BASE + "/",
}


class OmegaScansAPI:
    def __init__(self, Config):
        self.Config = Config
        self.session = None

    async def __aenter__(self):
        self.session = AsyncSession(impersonate="chrome124", verify=False)
        self.session.headers.update(_HEADERS)
        return self

    async def __aexit__(self, *_):
        if self.session:
            await self.session.close()

    # ── helpers ────────────────────────────────────────────────────────────────
    def _encode_id(self, series_id: int, series_slug: str, chapter_id: int, chapter_slug: str) -> str:
        return f"{series_id}|{series_slug}|{chapter_id}|{chapter_slug}"

    def _decode_chapter_id(self, chapter_id: str):
        parts = chapter_id.split("|")
        if len(parts) == 4:
            return int(parts[0]), parts[1], int(parts[2]), parts[3]
        raise ValueError(f"Invalid Omega chapter_id format: {chapter_id!r}")

    # ── search ─────────────────────────────────────────────────────────────────
    async def search_manga(self, query: str, limit: int = 10) -> List[Dict]:
        """Search by scanning listing pages (API's own search often returns 0)."""
        try:
            results: List[Dict] = []
            page = 1
            query_lc = query.lower()

            while len(results) < limit:
                r = await self.session.get(
                    f"{OMEGA_API}/query",
                    params={"perPage": 30, "page": page},
                )
                r.raise_for_status()
                data = r.json()
                items = data.get("data", [])
                if not items:
                    break

                for item in items:
                    title = item.get("title", "")
                    if query_lc in title.lower():
                        results.append({
                            "id": f"{item['id']}|{item.get('series_slug', '')}",
                            "title": title,
                        })
                        if len(results) >= limit:
                            break

                meta = data.get("meta", {})
                if page >= meta.get("last_page", 1):
                    break
                page += 1

            return results
        except Exception as e:
            logger.error(f"OmegaScans search failed: {e}")
            return []

    # ── manga info ─────────────────────────────────────────────────────────────
    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        try:
            raw_id = manga_id.split("|")[0]
            slug   = manga_id.split("|")[1] if "|" in manga_id else ""

            # Scan listing to find matching row
            page = 1
            while True:
                r = await self.session.get(f"{OMEGA_API}/query", params={"perPage": 50, "page": page})
                r.raise_for_status()
                data = r.json()
                items = data.get("data", [])
                item = next((x for x in items if str(x.get("id")) == raw_id), None)
                if item:
                    cover = item.get("thumbnail") or item.get("series_thumbnail") or ""
                    return {
                        "id": manga_id,
                        "title": item.get("title", ""),
                        "description": re.sub(r"<[^>]+>", "", item.get("description", "")),
                        "cover": cover,
                        "_slug": item.get("series_slug", slug),
                    }
                if page >= data.get("meta", {}).get("last_page", 1):
                    break
                page += 1
            return None
        except Exception as e:
            logger.error(f"OmegaScans get_manga_info failed: {e}")
            return None

    # ── chapters ───────────────────────────────────────────────────────────────
    async def get_manga_chapters(self, manga_id: str, limit: int = 500, offset: int = 0, languages=None) -> List[Dict]:
        try:
            raw_id = manga_id.split("|")[0]
            slug   = manga_id.split("|")[1] if "|" in manga_id else ""

            results: List[Dict] = []
            page = 1
            while True:
                r = await self.session.get(
                    f"{OMEGA_API}/chapter/query",
                    params={"series_id": int(raw_id), "perPage": 100, "page": page},
                )
                r.raise_for_status()
                data = r.json()
                chapters = data.get("data", [])
                if not chapters:
                    break

                for ch in chapters:
                    if ch.get("price", 0) != 0:
                        continue  # skip paid chapters
                    ch_id    = ch["id"]
                    ch_slug  = ch.get("chapter_slug", "")
                    ch_name  = ch.get("chapter_name", "")
                    ch_title = ch.get("chapter_title", "") or ""
                    num_match = re.search(r"[\d.]+", ch_name)
                    chapter_num = num_match.group() if num_match else ch_name

                    results.append({
                        "id": self._encode_id(int(raw_id), slug, ch_id, ch_slug),
                        "chapter": chapter_num,
                        "title": ch_title,
                        "language": "en",
                        "volume": "",
                    })

                meta = data.get("meta", {})
                if page >= meta.get("last_page", 1):
                    break
                page += 1

            results.reverse()
            return results[offset: offset + limit]
        except Exception as e:
            logger.error(f"OmegaScans get_manga_chapters failed: {e}")
            return []

    async def get_latest_chapters(self, manga_id: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        return await self.get_manga_chapters(manga_id, limit=limit, offset=offset)

    # ── chapter info ───────────────────────────────────────────────────────────
    async def get_chapter_info(self, chapter_id: str) -> Optional[Dict]:
        try:
            series_id, series_slug, ch_id, ch_slug = self._decode_chapter_id(chapter_id)

            r = await self.session.get(
                f"{OMEGA_API}/chapter/query",
                params={"series_id": series_id, "perPage": 200, "page": 1},
            )
            r.raise_for_status()
            chapters = r.json().get("data", [])
            ch = next((c for c in chapters if c["id"] == ch_id), None)

            ch_name  = (ch or {}).get("chapter_name", "")
            ch_title = (ch or {}).get("chapter_title", "") or ""
            num_match = re.search(r"[\d.]+", ch_name)
            chapter_num = num_match.group() if num_match else ch_name

            info = await self.get_manga_info(f"{series_id}|{series_slug}")
            manga_title = (info or {}).get("title", "")

            return {
                "id": chapter_id,
                "chapter": chapter_num,
                "title": ch_title or f"Chapter {chapter_num}",
                "manga_title": manga_title,
            }
        except Exception as e:
            logger.error(f"OmegaScans get_chapter_info failed: {e}")
            return None

    # ── chapter images via Playwright ──────────────────────────────────────────
    async def get_chapter_images(self, chapter_id: str) -> List[str]:
        """Uses a Playwright Chromium instance to render the reader and extract page URLs."""
        try:
            _, series_slug, _, ch_slug = self._decode_chapter_id(chapter_id)
            reader_url = f"{OMEGA_BASE}/series/{series_slug}/{ch_slug}"
            logger.info(f"OmegaScans: Playwright → {reader_url}")
            # Run in a separate thread/loop so it doesn't block the bot's event loop
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _fetch_images_sync, reader_url)
        except Exception as e:
            logger.error(f"OmegaScans get_chapter_images failed: {e}")
            return []


# ── Playwright helpers (sync wrapper + async impl) ─────────────────────────────

def _fetch_images_sync(url: str) -> List[str]:
    """
    Sync wrapper called from run_in_executor.
    Sets a ProactorEventLoop policy (required on Windows for subprocess/Playwright)
    then runs the async Playwright scraper in its own isolated event loop.
    """
    import asyncio as _asyncio
    import sys

    # Windows requires ProactorEventLoop for subprocess support in threads
    if sys.platform == "win32":
        _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())

    return _asyncio.run(_fetch_images_pw(url))


async def _fetch_images_pw(url: str) -> List[str]:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # Wait for chapter images to hydrate
            try:
                await page.wait_for_selector(
                    f'img[src*="{MEDIA_HOST}"][src*="/uploads/"]',
                    timeout=20000,
                )
            except Exception:
                import asyncio as _aio
                await _aio.sleep(6)  # fallback wait

            images: List[str] = await page.evaluate("""
            () => {
                const imgs = Array.from(document.querySelectorAll('img'));
                return imgs
                    .map(img => img.src || img.getAttribute('data-src') || '')
                    .filter(src =>
                        src.startsWith('http') &&
                        src.includes('media.omegascans.org') &&
                        src.includes('/uploads/')
                    );
            }
            """)
            return images
        finally:
            await browser.close()
