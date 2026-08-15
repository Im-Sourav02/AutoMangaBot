# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from Plugins.downloading import Downloader
from Plugins.Sites.mangadex import MangaDexAPI
from Plugins.Sites.mangaforest import MangaForestAPI
from Database.database import Seishiro
from Database.subscriptions import SubscriptionDB
from Plugins.helper import (
    edit_msg_with_pic, get_styled_text,
    user_states, user_data,
    WAITING_CHAPTER_INPUT, WAITING_BATCH_NUMBER,
)

import logging
import asyncio
import difflib
import shutil
from pathlib import Path
import os
import re

logger = logging.getLogger(__name__)

# ─── Chapter-ID registry ───────────────────────────────────────────────────────
# Telegram's callback_data is capped at 64 bytes.  For sources whose chapter
# IDs can be much longer (e.g. OmegaScans: "12345|series-slug|67890|ch-slug")
# we store the full ID here and expose only a compact numeric token.
_chapter_id_registry: dict[int, str] = {}   # token -> full_chapter_id
_chapter_id_counter: int = 0

def _register_chapter_id(full_id: str) -> int:
    """Store full_id and return a short integer token."""
    global _chapter_id_counter
    _chapter_id_counter += 1
    _chapter_id_registry[_chapter_id_counter] = full_id
    return _chapter_id_counter

def _resolve_chapter_id(token: int) -> str | None:
    """Look up a token and return the full chapter ID, or None if expired."""
    return _chapter_id_registry.get(token)


from Plugins.Sites.mangakakalot import MangakakalotAPI
from Plugins.Sites.allmanga import AllMangaAPI
from Plugins.Sites.comick import ComickAPI
from Plugins.Sites.atsumaru import AtsumaruAPI
from Plugins.Sites.omegascans import OmegaScansAPI

# Madara-based
from Plugins.Sites.toonily import ToonilyAPI
from Plugins.Sites.manhwaread import ManhwaReadAPI
from Plugins.Sites.weebtoon import WebtoonScanAPI
from Plugins.Sites.hentai20 import Hentai20API
from Plugins.Sites.manga18fx import Manga18fxAPI
from Plugins.Sites.manga18club import Manga18clubAPI
from Plugins.Sites.manhwa18 import Manhwa18API

from Plugins.Sites.manhwahub import ManhwaHubAPI
from Plugins.Sites.manytoon import ManyToonAPI
from Plugins.Sites.hiperdex import HiperdexAPI
from Plugins.Sites.mangaforfree import MangaForFreeAPI
from Plugins.Sites.mangadistrict import MangaDistrictAPI
# Custom scrapers
from Plugins.Sites.manganato import MangaNatoAPI
from Plugins.Sites.asurascans import AsuraScansAPI
from Plugins.Sites.vortexscans import VortexScansAPI
from Plugins.Sites.toongod import ToonGodAPI
from Plugins.Sites.hivetoons import HiveToonsAPI

SITES = {
    # Original sources
    "MangaDex": MangaDexAPI,
    "MangaForest": MangaForestAPI,
    "Mangakakalot": MangakakalotAPI,
    "AllManga": AllMangaAPI,
    "Comick": ComickAPI,
    "Atsumaru": AtsumaruAPI,
    "OmegaScans": OmegaScansAPI,

    "WebCentral": None,
    # Madara-based sources
    "Toonily": ToonilyAPI,
    "ManhwaRead": ManhwaReadAPI,
    # WebtoonScan removed — domain dead
    "Hentai20": Hentai20API,
    "Manga18fx": Manga18fxAPI,
    "Manga18Club": Manga18clubAPI,
    "Manhwa18": Manhwa18API,

    "ManhwaHub": ManhwaHubAPI,
    "ManyToon": ManyToonAPI,
    "Hiperdex": HiperdexAPI,
    "MangaForFree": MangaForFreeAPI,
    "MangaDistrict": MangaDistrictAPI,
    # Custom scrapers
    "MangaNato": MangaNatoAPI,
    "AsuraScans": AsuraScansAPI,
    "VortexScans": VortexScansAPI,
    "ToonGod": ToonGodAPI,
    "HiveToons": HiveToonsAPI,
}

try:
    from Plugins.Sites.webcentral import WebCentralAPI
    SITES["WebCentral"] = WebCentralAPI
except ImportError:
    pass

def get_api_class(source):
    # Try exact match first, then case-insensitive
    cls = SITES.get(source)
    if cls is not None:
        return cls
    for key, val in SITES.items():
        if key.lower() == source.lower():
            return val
    return None


def check_search_state(_, __, m):
    """Return True only when the message should be treated as a search query."""
    if m.text and m.text.startswith('/'):
        return False
    uid = m.from_user.id
    state = user_states.get(uid)
    # Pass through only if: no active state, OR in the chapter-range-input sub-state
    if state is None:
        return True
    if state == WAITING_CHAPTER_INPUT:
        return True
    # WAITING_BATCH_NUMBER and any other state must NOT fall through to search
    return False

search_filter = filters.create(check_search_state)

