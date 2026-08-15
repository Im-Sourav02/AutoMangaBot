"""
MadaraBaseAPI — Generic base class for Madara WordPress manga theme sites.

CF Bypass Strategy (no paid services):
  1. curl_cffi Chrome impersonation — fast, bypasses mild CF
  2. Camoufox clearance extraction — Firefox anti-detect browser that
     natively passes Cloudflare Turnstile/Managed Challenge.
     Extracts cf_clearance cookie + User-Agent and caches them per-domain
     for 25 minutes. Subsequent requests use fast curl_cffi + injected cookie.
  3. Direct Camoufox page load — last resort if clearance doesn’t help.

Chapter ID format: "{manga_slug}|{chapter_slug}"
"""

import asyncio
import logging
import os
import re
import sys
import time
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, quote_plus

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Per-domain clearance cache: domain -> (cf_clearance, user_agent, expires_timestamp)
_clearance_cache: Dict[str, Tuple[str, str, float]] = {}


# ─── CF-aware HTTP helpers ──────────────────────────────────────────────────────────

def _is_cf_block(text: str, status: int) -> bool:
    if status in (403, 429, 503):
        low = text.lower()
        return "cloudflare" in low or "just a moment" in low or "ray id" in low
    return False


async def _cffi_get(url: str, cf_clearance: str = "", ua_override: str = "",
                    timeout: int = 20) -> Optional[str]:
    """GET via curl_cffi Chrome impersonation with optional CF clearance cookie."""
    try:
        from curl_cffi.requests import AsyncSession
        h = dict(_BASE_HEADERS)
        if ua_override:
            h["User-Agent"] = ua_override
        cookies = {"cf_clearance": cf_clearance} if cf_clearance else {}
        async with AsyncSession(impersonate="chrome124") as s:
            r = await s.get(url, headers=h, cookies=cookies,
                            timeout=timeout, allow_redirects=True)
            if _is_cf_block(r.text, r.status_code):
                return None
            if r.status_code >= 400:
                return None
            return r.text
    except Exception as e:
        logger.debug(f"cffi_get {url}: {e}")
        return None


async def _cffi_post(url: str, data: dict, cf_clearance: str = "",
                     ua_override: str = "", timeout: int = 20) -> Optional[str]:
    """POST via curl_cffi Chrome impersonation with optional CF clearance cookie."""
    try:
        from curl_cffi.requests import AsyncSession
        h = {**_BASE_HEADERS, "X-Requested-With": "XMLHttpRequest"}
        if ua_override:
            h["User-Agent"] = ua_override
        cookies = {"cf_clearance": cf_clearance} if cf_clearance else {}
        async with AsyncSession(impersonate="chrome124") as s:
            r = await s.post(url, data=data, headers=h, cookies=cookies, timeout=timeout)
            if _is_cf_block(r.text, r.status_code):
                return None
            return r.text
    except Exception as e:
        logger.debug(f"cffi_post {url}: {e}")
        return None


# ─── Camoufox clearance extraction ──────────────────────────────────────────────────

def _win_policy():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


async def _camoufox_bypass(url: str) -> Tuple[str, str, Optional[str]]:
    """
    Launch Camoufox (Firefox with C++ anti-detect patches) to bypass
    Cloudflare Turnstile / Managed Challenge without any paid CAPTCHA service.

    Strategy:
      - Camoufox's Firefox fingerprint auto-passes CF Managed Challenges
      - For interactive Turnstile (checkbox), we locate the CF iframe
        and simulate a human-like click
      - Returns (cf_clearance, user_agent, page_html)

    The cf_clearance cookie is cached per-domain for 25 minutes so Camoufox
    only needs to be launched once, after which fast curl_cffi handles all
    subsequent requests.
    """
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError:
        logger.error(
            "camoufox not installed. Run: "
            "pip install camoufox && python -m camoufox fetch"
        )
        return "", "", None

    # ── Memory-limiting Firefox prefs — keeps RAM under ~300 MB ───────────────
    _ff_prefs = {
        # Disable GPU acceleration (no GPU in Railway containers)
        "layers.acceleration.disabled":           True,
        "gfx.webrender.all":                      False,
        "gfx.webrender.enabled":                  False,
        # Limit JS worker threads
        "dom.workers.maxPerDomain":               2,
        # Disable telemetry / background services
        "toolkit.telemetry.enabled":              False,
        "datareporting.healthreport.uploadEnabled": False,
        "browser.ping-centre.telemetry":          False,
        # Reduce memory caches
        "browser.cache.memory.capacity":          8192,   # 8 MB
        "browser.sessionhistory.max_total_viewers": 0,
        # Disable shared memory (crashes in Docker without --shm-size)
        "media.ffmpeg.low-latency.enabled":       False,
    }

    # ── Extra env flags recognised by Playwright/Camoufox ─────────────────────
    import os as _os
    _os.environ.setdefault("MOZ_DISABLE_CONTENT_SANDBOX", "1")  # avoids EACCES

    logger.info(f"Camoufox: bypassing CF for {url}")
    async with AsyncCamoufox(
        headless=True,
        firefox_user_prefs=_ff_prefs,
        # Playwright-level context: restrict viewport to save memory
        args=["--no-remote"],
    ) as browser:
        ctx  = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            iframe_clicked = False
            for i in range(15):  # up to 30 seconds
                try:
                    title = (await page.title()).lower()
                    body  = await page.evaluate(
                        "() => document.body?.innerText?.toLowerCase() || ''"
                    )
                except Exception:
                    # Execution context destroyed = page is navigating (CF redirect)
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                        await page.wait_for_load_state("load", timeout=10000)
                    except Exception:
                        pass
                    await asyncio.sleep(1)
                    continue

                is_cf = (
                    "just a moment" in title or "cloudflare" in title
                    or "security verification" in body
                    or "verify you are human" in body
                )
                if not is_cf:
                    break  # CF challenge cleared!

                if not iframe_clicked and (
                    "verify you are human" in body or "security verification" in body
                ):
                    iframe_clicked = True
                    try:
                        for frame in page.frames:
                            if "challenges.cloudflare.com" in (frame.url or ""):
                                await frame.evaluate(
                                    "() => { "
                                    "  const cb = document.querySelector('input[type=checkbox]'); "
                                    "  if (cb) cb.click(); "
                                    "}"
                                )
                                logger.info("Camoufox: clicked Turnstile checkbox")
                                break
                        cf_frame = page.frame_locator(
                            "iframe[src*='challenges.cloudflare.com']"
                        )
                        checkbox = cf_frame.locator("input[type='checkbox']")
                        if await checkbox.count() > 0:
                            await checkbox.click(delay=120)
                    except Exception as click_err:
                        logger.debug(f"Camoufox iframe click: {click_err}")

                await asyncio.sleep(2)

            # Wait for the post-redirect page to fully load
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=12000)
                await page.wait_for_load_state("load", timeout=12000)
            except Exception:
                await asyncio.sleep(2)

            await asyncio.sleep(1)

            # ── Extract the clearance cookie + UA ─────────────────────────────
            cookies = await ctx.cookies()
            cf_clearance = next(
                (c["value"] for c in cookies if c["name"] == "cf_clearance"), ""
            )
            try:
                ua = await page.evaluate("() => navigator.userAgent")
            except Exception:
                ua = UA
            try:
                html = await page.content()
            except Exception:
                html = None

            if cf_clearance:
                logger.info(f"Camoufox: obtained cf_clearance for {url}")
            else:
                logger.warning(f"Camoufox: no cf_clearance obtained for {url} (may still work)")

            return cf_clearance, ua, html
        finally:
            # ── Immediately close page & context to free memory ───────────────
            try:
                await page.close()
            except Exception:
                pass
            try:
                await ctx.close()
            except Exception:
                pass




def _sync_camoufox_bypass(url: str) -> Tuple[str, str, Optional[str]]:
    """Blocking wrapper — runs in executor thread."""
    _win_policy()
    return asyncio.run(_camoufox_bypass(url))


def _sync_camoufox_post(base_url: str, post_url: str, data: dict) -> Optional[str]:
    """
    Execute a POST request *inside* a Camoufox browser context so that CF
    cookies / challenge state are guaranteed to be present.
    Runs in an executor thread (blocking wrapper).
    """
    _win_policy()

    async def _do_post():
        try:
            from camoufox.async_api import AsyncCamoufox
        except ImportError:
            return None

        async with AsyncCamoufox(headless=True) as browser:
            page = await browser.new_page()
            try:
                # Load the homepage first so CF cookies are set
                await page.goto(base_url, wait_until="domcontentloaded", timeout=45000)

                # Wait for CF challenge to clear
                for _ in range(15):
                    title = await page.title()
                    if "just a moment" not in title.lower() and "cloudflare" not in title.lower():
                        break
                    try:
                        cf_frame = page.frame_locator("iframe[src*='challenges.cloudflare.com']")
                        checkbox = cf_frame.locator("input[type='checkbox']")
                        if await checkbox.count() > 0:
                            await checkbox.click(delay=120)
                    except Exception:
                        pass
                    await asyncio.sleep(2)

                # Build FormData and POST from inside the browser
                form_entries = ", ".join(
                    f"fd.append({k!r}, {v!r})" for k, v in data.items()
                )
                js = f"""async () => {{
                    const fd = new FormData();
                    {form_entries};
                    const res = await fetch({post_url!r}, {{method: 'POST', body: fd}});
                    return await res.text();
                }}"""
                result = await page.evaluate(js)
                return result
            finally:
                await page.close()

    return asyncio.run(_do_post())