@Client.on_message(filters.text & filters.private & search_filter & ~filters.command(["start", "help", "settings", "search"]))
async def message_handler(client, message):
    user_id = message.from_user.id
    
    if user_id in user_states:
        if user_states[user_id] == WAITING_CHAPTER_INPUT:
            await custom_dl_input_handler(client, message)
            return
        return

    # If no state is active, treat the message as a manga search
    query = message.text.strip()
    if len(query) < 2:
        await message.reply("❌ query too short.")
        return
    
    buttons = []
    row = []
    for source in SITES.keys():
        if SITES[source] is not None:
            row.append(InlineKeyboardButton(source, callback_data=f"search_src_{source}_{query[:30]}"))
            if len(row) == 2:  # 2 buttons per row
                buttons.append(row)
                row = []
    
    if row:
        buttons.append(row)
    
    if not buttons:
        await message.reply("❌ no sources available.")
        return
        
    buttons.append([InlineKeyboardButton("🌐 Search All Sources", callback_data=f"search_all_{query[:30]}")])
    buttons.append([InlineKeyboardButton("❌ close", callback_data="stats_close")])
    
    await message.reply(
        f"<b>🔍 search:</b> <code>{query}</code>\n\nselect a source to search in:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )

@Client.on_message(filters.command("search") & filters.private)
async def search_command_handler(client, message):
    """Handle /search command for manga queries"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("❌ usage: /search <query>")
        return
    
    query = parts[1].strip()
    if len(query) < 2:
        await message.reply("❌ query too short.")
        return
    
    buttons = []
    row = []
    for source in SITES.keys():
        if SITES[source] is not None:
            row.append(InlineKeyboardButton(source, callback_data=f"search_src_{source}_{query[:30]}"))
            if len(row) == 2:  # 2 buttons per row
                buttons.append(row)
                row = []
    
    if row:
        buttons.append(row)
    
    if not buttons:
        await message.reply("❌ no sources available.")
        return
        
    buttons.append([InlineKeyboardButton("🌐 Search All Sources", callback_data=f"search_all_{query[:30]}")])
    buttons.append([InlineKeyboardButton("❌ close", callback_data="stats_close")])
    
    await message.reply(
        f"<b>🔍 search:</b> <code>{query}</code>\n\nselect a source to search in:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex("^search_src_"))
async def search_source_cb(client, callback_query):
    parts = callback_query.data.split("_", 3)
    source = parts[2]
    query = parts[3] # this might be truncated, but we used Message text in original. 
    
    api_class = get_api_class(source)
    if not api_class:
        await callback_query.answer("source not available", show_alert=True)
        return
        
    status_msg = await callback_query.message.edit_text(f"<i>🔍 Searching {source}...</i>", parse_mode=enums.ParseMode.HTML)
    
    async with api_class(Config) as api:
        results = await api.search_manga(query)
    
    if not results:
        await status_msg.edit_text(f"❌ no results found in {source}.")
        return

    buttons = []
    for m in results[:10]:  # top 10
        title = m['title'][:35]
        # Telegram callback_data limit is 64 bytes — guard it
        cb = f"view_{source}_{m['id']}"
        if len(cb.encode()) > 62:
            cb = f"view_{source}_{m['id'][:62 - len(source) - 6]}"
        buttons.append([InlineKeyboardButton(title, callback_data=cb)])
    
    buttons.append([InlineKeyboardButton("❌ close", callback_data="stats_close")])
    
    await status_msg.edit_text(
        f"<b>found {len(results)} results in {source}:</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex("^search_all_"))
async def search_all_cb(client, callback_query):
    """Search all available sources concurrently and aggregate results."""
    query = callback_query.data[len("search_all_"):]
    status_msg = await callback_query.message.edit_text(
        f"<i>🌐 Searching all sources for <b>{query}</b>...</i>",
        parse_mode=enums.ParseMode.HTML
    )

    active_sources = {name: cls for name, cls in SITES.items() if cls is not None}

    async def search_one(name, cls):
        try:
            async with cls(Config) as api:
                results = await api.search_manga(query, limit=5)
            return name, results
        except Exception as e:
            logger.warning(f"search_all: {name} failed: {e}")
            return name, []

    tasks = [search_one(name, cls) for name, cls in active_sources.items()]
    all_results = await asyncio.gather(*tasks)

    buttons = []
    found_any = False
    sources_shown = 0
    for source_name, results in all_results:
        if not results:
            continue
        found_any = True
        if sources_shown >= 10:  # cap: at most 10 sources to keep button count < 40
            continue
        sources_shown += 1
        # Section label row
        buttons.append([InlineKeyboardButton(f"── {source_name} ──", callback_data="noop")])
        for m in results[:2]:  # 2 per source (10 sources × 2 = 20 result buttons max)
            title = m['title'][:35]
            # Guard 64-byte callback_data limit
            cb = f"view_{source_name}_{m['id']}"
            if len(cb.encode()) > 62:
                cb = f"view_{source_name}_{m['id'][:62 - len(source_name) - 6]}"
            buttons.append([InlineKeyboardButton(title, callback_data=cb)])

    if not found_any:
        await status_msg.edit_text(f"❌ no results found in any source for <b>{query}</b>.", parse_mode=enums.ParseMode.HTML)
        return

    buttons.append([InlineKeyboardButton("❌ close", callback_data="stats_close")])
    await status_msg.edit_text(
        f"<b>🌐 Search All — results for:</b> <code>{query}</code>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex("^noop$"))
async def noop_cb(client, callback_query):
    await callback_query.answer()


@Client.on_callback_query(filters.regex("^view_"))
async def view_manga_cb(client, callback_query):
    parts = callback_query.data.split("_", 2)
    source = parts[1]
    manga_id = parts[2]
    
    api_class = get_api_class(source)
    if not api_class: return

    async with api_class(Config) as api:
        info = await api.get_manga_info(manga_id)
    
    if not info:
        await callback_query.answer("error fetching details", show_alert=True)
        return

    # Check subscription status
    user_id = callback_query.from_user.id
    subs = await Seishiro.subs_db.get_user_subscriptions(user_id)
    is_subscribed = any(sub.get('url') == manga_id and sub.get('source') == source for sub in subs)

    caption = (
        f"<blockquote><b>{info['title']}</b></blockquote>\n\n"
        f"<b>Status:</b> {info.get('status', 'N/A')}\n"
        f"<b>Genres:</b> {info.get('genres', 'N/A')}\n\n"
        f"<b>Description:</b>\n"
        f"<blockquote>{info.get('description', 'N/A')[:300]}...</blockquote>"
    )
    
    # Safe title for callback (max 64 bytes total)
    safe_title = info['title'][:20]
    
    if is_subscribed:
        sub_btn = InlineKeyboardButton("🔕 UNSUBSCRIBE 🔕", callback_data=f"unsub_{source}_{manga_id}")
    else:
        # We need to pass title safely or store it temporarily, but callback limit is tight
        # Since we just have source and manga_id, the sub handler will need to fetch it again if it needs the title.
        sub_btn = InlineKeyboardButton("🔔 SUBSCRIBE 🔔", callback_data=f"sub_{source}_{manga_id}")
        
    buttons = [
        [
            InlineKeyboardButton("▶ CHAPTERS ◀", callback_data=f"chapters_{source}_{manga_id}_0"),
            InlineKeyboardButton("▶ 𝖡𝖺𝗍𝖼𝗁 ◀", callback_data=f"custom_dl_{source}_{manga_id}")
        ],
        [sub_btn],
        [
            InlineKeyboardButton("(っ◐◡◐)っ", callback_data="noop"), 
            InlineKeyboardButton("| CLOSE |", callback_data="stats_close")
        ]
    ]
    
    msg = callback_query.message
    
    # Check if there is a cover image available in info
    cover_url = info.get('cover')
    try:
        if cover_url:
            await edit_msg_with_pic(msg, caption, InlineKeyboardMarkup(buttons), pic=cover_url)
        else:
            await edit_msg_with_pic(msg, caption, InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error editing manga card: {e}")
        await edit_msg_with_pic(msg, caption, InlineKeyboardMarkup(buttons))



@Client.on_callback_query(filters.regex("^chapters_"))
async def chapters_list_cb(client, callback_query):
    """
    Shows a paginated chapter list.  callback_data format:
        chapters_{source}_{manga_id}_{offset}
    manga_id may itself contain underscores (e.g. Madara slugs), so we
    treat everything from index-2 to the last segment as the manga_id and
    the LAST segment as the numeric offset.
    """
    try:
        raw = callback_query.data  # e.g. "chapters_OmegaScans_12345|slug_0"
        # Split on "_" but limit to 3 parts: prefix, source, rest
        _, source, rest = raw.split("_", 2)
        # The last token after the final "_" is the integer offset
        last_underscore = rest.rfind("_")
        manga_id = rest[:last_underscore]
        offset   = int(rest[last_underscore + 1:])
    except Exception as parse_err:
        logger.error(f"chapters_list_cb parse error: {parse_err} | data={callback_query.data!r}")
        await callback_query.answer("❌ Invalid callback data", show_alert=True)
        return

    API = get_api_class(source)
    if not API:
        await callback_query.answer("❌ Source not found", show_alert=True)
        return

    page_size = 10

    try:
        async with API(Config) as api:
            # Fetch chapters + cover in one context
            chapters = await api.get_manga_chapters(manga_id, limit=page_size, offset=offset)
            info = await api.get_manga_info(manga_id)
    except Exception as e:
        logger.error(f"chapters_list_cb fetch error: {e}", exc_info=True)
        await callback_query.answer("❌ Failed to fetch chapters.", show_alert=True)
        return

    if not chapters and offset == 0:
        await callback_query.answer("No chapters found.", show_alert=True)
        return
    elif not chapters:
        await callback_query.answer("No more chapters.", show_alert=True)
        return

    cover_url = (info or {}).get("cover")
    current_page = (offset // page_size) + 1

    # ── Chapter buttons — use token registry to stay within 64-byte limit ──
    buttons = []
    row = []
    for ch in chapters:
        ch_num   = ch["chapter"]
        btn_text = f"Chapter {ch_num}"
        token    = _register_chapter_id(ch["id"])
        # callback: dl_ask_{source}_{manga_id}_{token}
        # Use a stable separator for manga_id: keep it as-is but build cb carefully
        cb = f"dl_ask_{source}_{manga_id}_{token}"
        # Safety: if still over 64 bytes (very long manga_id), shorten token only
        if len(cb.encode()) > 64:
            # Token is just an int so it's always tiny — manga_id must be the culprit;
            # Shorten the manga_id portion in the callback (token still resolves the real ID)
            max_mid = 64 - len(f"dl_ask_{source}__") - len(str(token))
            cb = f"dl_ask_{source}_{manga_id[:max_mid]}_{token}"
        row.append(InlineKeyboardButton(btn_text, callback_data=cb))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # ── Pagination nav ──
    nav_row_1 = []
    nav_row_2 = []
    if offset >= page_size:
        nav_row_1.append(InlineKeyboardButton("<< Prev", callback_data=f"chapters_{source}_{manga_id}_{offset - page_size}"))
    if offset >= page_size * 2:
        nav_row_1.insert(0, InlineKeyboardButton("<< 2x",  callback_data=f"chapters_{source}_{manga_id}_{offset - page_size*2}"))
    if offset >= page_size * 5:
        nav_row_1.insert(0, InlineKeyboardButton("<< 5x",  callback_data=f"chapters_{source}_{manga_id}_{offset - page_size*5}"))

    nav_row_2.append(InlineKeyboardButton("Next >>", callback_data=f"chapters_{source}_{manga_id}_{offset + page_size}"))
    nav_row_2.append(InlineKeyboardButton("2x >>",  callback_data=f"chapters_{source}_{manga_id}_{offset + page_size*2}"))
    nav_row_2.append(InlineKeyboardButton("5x >>",  callback_data=f"chapters_{source}_{manga_id}_{offset + page_size*5}"))

    if nav_row_1: buttons.append(nav_row_1)
    if nav_row_2: buttons.append(nav_row_2)

    # ── Subscription status ──
    user_id = callback_query.from_user.id
    subs = await Seishiro.subs_db.get_user_subscriptions(user_id)
    is_subscribed = any(sub.get("url") == manga_id and sub.get("source") == source for sub in subs)
    sub_text = "🔕 UNSUBSCRIBE 🔕" if is_subscribed else "🔔 SUBSCRIBE 🔔"
    sub_cb   = f"unsub_{source}_{manga_id}"  if is_subscribed else f"sub_{source}_{manga_id}"

    # ── Bottom action row (guard 64-byte limit) ──
    user_settings  = await Seishiro.settings_db.get_settings(user_id)
    autobat_cb = f"autobat_{source}_{manga_id}"
    dl_pg_cb   = f"dl_pg_{source}_{manga_id}_{offset}"
    dl_all_cb  = f"dl_all_{source}_{manga_id}"

    def _guard(cb, prefix, suffix=""):
        if len(cb.encode("utf-8")) > 64:
            max_mid = 64 - len(prefix) - len(suffix) - 2
            short   = manga_id[:max(max_mid, 4)]
            return f"{prefix}_{short}{suffix}"
        return cb

    autobat_cb = _guard(autobat_cb, f"autobat_{source}")
    dl_pg_cb   = _guard(dl_pg_cb,   f"dl_pg_{source}",  f"_{offset}")
    dl_all_cb  = _guard(dl_all_cb,  f"dl_all_{source}")

    buttons.extend([
        [InlineKeyboardButton("Auto Batch", callback_data=autobat_cb)],
        [
            InlineKeyboardButton("⬆ FULL PAGE ⬆", callback_data=dl_pg_cb),
            InlineKeyboardButton("⬆ ALL CHAPTERS ⬆", callback_data=dl_all_cb),
        ],
        [InlineKeyboardButton(sub_text, callback_data=sub_cb)],
        [
            InlineKeyboardButton("BACK", callback_data=f"view_{source}_{manga_id}"),
            InlineKeyboardButton("| CLOSE |", callback_data="stats_close"),
        ],
    ])

    caption_text = f"<b>Chapter Selection:</b>\nPage: {current_page}"

    try:
        await edit_msg_with_pic(
            callback_query.message, caption_text,
            InlineKeyboardMarkup(buttons), pic=cover_url
        )
    except Exception as e:
        logger.error(f"chapters_list_cb edit error: {e}", exc_info=True)
        # Don't silently delete — at least answer the callback so the spinner stops
        await callback_query.answer("⚠️ Failed to display chapters.", show_alert=True)



# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat


@Client.on_callback_query(filters.regex("^custom_dl_"))
async def custom_dl_start_cb(client, callback_query):
    parts = callback_query.data.split("_")
    source = parts[2]
    manga_id = "_".join(parts[3:])
    
    user_id = callback_query.from_user.id
    
    user_states[user_id] = WAITING_CHAPTER_INPUT
    user_data[user_id] = {
        'source': source,
        'manga_id': manga_id
    }
    
    await callback_query.message.reply_text(
        "<b>⬇ custom download mode</b>\n\n"
        "Please enter the Chapter Number you want to download.\n"
        "You can download a single chapter or a range.\n\n"
        "<b>Examples:</b>\n"
        "<code>5</code> (Download Chapter 5)\n"
        "<code>10-20</code> (Download Chapters 10 to 20)\n\n"
        "<i>Downloads will be sent to your Private Chat.</i>",
        parse_mode=enums.ParseMode.HTML
    )
    await callback_query.answer()

async def custom_dl_input_handler(client, message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    if user_id in user_states:
        del user_states[user_id]
        
    data = user_data.get(user_id)
    if not data:
        await message.reply("❌ session expired. please search again.")
        return
        
    source = data['source']
    manga_id = data['manga_id']
    
    target_chapters = [] # List of floats/strings numbers
    is_range = False
    combine_mode = False
    
    if text.lower().endswith(" c"):
        combine_mode = True
        text = text[:-2].strip()
    
    try:
        if "-" in text:
            is_range = True
            start, end = map(float, text.split("-"))
            range_min = min(start, end)
            range_max = max(start, end)
        else:
            target_chapters.append(float(text))
    except ValueError:
        await message.reply("❌ invalid format. please enter numbers like `5`, `10-20`, or `10-20 c`.")
        return

    status_msg = await message.reply("<i>⏳ fetching chapter list...</i>", parse_mode=enums.ParseMode.HTML)
    
    API = get_api_class(source)
    all_chapters = []
    
    
    async with API(Config) as api:
        offset = 0
        while True:
            batch = await api.get_manga_chapters(manga_id, limit=100, offset=offset)
            if not batch: break
            all_chapters.extend(batch)
            if len(batch) < 100: break
            offset += 100
            if len(all_chapters) > 2000: break # Safety Break
            
    if not all_chapters:
        await status_msg.edit_text("❌ no chapters found.")
        return

    to_download = []
    for ch in all_chapters:
        try:
            ch_num = float(ch['chapter'])
            if is_range:
                if range_min <= ch_num <= range_max:
                    to_download.append(ch)
            else:
                if ch_num in target_chapters:
                     to_download.append(ch)
        except:
             pass # Skip non-numeric chapters
             
    if not to_download:
        await status_msg.edit_text(f"❌ no chapters found for input: {text}")
        return

    await status_msg.edit_text(f"✅ Found {len(to_download)} chapters. Starting download...")
    
    to_download.sort(key=lambda x: float(x['chapter']))
    
    if combine_mode and len(to_download) > 1:
        from Plugins.task_manager import task_manager
        pos = await task_manager.add_task(user_id, message.chat.id, execute_download_combined, client, message.chat.id, source, manga_id, to_download, user_id)
        await status_msg.edit_text(f"✅ Added {len(to_download)} chapters (combined) to queue. Position: {pos}")
    else:
        from Plugins.task_manager import task_manager
        for ch in to_download:
            import Plugins.helper as helper
            if helper.CANCEL_TASKS.get(message.chat.id, False):
                helper.CANCEL_TASKS[message.chat.id] = False
                break
            await task_manager.add_task(user_id, message.chat.id, execute_download, client, message.chat.id, source, manga_id, ch['id'], user_id)
        await status_msg.edit_text(f"✅ Added {len(to_download)} chapters to queue.")


async def execute_download_combined(client, target_chat_id, source, manga_id, chapters_to_download, user_id):
    import Plugins.helper as helper
    import shutil
    import asyncio
    import re
    from pathlib import Path
    import difflib
    from pyrogram import enums
    from config import Config
    from Plugins.downloading import Downloader

    from Database.database import Seishiro
    
    status_chat_id = target_chat_id
    status_msg = await client.send_message(status_chat_id, f"<i>⏳ 𝘐𝘯𝘪𝘵𝘪𝘢𝘭𝘪𝘻𝘪𝘯𝘨 𝘊𝘰𝘮𝘣𝘪𝘯𝘦𝘥 𝘋𝘰𝘸𝘯𝘭𝘰𝘢𝘥 𝘧𝘰𝘳 {len(chapters_to_download)} 𝘊𝘩𝘢𝘱𝘵𝘦𝘳𝘴...</i>", parse_mode=enums.ParseMode.HTML)
    
    try:
        API = get_api_class(source)
        all_images = []
        manga_title = ""
        
        async with API(Config) as api:
            m_info = await api.get_manga_info(manga_id)
            if m_info: manga_title = m_info.get('title', manga_id)
            else: manga_title = manga_id
            
            for ch in chapters_to_download:
                if helper.CANCEL_TASKS.get(target_chat_id, False):
                    helper.CANCEL_TASKS[target_chat_id] = False
                    await status_msg.edit_text("❌ 𝘋𝘰𝘸𝘯𝘭𝘰𝘢𝘥 𝘊𝘢𝘯𝘤𝘦𝘭𝘭𝘦𝘥.")
                    return
                images = await api.get_chapter_images(ch['id'])
                if images:
                    all_images.extend(images)
                
        if not all_images:
            await status_msg.edit_text(f"❌ 𝘕𝘰 𝘐𝘮𝘢𝘨𝘦𝘴 𝘍𝘰𝘶𝘯𝘥 𝘪𝘯 𝘵𝘩𝘦 𝘚𝘦𝘭𝘦𝘤𝘵𝘦𝘥 𝘊𝘩𝘢𝘱𝘵𝘦𝘳𝘴.")
            return
            
        safe_manga_id = re.sub(r'[\\/:*?"<>|]', '_', manga_id)
        ch_range_str = f"{chapters_to_download[0]['chapter']}-{chapters_to_download[-1]['chapter']}"
        chapter_dir = Path(Config.DOWNLOAD_DIR) / f"{source}_{safe_manga_id}" / f"ch_{ch_range_str}"
        chapter_dir.mkdir(parents=True, exist_ok=True)
        
        await status_msg.edit_text(f"<i>⬇ downloading {len(all_images)} pages...</i>", parse_mode=enums.ParseMode.HTML)
        
        async with Downloader(Config) as downloader:
            dl_referer = getattr(api, 'base_url', None) or getattr(api, '_base_url', None)
            dl_headers = {'Referer': dl_referer.rstrip('/') + '/'} if dl_referer else None
            if not await downloader.download_images(all_images, chapter_dir, headers=dl_headers):
                 await status_msg.edit_text("❌ 𝘋𝘰𝘸𝘯𝘭𝘰𝘢𝘥 𝘍𝘢𝘪𝘭𝘦𝘥.")
                 return
            
            await status_msg.edit_text(f"<i>𝘗𝘳𝘰𝘤𝘦𝘴𝘴𝘪𝘯𝘨 𝘍𝘪𝘭𝘦𝘴...</i>", parse_mode=enums.ParseMode.HTML)
            
            user_settings = await Seishiro.settings_db.get_settings(user_id)
            file_type = user_settings.get("file_type", "PDF")
            quality = await Seishiro.get_config("image_quality")
            
            banner_1 = await Seishiro.get_config("banner_image_1")
            banner_2 = await Seishiro.get_config("banner_image_2")
            
            intro_p = None; outro_p = None
            if banner_1:
                 intro_p = chapter_dir.parent / "intro.jpg"
                 try: await client.download_media(banner_1, file_name=str(intro_p))
                 except: intro_p = None
            if banner_2:
                 outro_p = chapter_dir.parent / "outro.jpg"
                 try: await client.download_media(banner_2, file_name=str(outro_p))
                 except: outro_p = None

            final_path = await asyncio.to_thread(
                 downloader.create_chapter_file,
                 chapter_dir, manga_title, ch_range_str, "Combined Chapters",
                 file_type, intro_p, outro_p, quality
            )
            
            if intro_p and intro_p.exists(): intro_p.unlink()
            if outro_p and outro_p.exists(): outro_p.unlink()
            
            if not final_path:
                 await status_msg.edit_text("❌ 𝘍𝘢𝘪𝘭𝘦𝘥 𝘵𝘰 𝘊𝘳𝘦𝘢𝘵𝘦 𝘍𝘪𝘭𝘦.")
                 return
            
            await status_msg.edit_text(f"<i>𝘜𝘱𝘭𝘰𝘢𝘥𝘪𝘯𝘨...</i>", parse_mode=enums.ParseMode.HTML)
            
            filename_format = await Seishiro.get_format()
            formatted_filename = filename_format \
                .replace("{manga_name}", manga_title) \
                .replace("{chapter}", ch_range_str) \
                .replace("{manga_title}", manga_title) \
                .replace("{chapter_num}", ch_range_str) \
                .replace("{chapter_title}", "Combined Chapters")
            safe_filename = "".join(c for c in formatted_filename if c.isalnum() or c in (' ', '-', '_', '.', '⌯', '[', ']', '@'))[:100].rstrip()
            file_ext = final_path.suffix
            if not safe_filename.endswith(file_ext):
                safe_filename += file_ext
            
            user_caption = await Seishiro.get_caption()
            if user_caption:
                caption = user_caption \
                    .replace("{manga_title}", manga_title) \
                    .replace("{chapter_num}", ch_range_str) \
                    .replace("{file_name}", safe_filename) \
                    .replace("{manga_name}", manga_title) \
                    .replace("{chapter}", ch_range_str) \
                    .replace("{chapter_title}", "Combined Chapters")
            else:
                caption = f"<b>{manga_title} - Ch {ch_range_str}</b>"
            
            custom_thumbnail = await Seishiro.get_config("custom_thumbnail")
            thumb_path = None
            if custom_thumbnail:
                try:
                    thumb_path = str(chapter_dir.parent / "thumb.jpg")
                    await client.download_media(custom_thumbnail, file_name=thumb_path)
                except Exception:
                    thumb_path = None
                    
            try:
                primary_chat = target_chat_id
                dump_channel = user_settings.get("dump_channel_id")
                if dump_channel:
                    primary_chat = dump_channel
                    
                msg = await client.send_document(
                    chat_id=primary_chat,
                    document=final_path,
                    caption=caption,
                    file_name=safe_filename,
                    thumb=thumb_path,
                    parse_mode=enums.ParseMode.HTML
                )
                
                # Check Auto Upload Channel
                should_send_to_aup = False
                auto_upload_id = None
                aup_channels = await Seishiro.get_auto_upload_channels(user_id)
                for chan in aup_channels:
                    c_title = chan.get('title', '').lower()
                    if difflib.SequenceMatcher(None, manga_title.lower(), c_title).ratio() > 0.8 \
                        or manga_title.lower() in c_title or c_title in manga_title.lower():
                        auto_upload_id = chan.get('channel_id')
                        should_send_to_aup = True
                        break
                        
                if should_send_to_aup and auto_upload_id:
                    try:
                        if msg and msg.document:
                            await client.send_document(auto_upload_id, msg.document.file_id, caption=caption)
                        else:
                            await client.send_document(auto_upload_id, final_path, caption=caption)
                    except Exception as e:
                        logger.error(f"𝘍𝘢𝘪𝘭𝘦𝘥 𝘵𝘰 𝘚𝘦𝘯𝘥 𝘵𝘰 𝘈𝘶𝘵𝘰 𝘜𝘱𝘭𝘰𝘢𝘥 𝘊𝘩𝘢𝘯𝘯𝘦𝘭 {auto_upload_id}: {e}")
                
            except Exception as e:
                logger.error(f"𝘜𝘱𝘭𝘰𝘢𝘥 𝘍𝘢𝘪𝘭𝘦𝘥: {e}")
                try: await status_msg.edit_text("❌ 𝘍𝘢𝘪𝘭𝘦𝘥 𝘵𝘰 𝘜𝘱𝘭𝘰𝘢𝘥 𝘍𝘪𝘭𝘦.")
                except Exception: pass
            
            if thumb_path and Path(thumb_path).exists():
                Path(thumb_path).unlink()
            
            shutil.rmtree(chapter_dir, ignore_errors=True)
            if final_path.exists(): final_path.unlink()
            
            await status_msg.delete() 

    except Exception as e:
        logger.error(f"DL Error: {e}", exc_info=True)
        try: await status_msg.edit_text(f"𝘌𝘳𝘳𝘰𝘳: {e}")
        except Exception: pass

async def execute_download(client, target_chat_id, source, manga_id, chapter_id, user_id, status_chat_id=None):
    """
    Downloads and uploads a chapter.
    status_chat_id: Where to send updates (if different from target).
    """
    if not status_chat_id: status_chat_id = target_chat_id
    
    status_msg = await client.send_message(status_chat_id, "<i>𝘐𝘯𝘪𝘵𝘪𝘢𝘭𝘪𝘻𝘪𝘯𝘨 𝘋𝘰𝘸𝘯𝘭𝘰𝘢𝘥...</i>", parse_mode=enums.ParseMode.HTML)
    
    try:
        API = get_api_class(source)
        async with API(Config) as api:
            meta = await api.get_chapter_info(chapter_id)
            if not meta:
                await status_msg.edit_text("𝘍𝘢𝘪𝘭𝘦𝘥 𝘵𝘰 𝘎𝘦𝘵 𝘊𝘩𝘢𝘱𝘵𝘦𝘳 𝘐𝘯𝘧𝘰.")
                return
            
            if not meta.get('manga_title'):
                 m_info = await api.get_manga_info(manga_id)
                 if m_info: meta['manga_title'] = m_info['title']

            images = await api.get_chapter_images(chapter_id)
            
        if not images:
            await status_msg.edit_text(f"❌ 𝘕𝘰 𝘐𝘮𝘢𝘨𝘦𝘴 𝘪𝘯 𝘵𝘩𝘪𝘴 𝘊𝘩𝘢𝘱𝘵𝘦𝘳 {meta.get('chapter', '?')}")
            return
            
        # Sanitize manga_id for use in directory names (Windows forbids | : * ? " < > \)
        safe_manga_id = re.sub(r'[\\/:*?"<>|]', '_', manga_id)
        chapter_dir = Path(Config.DOWNLOAD_DIR) / f"{source}_{safe_manga_id}" / f"ch_{meta['chapter']}"
        chapter_dir.mkdir(parents=True, exist_ok=True)
        
        await status_msg.edit_text(f"<i>𝘋𝘰𝘸𝘯𝘭𝘰𝘢𝘥𝘪𝘯𝘨 ⬇  {len(images)} 𝘱𝘢𝘨𝘦𝘴...</i>", parse_mode=enums.ParseMode.HTML)
        
        async with Downloader(Config) as downloader:
            # Pass the source site as Referer so hotlink-protected CDNs accept the request
            dl_referer = getattr(api, 'base_url', None) or getattr(api, '_base_url', None)
            dl_headers = {'Referer': dl_referer.rstrip('/') + '/'} if dl_referer else None
            if not await downloader.download_images(images, chapter_dir, headers=dl_headers):
                 await status_msg.edit_text("𝘋𝘰𝘸𝘯𝘭𝘰𝘢𝘥 𝘍𝘢𝘪𝘭𝘦𝘥.")
                 return
            
            await status_msg.edit_text("<i>⚙️ 𝘗𝘳𝘰𝘤𝘦𝘴𝘴𝘪𝘯𝘨 𝘗𝘋𝘍...</i>", parse_mode=enums.ParseMode.HTML)
            
            user_settings = await Seishiro.settings_db.get_settings(user_id)
            file_type = user_settings.get("file_type", "PDF")
            quality = await Seishiro.get_config("image_quality")
            
            banner_1 = await Seishiro.get_config("banner_image_1")
            banner_2 = await Seishiro.get_config("banner_image_2")
            
            intro_p = None; outro_p = None
            if banner_1:
                 intro_p = chapter_dir.parent / "intro.jpg"
                 try: await client.download_media(banner_1, file_name=str(intro_p))
                 except: intro_p = None
            if banner_2:
                 outro_p = chapter_dir.parent / "outro.jpg"
                 try: await client.download_media(banner_2, file_name=str(outro_p))
                 except: outro_p = None

            final_path = await asyncio.to_thread(
                 downloader.create_chapter_file,
                 chapter_dir, meta['manga_title'], meta['chapter'], meta['title'],
                 file_type, intro_p, outro_p, quality
            )
            
            if intro_p and intro_p.exists(): intro_p.unlink()
            if outro_p and outro_p.exists(): outro_p.unlink()
            
            if not final_path:
                 await status_msg.edit_text("𝘍𝘢𝘪𝘭𝘦𝘥 𝘵𝘰 𝘊𝘳𝘦𝘢𝘵𝘦 𝘍𝘪𝘭𝘦.")
                 return
            
            await status_msg.edit_text(f"<i>𝘜𝘱𝘭𝘰𝘢𝘥𝘪𝘯𝘨...⬆ </i>", parse_mode=enums.ParseMode.HTML)
            
            manga_title = meta['manga_title']
            chapter_num = meta['chapter']
            chapter_title = meta.get('title', '')
            
            # Filename from user's /set_format template ({manga_name}, {chapter})
            filename_format = await Seishiro.get_format()
            formatted_filename = filename_format \
                .replace("{manga_name}", manga_title) \
                .replace("{chapter}", str(chapter_num)) \
                .replace("{manga_title}", manga_title) \
                .replace("{chapter_num}", str(chapter_num)) \
                .replace("{chapter_title}", chapter_title or "")
            safe_filename = "".join(c for c in formatted_filename if c.isalnum() or c in (' ', '-', '_', '.', '⌯', '[', ']', '@'))[:100].rstrip()
            file_ext = final_path.suffix
            if not safe_filename.endswith(file_ext):
                safe_filename += file_ext
            
            # Caption from user's Caption setting (Seishiro.get_caption())
            # Template vars: {manga_title}, {chapter_num}, {file_name}
            user_caption = await Seishiro.get_caption()
            if user_caption:
                caption = user_caption \
                    .replace("{manga_title}", manga_title) \
                    .replace("{chapter_num}", str(chapter_num)) \
                    .replace("{file_name}", safe_filename) \
                    .replace("{manga_name}", manga_title) \
                    .replace("{chapter}", str(chapter_num)) \
                    .replace("{chapter_title}", chapter_title or "")
            else:
                caption = f"<b>{manga_title} - Ch {chapter_num}</b>"
            
            # Thumbnail from user's settings
            custom_thumbnail = await Seishiro.get_config("custom_thumbnail")
            thumb_path = None
            if custom_thumbnail:
                try:
                    thumb_path = str(chapter_dir.parent / "thumb.jpg")
                    await client.download_media(custom_thumbnail, file_name=thumb_path)
                except Exception:
                    thumb_path = None
            
            dump_channel = user_settings.get("dump_channel_id")
            
            primary_chat = dump_channel or target_chat_id
            
            try:
                # 1. Check if there is an Auto Upload Channel matching the manga title
                aup_channels = await Seishiro.get_auto_upload_channels(target_chat_id)
                auto_upload_id = None
                for chan in aup_channels:
                    c_title = chan.get('title', '').lower()
                    if not c_title: continue
                    ratio = difflib.SequenceMatcher(None, manga_title.lower(), c_title).ratio()
                    if ratio > 0.8 or manga_title.lower() in c_title or c_title in manga_title.lower():
                        auto_upload_id = chan.get('channel_id')
                        break

                should_send_to_aup = False
                subs_db = SubscriptionDB(Seishiro.database)

                if auto_upload_id:
                    # Check if user is subscribed to this manga
                    user_subs = await subs_db.get_user_subscriptions(target_chat_id)
                    sub_record = None
                    for sub in user_subs:
                        if sub.get('title', '').lower() == manga_title.lower() or sub.get('url') == meta.get('manga_id'):
                            sub_record = sub
                            break
                    
                    try:
                        current_ch_num = float(chapter_num)
                    except ValueError:
                        current_ch_num = 0.0

                    if not sub_record or not sub_record.get('latest_chapter'):
                        # If no subscription or no latest_chapter, we set it to this episode and create a sub for it
                        should_send_to_aup = True
                        if sub_record:
                            await subs_db.update_last_chapter(target_chat_id, sub_record['url'], sub_record['source'], str(chapter_num))
                            await subs_db.update_auto_upload_channel_id(target_chat_id, sub_record['url'], auto_upload_id)
                        else:
                            sub_data = {
                                "id": manga_id,
                                "title": manga_title,
                                "latest_chapter": str(chapter_num),
                                "auto_upload_channel_id": auto_upload_id
                            }
                            await subs_db.add_subscription(target_chat_id, sub_data, source)
                    else:
                        try:
                            latest_ch_num = float(sub_record['latest_chapter'])
                        except ValueError:
                            latest_ch_num = 0.0
                        
                        if current_ch_num > latest_ch_num:
                            should_send_to_aup = True
                            await subs_db.update_last_chapter(target_chat_id, sub_record['url'], sub_record['source'], str(chapter_num))
                            await subs_db.update_auto_upload_channel_id(target_chat_id, sub_record['url'], auto_upload_id)
                        else:
                            should_send_to_aup = False

                msg = await client.send_document(
                    chat_id=primary_chat,
                    document=final_path,
                    caption=caption,
                    file_name=safe_filename,
                    thumb=thumb_path,
                    parse_mode=enums.ParseMode.HTML
                )
                
                if should_send_to_aup and auto_upload_id:
                    try:
                        if msg and msg.document:
                            await client.send_document(auto_upload_id, msg.document.file_id, caption=caption)
                        else:
                            await client.send_document(auto_upload_id, final_path, caption=caption)
                    except Exception as e:
                        logger.error(f"❌ 𝘍𝘢𝘪𝘭𝘦𝘥 𝘵𝘰 𝘚𝘦𝘯𝘥 𝘵𝘰 𝘈𝘶𝘵𝘰 𝘜𝘱𝘭𝘰𝘢𝘥 𝘊𝘩𝘢𝘯𝘯𝘦𝘭 {auto_upload_id}: {e}")
                
                # Do NOT send to user PM if dump_channel is set (requested by user)
            except Exception as e:
                logger.error(f"Upload failed: {e}")
                try: await status_msg.edit_text("❌ 𝘍𝘢𝘪𝘭𝘦𝘥 𝘵𝘰 𝘜𝘱𝘭𝘰𝘢𝘥 𝘍𝘪𝘭𝘦.")
                except Exception: pass
            
            if thumb_path and Path(thumb_path).exists():
                Path(thumb_path).unlink()
            
            shutil.rmtree(chapter_dir, ignore_errors=True)
            if final_path.exists(): final_path.unlink()
            
            await status_msg.delete() # Cleanup status Message on success to avoid clutter? 

    except Exception as e:
        logger.error(f"DL Error: {e}", exc_info=True)
        try: await status_msg.edit_text(f"❌ 𝘌𝘳𝘳𝘰𝘳: {e}")
        except Exception: pass


@Client.on_callback_query(filters.regex("^dl_ask_"))
async def dl_ask_cb(client, callback_query):
    """
    callback_data format:  dl_ask_{source}_{manga_id}_{chapter_token}
    The chapter_token is an integer registered in _chapter_id_registry.
    We split from the RIGHT so a manga_id with underscores is handled correctly.
    """
    data = callback_query.data  # e.g. "dl_ask_OmegaScans_12345|slug_42"
    try:
        if data.startswith("dl_ask_"):
            data = data[7:]
        source, rest = data.split("_", 1)
        last_us = rest.rfind("_")
        manga_id = rest[:last_us]
        token    = int(rest[last_us + 1:])
    except Exception as parse_err:
        logger.error(f"dl_ask_cb parse error: {parse_err} | data={callback_query.data!r}")
        await callback_query.answer("❌ Invalid data, please go back and retry.", show_alert=True)
        return

    # Resolve the full chapter ID from registry
    chapter_id = _resolve_chapter_id(token)
    if chapter_id is None:
        logger.warning(f"dl_ask_cb: token {token} not found in registry (session restart?)")
        await callback_query.answer(
            "⚠️ Session expired. Please go back and re-open the chapter list.",
            show_alert=True,
        )
        return

    try:
        await callback_query.answer("𝘚𝘵𝘢𝘳𝘵𝘪𝘯𝘨 𝘋𝘰𝘸𝘯𝘭𝘰𝘢𝘥...", show_alert=False)
    except Exception:
        pass

    db_channel = await Seishiro.get_default_channel()
    channel_id = int(db_channel) if db_channel else callback_query.message.chat.id

    from Plugins.task_manager import task_manager
    user_id = callback_query.from_user.id
    pos = await task_manager.add_task(
        user_id, callback_query.message.chat.id,
        execute_download,
        client, channel_id, source, manga_id, chapter_id, callback_query.message.chat.id
    )
    await callback_query.message.reply(f"✅ 𝘈𝘥𝘥𝘦𝘥 𝘤𝘩𝘢𝘱𝘵𝘦𝘳 𝘵𝘰 𝘘𝘶𝘦𝘶𝘦. 𝘗𝘰𝘴𝘪𝘵𝘪𝘰𝘯: {pos}")





AWAITING_BATCH = {}  # legacy; state now lives in user_states/user_data


@Client.on_callback_query(filters.regex("^autobat_"))
async def autobatch_cb(client, callback_query):
    """
    callback_data format: autobat_{source}_{manga_id}

    Sets FSM state WAITING_BATCH_NUMBER in user_states so the search handler
    is bypassed and autobatch_reply_handler gets the next message exclusively.
    """
    data = callback_query.data
    # Strip the "autobat_" prefix, then split source from manga_id once
    without_prefix = data[len("autobat_"):]
    first_us = without_prefix.find("_")
    if first_us == -1:
        await callback_query.answer("❌ Bad callback data.", show_alert=True)
        return
    source   = without_prefix[:first_us]
    manga_id = without_prefix[first_us + 1:]
    user_id  = callback_query.from_user.id

    # Set FSM state — this blocks the search handler from stealing the reply
    user_data[user_id]   = {"source": source, "manga_id": manga_id}
    user_states[user_id] = WAITING_BATCH_NUMBER

    await callback_query.answer("Auto Batch selected!", show_alert=False)

    from pyrogram.types import ForceReply
    await callback_query.message.reply(
        "<b>⚡ Auto Batch Mode</b>\n\n"
        "Reply to this message with the <b>number of chapters per batch</b>\n"
        "<i>Example: reply 10 → combines Ch.1–10, Ch.11–20, …</i>\n\n"
        "Send /cancel to abort.",
        reply_markup=ForceReply(selective=True),
        parse_mode=enums.ParseMode.HTML,
    )


@Client.on_message(
    filters.text & filters.private
    & ~filters.command(["start", "help", "settings", "search"])
)
async def autobatch_reply_handler(client, message):
    """
    Handles the batch-size number reply.
    Fires only when the user is in WAITING_BATCH_NUMBER state.
    Because check_search_state returns False for that state, message_handler
    never sees these messages — no race condition.
    """
    user_id = message.from_user.id

    # Only act if this user is waiting for a batch number
    if user_states.get(user_id) != WAITING_BATCH_NUMBER:
        return

    text = (message.text or "").strip()

    # /cancel support
    if text.lower() in ("/cancel", "cancel"):
        user_states.pop(user_id, None)
        user_data.pop(user_id, None)
        await message.reply("❌ Auto Batch cancelled.")
        return

    try:
        batch_size = int(text)
        if batch_size <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.reply(
            "❌ Please send a valid positive integer (e.g. <code>10</code>).",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # Consume FSM state
    ctx      = user_data.pop(user_id, {})
    user_states.pop(user_id, None)
    source   = ctx.get("source", "")
    manga_id = ctx.get("manga_id", "")

    if not source or not manga_id:
        await message.reply("❌ Session data lost — please open the chapter list again.")
        return

    status_msg = await message.reply(
        f"<i>⏳ Fetching all chapters for batch size {batch_size}…</i>",
        parse_mode=enums.ParseMode.HTML,
    )

    API = get_api_class(source)
    if not API:
        await status_msg.edit_text(f"❌ Unknown source: {source}")
        return

    all_chapters = []
    try:
        async with API(Config) as api:
            c_offset = 0
            while True:
                batch = await api.get_manga_chapters(manga_id, limit=100, offset=c_offset)
                if not batch:
                    break
                all_chapters.extend(batch)
                if len(batch) < 100:
                    break
                c_offset += 100
    except Exception as e:
        logger.error(f"autobatch fetch error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Failed to fetch chapters: {e}")
        return

    if not all_chapters:
        await status_msg.edit_text("❌ No chapters found.")
        return

    # Sort ascending; guard against non-numeric chapter values
    def _ch_sort_key(ch):
        try:
            return float(ch["chapter"])
        except (ValueError, KeyError):
            return 0.0

    all_chapters.sort(key=_ch_sort_key)

    # Split into full batches + leftover singles
    chunks  = []
    singles = []
    for i in range(0, len(all_chapters), batch_size):
        chunk = all_chapters[i: i + batch_size]
        if len(chunk) == batch_size:
            chunks.append(chunk)
        else:
            singles.extend(chunk)

    await status_msg.edit_text(
        f"✅ Found <b>{len(all_chapters)}</b> chapters.\n"
        f"Queuing <b>{len(chunks)}</b> combined batches + <b>{len(singles)}</b> singles…",
        parse_mode=enums.ParseMode.HTML,
    )

    from Plugins.task_manager import task_manager
    import Plugins.helper as helper

    for chunk in chunks:
        if helper.CANCEL_TASKS.get(message.chat.id, False):
            helper.CANCEL_TASKS[message.chat.id] = False
            break
        await task_manager.add_task(
            user_id, message.chat.id,
            execute_download_combined,
            client, message.chat.id, source, manga_id, chunk, user_id,
        )

    for ch in singles:
        if helper.CANCEL_TASKS.get(message.chat.id, False):
            helper.CANCEL_TASKS[message.chat.id] = False
            break
        await task_manager.add_task(
            user_id, message.chat.id,
            execute_download,
            client, message.chat.id, source, manga_id, ch["id"], user_id,
        )

    await status_msg.edit_text(
        f"✅ Added all <b>{len(all_chapters)}</b> chapters to queue.",
        parse_mode=enums.ParseMode.HTML,
    )


@Client.on_callback_query(filters.regex("^dl_pg_"))
async def dl_full_page_cb(client, callback_query):
    parts = callback_query.data.split("_")
    source = parts[2]
    offset = int(parts[-1])
    manga_id = "_".join(parts[3:-1])
    user_id = callback_query.from_user.id
    
    await callback_query.answer("𝘚𝘵𝘢𝘳𝘵𝘪𝘯𝘨 𝘋𝘰𝘸𝘯𝘭𝘰𝘢𝘥 𝘧𝘰𝘳 𝘛𝘩𝘪𝘴 𝘱𝘢𝘨𝘦...", show_alert=False)
    
    API = get_api_class(source)
    async with API(Config) as api:
        chapters = await api.get_manga_chapters(manga_id, limit=10, offset=offset)
        
    if not chapters:
        return
        
    for ch in reversed(chapters):
        import Plugins.helper as helper
        if helper.CANCEL_TASKS.get(callback_query.message.chat.id, False):
            helper.CANCEL_TASKS[callback_query.message.chat.id] = False
            break
        from Plugins.task_manager import task_manager
        await task_manager.add_task(user_id, callback_query.message.chat.id, execute_download, client, callback_query.message.chat.id, source, manga_id, ch['id'], user_id)
    await callback_query.message.reply(f"✅ Added {len(chapters)} chapters to queue.")


@Client.on_callback_query(filters.regex("^dl_all_"))
async def dl_all_chapters_cb(client, callback_query):
    parts = callback_query.data.split("_")
    source = parts[2]
    manga_id = "_".join(parts[3:])
    user_id = callback_query.from_user.id
    
    await callback_query.answer("𝘚𝘵𝘢𝘳𝘵𝘪𝘯𝘨 𝘋𝘰𝘸𝘯𝘭𝘰𝘢𝘥 𝘧𝘰𝘳 𝘈𝘓𝘓 𝘊𝘩𝘢𝘱𝘵𝘦𝘳𝘴...", show_alert=True)
    
    API = get_api_class(source)
    all_chapters = []
    
    status_msg = await callback_query.message.reply("<i>⏳ 𝘍𝘦𝘵𝘤𝘩𝘪𝘯𝘨 𝘈𝘭𝘭 𝘊𝘩𝘢𝘱𝘵𝘦𝘳𝘴...</i>", parse_mode=enums.ParseMode.HTML)
    
    async with API(Config) as api:
        c_offset = 0
        while True:
            batch = await api.get_manga_chapters(manga_id, limit=100, offset=c_offset)
            if not batch: break
            all_chapters.extend(batch)
            if len(batch) < 100: break
            c_offset += 100
            
    if not all_chapters:
        await status_msg.edit_text("❌ 𝘕𝘰 𝘊𝘩𝘢𝘱𝘵𝘦𝘳𝘴 𝘍𝘰𝘶𝘯𝘥.")
        return
        
    await status_msg.edit_text(f"✅ 𝘍𝘰𝘶𝘯𝘥 {len(all_chapters)} 𝘊𝘩𝘢𝘱𝘵𝘦𝘳𝘴. 𝘘𝘶𝘦𝘶𝘦𝘪𝘯𝘨 𝘋𝘰𝘸𝘯𝘭𝘰𝘢𝘥𝘴...")
    
    all_chapters.sort(key=lambda x: float(x['chapter']))
    
    for ch in all_chapters:
        import Plugins.helper as helper
        if helper.CANCEL_TASKS.get(callback_query.message.chat.id, False):
            helper.CANCEL_TASKS[callback_query.message.chat.id] = False
            break
        from Plugins.task_manager import task_manager
        await task_manager.add_task(user_id, callback_query.message.chat.id, execute_download, client, callback_query.message.chat.id, source, manga_id, ch['id'], user_id)
    await status_msg.edit_text(f"✅ 𝘈𝘥𝘥𝘦𝘥 {len(all_chapters)} 𝘊𝘩𝘢𝘱𝘵𝘦𝘳𝘴 𝘵𝘰 𝘘𝘶𝘦𝘶𝘦.")