async def _get_clearance(base_url: str) -> Tuple[str, str]:
    """
    Return (cf_clearance, user_agent) for base_url's domain.
    Uses a 25-minute in-process cache so Camoufox launches at most once
    per domain per session.
    """
    from urllib.parse import urlparse
    domain = urlparse(base_url).netloc
    cached = _clearance_cache.get(domain)
    if cached:
        cf_cl, ua, expires_at = cached
        if time.time() < expires_at:
            return cf_cl, ua

    loop = asyncio.get_event_loop()
    cf_cl, ua, _ = await loop.run_in_executor(None, _sync_camoufox_bypass, base_url)
    if cf_cl:
        _clearance_cache[domain] = (cf_cl, ua, time.time() + 1500)  # 25 min
    return cf_cl, ua


# ─── Base class ────────────────────────────────────────────────────────────────

class MadaraBaseAPI:
    """
    Generic Madara WordPress manga scraper.

    Subclass and set:
        base_url = "https://yoursite.com"
        use_playwright = True   # if the site blocks curl_cffi consistently
    """

    base_url: str = ""
    use_playwright: bool = False  # override to True for strict-CF sites
    manga_path: str = "manga"    # Toonily uses "webtoon", some sites use "series"

    # CSS selectors — override if the theme uses non-standard classes
    SEARCH_ITEM_SEL = ".post-title h3 a, .post-title h5 a, article .post-title a, .c-image-hover a"
    CHAPTER_ROW_SEL = ".wp-manga-chapter, li.wp-manga-chapter"
    IMAGE_SEL       = ".reading-content img, .page-break img, .chapter-content img, div.text-left img"

    def __init__(self, Config):
        self.Config = Config

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    # ── internal fetch ─────────────────────────────────────────────────────────

    async def _fetch(self, url: str) -> Optional[str]:
        """
        4-tier CF-bypass fetch cascade (no paid services):
          1. curl_cffi (fast Chrome impersonation)
          2. curl_cffi + cached cf_clearance cookie (if domain was previously unlocked)
          3. Camoufox clearance extraction → retry curl_cffi with fresh cookie
          4. Direct Camoufox page load (last resort)
        """
        from urllib.parse import urlparse
        domain = urlparse(self.base_url).netloc

        # Tier 1: plain curl_cffi
        html = await _cffi_get(url)
        if html is not None:
            return html

        # Tier 2: cached clearance
        cached = _clearance_cache.get(domain)
        if cached:
            cf_cl, ua, expires_at = cached
            if time.time() < expires_at:
                html = await _cffi_get(url, cf_clearance=cf_cl, ua_override=ua)
                if html is not None:
                    return html

        # Tier 3: get fresh clearance via Camoufox
        logger.info(f"{self.__class__.__name__}: getting CF clearance via Camoufox for {domain}")
        cf_cl, ua = await _get_clearance(self.base_url)
        if cf_cl:
            html = await _cffi_get(url, cf_clearance=cf_cl, ua_override=ua)
            if html is not None:
                return html

        # Tier 4: direct Camoufox page load
        logger.info(f"{self.__class__.__name__}: direct Camoufox load for {url}")
        loop = asyncio.get_event_loop()
        _, _, html = await loop.run_in_executor(None, _sync_camoufox_bypass, url)
        return html

    async def _fetch_post(self, url: str, data: dict) -> Optional[str]:
        """
        POST with full CF-bypass cascade:
          1. curl_cffi + cached clearance (fast path)
          2. Obtain fresh Camoufox clearance → retry curl_cffi
          3. Execute POST *inside* the Camoufox browser context (last resort)
        """
        from urllib.parse import urlparse
        domain = urlparse(self.base_url).netloc

        # Tier 1 – try with cached clearance
        cached = _clearance_cache.get(domain)
        cf_cl, ua = "", ""
        if cached:
            _cf_cl, _ua, expires_at = cached
            if time.time() < expires_at:
                cf_cl, ua = _cf_cl, _ua

        result = await _cffi_post(url, data, cf_clearance=cf_cl, ua_override=ua)
        if result is not None:
            return result

        # Tier 2 – get fresh clearance via Camoufox, then retry POST
        logger.info(f"{self.__class__.__name__}: CF blocking POST, getting clearance for {domain}")
        cf_cl, ua = await _get_clearance(self.base_url)
        if cf_cl:
            result = await _cffi_post(url, data, cf_clearance=cf_cl, ua_override=ua)
            if result is not None:
                return result

        # Tier 3 – execute POST inside the Camoufox browser (guaranteed to have cookies)
        logger.info(f"{self.__class__.__name__}: executing POST inside Camoufox for {url}")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, _sync_camoufox_post, self.base_url, url, data
        )
        return result

    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    async def _soup_async(self, html: str) -> BeautifulSoup:
        """Parse HTML in a thread pool to avoid blocking the event loop."""
        return await asyncio.to_thread(BeautifulSoup, html, "lxml")

    # ── search ─────────────────────────────────────────────────────────────────

    async def search_manga(self, query: str, limit: int = 10) -> List[Dict]:
        try:
            url = f"{self.base_url}/?s={quote_plus(query)}&post_type=wp-manga"
            html = await self._fetch(url)
            results = []
            if html:
                soup = self._soup(html)
                for a in soup.select(self.SEARCH_ITEM_SEL)[:limit * 2]:
                    href = a.get("href", "")
                    title = a.get_text(strip=True)
                    if not href or not title:
                        continue
                    slug = self._slug_from_url(href)
                    if slug and not any(r["id"] == slug for r in results):
                        results.append({"id": slug, "title": title})
                    if len(results) >= limit:
                        break
            
            # If standard search yields no results (e.g. ToonGod disabled it), try Madara AJAX search
            if not results:
                data = {"action": "wp-manga-search-manga", "title": query}
                ajax_resp = await self._fetch_post(f"{self.base_url}/wp-admin/admin-ajax.php", data)
                if ajax_resp:
                    try:
                        import json
                        js_data = json.loads(ajax_resp)
                        if js_data.get("success") and js_data.get("data"):
                            for item in js_data["data"]:
                                href = item.get("url", "")
                                title = item.get("title", "")
                                if not href or not title:
                                    continue
                                slug = self._slug_from_url(href)
                                if slug and not any(r["id"] == slug for r in results):
                                    results.append({"id": slug, "title": title})
                                if len(results) >= limit:
                                    break
                    except Exception as parse_err:
                        logger.debug(f"search_manga ajax parse error: {parse_err}")

            return results
        except Exception as e:
            logger.error(f"{self.__class__.__name__} search_manga: {e}")
            return []

    # ── manga info ─────────────────────────────────────────────────────────────

    async def get_manga_info(self, manga_id: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/{self.manga_path}/{manga_id}/"
            html = await self._fetch(url)
            if not html:
                return None
            soup = self._soup(html)

            title = (
                (soup.select_one(".post-title h1") or
                 soup.select_one(".manga-title") or
                 soup.select_one("h1"))
            )
            title = title.get_text(strip=True) if title else manga_id

            desc_el = soup.select_one(".summary__content, .description-summary, .manga-excerpt")
            desc = desc_el.get_text(strip=True) if desc_el else ""

            cover_el = soup.select_one(".summary_image img, .manga-thumbnail img, .tab-summary img")
            cover = ""
            if cover_el:
                cover = (cover_el.get("data-src") or cover_el.get("data-lazy-src")
                         or cover_el.get("src") or "")

            return {"id": manga_id, "title": title, "description": desc, "cover": cover}
        except Exception as e:
            logger.error(f"{self.__class__.__name__} get_manga_info: {e}")
            return None

    # ── chapter list ───────────────────────────────────────────────────────────

    async def get_manga_chapters(self, manga_id: str, limit: int = 500,
                                  offset: int = 0, languages=None) -> List[Dict]:
        try:
            url = f"{self.base_url}/{self.manga_path}/{manga_id}/"
            html = await self._fetch(url)
            if not html:
                return []
            soup = self._soup(html)

            rows = soup.select(self.CHAPTER_ROW_SEL)
            # If chapters are missing, try AJAX (Madara "load more" pattern)
            if not rows:
                html2 = await self._fetch_madara_chapters_ajax(manga_id, soup)
                if html2:
                    soup2 = self._soup(html2)
                    rows = soup2.select(self.CHAPTER_ROW_SEL)

            results = []
            for row in rows:
                a = row.select_one("a")
                if not a:
                    continue
                href = a.get("href", "")
                text = a.get_text(strip=True)
                ch_slug = self._chapter_slug_from_url(href)
                if not ch_slug:
                    continue
                num_match = re.search(r"([\d]+(?:\.\d+)?)", text)
                chapter_num = num_match.group(1) if num_match else ch_slug
                results.append({
                    "id": f"{manga_id}|{ch_slug}",
                    "chapter": chapter_num,
                    "title": text,
                    "language": "en",
                    "volume": "",
                })

            results.reverse()  # oldest first
            return results[offset: offset + limit]
        except Exception as e:
            logger.error(f"{self.__class__.__name__} get_manga_chapters: {e}")
            return []

    async def _fetch_madara_chapters_ajax(self, manga_id: str, soup: BeautifulSoup) -> Optional[str]:
        """Try Madara's AJAX chapter loader when chapters aren't in the page HTML."""
        try:
            # Extract WordPress post ID from the page
            post_id = None
            for el in soup.select("[id^=manga-chapters-holder]"):
                post_id = el.get("data-id")
                break
            if not post_id:
                script = soup.find("script", string=re.compile(r'"manga_id"\s*:\s*"(\d+)"'))
                if script:
                    m = re.search(r'"manga_id"\s*:\s*"(\d+)"', script.string)
                    if m:
                        post_id = m.group(1)
            if not post_id:
                return None

            data = {
                "action": "manga_get_chapters",
                "manga": post_id,
            }
            return await _cffi_post(f"{self.base_url}/wp-admin/admin-ajax.php", data)
        except Exception as e:
            logger.debug(f"_fetch_madara_chapters_ajax: {e}")
            return None

    async def get_latest_chapters(self, manga_id: str, limit: int = 20,
                                   offset: int = 0) -> List[Dict]:
        return await self.get_manga_chapters(manga_id, limit=limit, offset=offset)

    # ── chapter info ───────────────────────────────────────────────────────────

    async def get_chapter_info(self, chapter_id: str) -> Optional[Dict]:
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
            num_match = re.search(r"chapter[_-]?([\d]+(?:[\-\.]\d+)?)", ch_slug, re.I)
            chapter_num = num_match.group(1).replace("-", ".") if num_match else ch_slug
            info = await self.get_manga_info(manga_slug)
            return {
                "id": chapter_id,
                "chapter": chapter_num,
                "title": f"Chapter {chapter_num}",
                "manga_title": (info or {}).get("title", ""),
            }
        except Exception as e:
            logger.error(f"{self.__class__.__name__} get_chapter_info: {e}")
            return None

    # ── chapter images ─────────────────────────────────────────────────────────

    async def get_chapter_images(self, chapter_id: str) -> List[str]:
        try:
            manga_slug, ch_slug = chapter_id.split("|", 1)
            url = f"{self.base_url}/{self.manga_path}/{manga_slug}/{ch_slug}/"
            html = await self._fetch(url)
            if not html:
                return []
            soup = self._soup(html)
            images = []
            for img in soup.select(self.IMAGE_SEL):
                src = (img.get("data-src") or img.get("data-lazy-src") or img.get("src") or "").strip()
                if src.startswith("http") and src not in images:
                    images.append(src)
            return images
        except Exception as e:
            logger.error(f"{self.__class__.__name__} get_chapter_images: {e}")
            return []

    # ── URL utilities ──────────────────────────────────────────────────────────

    def _slug_from_url(self, url: str) -> Optional[str]:
        """Extract manga slug from a Madara manga URL (handles /manga/, /webtoon/, /series/ paths)."""
        url = url.rstrip("/")
        # Try configured path first, then common alternatives, then last segment
        for path in (self.manga_path, "manga", "webtoon", "series", "manhwa"):
            m = re.search(rf"/{re.escape(path)}/([^/?#]+)$", url)
            if m:
                return m.group(1)
        m = re.search(r"/([^/?#]+)$", url)
        return m.group(1) if m else None

    def _chapter_slug_from_url(self, url: str) -> Optional[str]:
        """Extract chapter slug from a Madara chapter URL."""
        url = url.rstrip("/")
        for path in (self.manga_path, "manga", "webtoon", "series", "manhwa"):
            m = re.search(rf"/{re.escape(path)}/[^/]+/([^/?#]+)$", url)
            if m:
                return m.group(1)
        m = re.search(r"/([^/?#]+)$", url)
        return m.group(1) if m else None
