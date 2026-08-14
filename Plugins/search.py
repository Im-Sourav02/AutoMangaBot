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
from Plugins.helper import edit_msg_with_pic, get_styled_text, user_states, user_data, WAITING_CHAPTER_INPUT
import logging
import asyncio
import difflib
import shutil
from pathlib import Path
import os
import re

logger = logging.getLogger(__name__)

from Plugins.Sites.mangakakalot import MangakakalotAPI
from Plugins.Sites.allmanga import AllMangaAPI
from Plugins.Sites.comick import ComickAPI
from Plugins.Sites.atsumaru import AtsumaruAPI
from Plugins.Sites.omegascans import OmegaScansAPI
from Plugins.Sites.theblank import TheBlankAPI
# Madara-based
from Plugins.Sites.toonily import ToonilyAPI
from Plugins.Sites.manhwaread import ManhwaReadAPI
from Plugins.Sites.weebtoon import WebtoonScanAPI
from Plugins.Sites.hentai20 import Hentai20API
from Plugins.Sites.manga18fx import Manga18fxAPI
from Plugins.Sites.manga18club import Manga18clubAPI
from Plugins.Sites.manhwa18 import Manhwa18API
from Plugins.Sites.manhwaclub import ManhwaClubAPI
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

SITES = {
    # Original sources
    "MangaDex": MangaDexAPI,
    "MangaForest": MangaForestAPI,
    "Mangakakalot": MangakakalotAPI,
    "AllManga": AllMangaAPI,
    "Comick": ComickAPI,
    "Atsumaru": AtsumaruAPI,
    "OmegaScans": OmegaScansAPI,
    "TheBlank": TheBlankAPI,
    "WebCentral": None,
    # Madara-based sources
    "Toonily": ToonilyAPI,
    "ManhwaRead": ManhwaReadAPI,
    # WebtoonScan removed — domain dead
    "Hentai20": Hentai20API,
    "Manga18fx": Manga18fxAPI,
    "Manga18Club": Manga18clubAPI,
    "Manhwa18": Manhwa18API,
    "ManhwaClub": ManhwaClubAPI,
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
    if m.text and m.text.startswith('/'):
        return False
    uid = m.from_user.id
    if uid not in user_states: return True
    return user_states[uid] == WAITING_CHAPTER_INPUT

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
    parts = callback_query.data.split("_")
    if len(parts) < 4:
        await callback_query.answer("❌ Invalid callback data", show_alert=True)
        return
    
    source = parts[1]
    offset = int(parts[-1])  # Last part is always offset
    manga_id = "_".join(parts[2:-1])  # Everything between source and offset
    
    API = get_api_class(source)
    async with API(Config) as api:
        chapters = await api.get_manga_chapters(manga_id, limit=10, offset=offset)
    
    if not chapters and offset == 0:
        await callback_query.answer("No chapters found.", show_alert=True)
        return
    elif not chapters:
        await callback_query.answer("No more chapters.", show_alert=True)
        return

    # Calculate offset logic
    # offset is chapter index (0 = first page of 10)
    page_size = 10
    current_page = (offset // page_size) + 1
    
    # We need total chapters to know when to stop
    # But some sources don't give total length easily, so we just check if we got chapters
    
    buttons = []
    row = []
    for ch in chapters:
        ch_num = ch['chapter']
        btn_text = f"Chapter {ch_num}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"dl_ask_{source}_{manga_id}_{ch['id'][:20]}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    
    # Pagination: << 5x, < 2x, <, >, 2x >, 5x >>
    # Wait, we need to know max pages. We'll just provide the buttons and if they hit an empty page it says "No more".
    # User requested: >>, 2x>, 5x>
    nav_row_1 = []
    nav_row_2 = []
    
    if offset >= page_size:
        nav_row_1.append(InlineKeyboardButton("<<", callback_data=f"chapters_{source}_{manga_id}_{offset - page_size}"))
    if offset >= page_size * 2:
        nav_row_1.insert(0, InlineKeyboardButton("<2x", callback_data=f"chapters_{source}_{manga_id}_{offset - page_size*2}"))
    if offset >= page_size * 5:
        nav_row_1.insert(0, InlineKeyboardButton("<5x", callback_data=f"chapters_{source}_{manga_id}_{offset - page_size*5}"))
        
    nav_row_2.append(InlineKeyboardButton(">>", callback_data=f"chapters_{source}_{manga_id}_{offset + page_size}"))
    nav_row_2.append(InlineKeyboardButton("2x>", callback_data=f"chapters_{source}_{manga_id}_{offset + page_size*2}"))
    nav_row_2.append(InlineKeyboardButton("5x>", callback_data=f"chapters_{source}_{manga_id}_{offset + page_size*5}"))
    
    if nav_row_1: buttons.append(nav_row_1)
    if nav_row_2: buttons.append(nav_row_2)
    
    # Check if subscribed
    user_id = callback_query.from_user.id
    subs = await Seishiro.subs_db.get_user_subscriptions(user_id)
    is_subscribed = any(sub.get('url') == manga_id and sub.get('source') == source for sub in subs)
    sub_text = "🔕 UNSUBSCRIBE 🔕" if is_subscribed else "🔔 SUBSCRIBE 🔔"
    sub_cb = f"unsub_{source}_{manga_id}" if is_subscribed else f"sub_{source}_{manga_id}"

    # Bottom utilities
    user_settings = await Seishiro.settings_db.get_settings(user_id)
    current_format = user_settings.get("file_type", "PDF")
    
    tgl_cb = f"tgl_fmt_{source}_{manga_id}_{offset}"
    dl_pg_cb = f"dl_pg_{source}_{manga_id}_{offset}"
    dl_all_cb = f"dl_all_{source}_{manga_id}"
    
    # Guard 64-byte limit
    if len(tgl_cb.encode('utf-8')) > 64:
        short_id = manga_id[:62 - len(source) - len(str(offset)) - 10]
        tgl_cb = f"tgl_fmt_{source}_{short_id}_{offset}"
        dl_pg_cb = f"dl_pg_{source}_{short_id}_{offset}"
        dl_all_cb = f"dl_all_{source}_{short_id}"
        
    buttons.extend([
        [InlineKeyboardButton(f"Single {current_format}", callback_data=tgl_cb)],
        [InlineKeyboardButton("⬆ FULL PAGE ⬆", callback_data=dl_pg_cb), InlineKeyboardButton("⬆ ALL CHAPTERS ⬆", callback_data=dl_all_cb)],
        [InlineKeyboardButton(sub_text, callback_data=sub_cb)],
        [InlineKeyboardButton("BACK", callback_data=f"view_{source}_{manga_id}"), InlineKeyboardButton("| CLOSE |", callback_data="stats_close")]
    ])
    
    caption_text = f"<b>Chapter Selection:</b>\nPage: {current_page}"
    
    try:
        api_class = get_api_class(source)
        cover_url = None
        if api_class:
            async with api_class(Config) as api:
                info = await api.get_manga_info(manga_id)
                if info:
                    cover_url = info.get('cover')

        await edit_msg_with_pic(callback_query.message, caption_text, InlineKeyboardMarkup(buttons), pic=cover_url)
    except Exception as e:
        logger.error(f"Edit error: {e}")


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
        await execute_download_combined(client, message.chat.id, source, manga_id, to_download, user_id)
    else:
        for ch in to_download:
            import Plugins.helper as helper
            if helper.CANCEL_TASKS.get(message.chat.id, False):
                helper.CANCEL_TASKS[message.chat.id] = False
                break
            await execute_download(client, message.chat.id, source, manga_id, ch['id'], user_id)


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
    status_msg = await client.send_message(status_chat_id, f"<i>⏳ Initializing combined download for {len(chapters_to_download)} chapters...</i>", parse_mode=enums.ParseMode.HTML)
    
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
                    await status_msg.edit_text("❌ Download cancelled.")
                    return
                images = await api.get_chapter_images(ch['id'])
                if images:
                    all_images.extend(images)
                
        if not all_images:
            await status_msg.edit_text(f"❌ no images found in the selected chapters.")
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
                 await status_msg.edit_text("❌ download failed.")
                 return
            
            await status_msg.edit_text(f"<i>⚙️ processing file...</i>", parse_mode=enums.ParseMode.HTML)
            
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
                 await status_msg.edit_text("❌ failed to create file.")
                 return
            
            await status_msg.edit_text(f"<i>⬆ uploading...</i>", parse_mode=enums.ParseMode.HTML)
            
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
                        logger.error(f"Failed to send to auto upload channel {auto_upload_id}: {e}")
                
            except Exception as e:
                logger.error(f"Upload failed: {e}")
                await status_msg.edit_text("❌ failed to upload file.")
            
            if thumb_path and Path(thumb_path).exists():
                Path(thumb_path).unlink()
            
            shutil.rmtree(chapter_dir, ignore_errors=True)
            if final_path.exists(): final_path.unlink()
            
            await status_msg.delete() 

    except Exception as e:
        logger.error(f"DL Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Error: {e}")

async def execute_download(client, target_chat_id, source, manga_id, chapter_id, user_id, status_chat_id=None):
    """
    Downloads and uploads a chapter.
    status_chat_id: Where to send updates (if different from target).
    """
    if not status_chat_id: status_chat_id = target_chat_id
    
    status_msg = await client.send_message(status_chat_id, "<i>⏳ Initializing download...</i>", parse_mode=enums.ParseMode.HTML)
    
    try:
        API = get_api_class(source)
        async with API(Config) as api:
            meta = await api.get_chapter_info(chapter_id)
            if not meta:
                await status_msg.edit_text("❌ failed to get chapter info.")
                return
            
            if not meta.get('manga_title'):
                 m_info = await api.get_manga_info(manga_id)
                 if m_info: meta['manga_title'] = m_info['title']

            images = await api.get_chapter_images(chapter_id)
            
        if not images:
            await status_msg.edit_text(f"❌ no images in chapter {meta.get('chapter', '?')}")
            return
            
        # Sanitize manga_id for use in directory names (Windows forbids | : * ? " < > \)
        safe_manga_id = re.sub(r'[\\/:*?"<>|]', '_', manga_id)
        chapter_dir = Path(Config.DOWNLOAD_DIR) / f"{source}_{safe_manga_id}" / f"ch_{meta['chapter']}"
        chapter_dir.mkdir(parents=True, exist_ok=True)
        
        await status_msg.edit_text(f"<i>⬇ downloading {len(images)} pages...</i>", parse_mode=enums.ParseMode.HTML)
        
        async with Downloader(Config) as downloader:
            # Pass the source site as Referer so hotlink-protected CDNs accept the request
            dl_referer = getattr(api, 'base_url', None) or getattr(api, '_base_url', None)
            dl_headers = {'Referer': dl_referer.rstrip('/') + '/'} if dl_referer else None
            if not await downloader.download_images(images, chapter_dir, headers=dl_headers):
                 await status_msg.edit_text("❌ download failed.")
                 return
            
            await status_msg.edit_text("<i>⚙️ processing pdf...</i>", parse_mode=enums.ParseMode.HTML)
            
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
                 await status_msg.edit_text("❌ failed to create file.")
                 return
            
            await status_msg.edit_text(f"<i>⬆ uploading...</i>", parse_mode=enums.ParseMode.HTML)
            
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
                        auto_upload_id = chan.get('_id')
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
                        logger.error(f"Failed to send to auto upload channel {auto_upload_id}: {e}")
                
                # Do NOT send to user PM if dump_channel is set (requested by user)
            except Exception as e:
                logger.error(f"Upload failed: {e}")
                await status_msg.edit_text("❌ failed to upload file.")
            
            if thumb_path and Path(thumb_path).exists():
                Path(thumb_path).unlink()
            
            shutil.rmtree(chapter_dir, ignore_errors=True)
            if final_path.exists(): final_path.unlink()
            
            await status_msg.delete() # Cleanup status Message on success to avoid clutter? 

    except Exception as e:
        logger.error(f"DL Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Error: {e}")


@Client.on_callback_query(filters.regex("^dl_ask_"))
async def dl_ask_cb(client, callback_query):
    data = callback_query.data.split("_")
    source = data[2]
    manga_id = data[3]
    chapter_id = "_".join(data[4:])
    
    try:
        await callback_query.answer("Starting download...", show_alert=False)
    except Exception:
        pass
        
    db_channel = await Seishiro.get_default_channel()
    channel_id = int(db_channel) if db_channel else callback_query.message.chat.id
    
    await execute_download(client, channel_id, source, manga_id, chapter_id, callback_query.message.chat.id)



# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat
@Client.on_callback_query(filters.regex("^tgl_fmt_"))
async def toggle_format_cb(client, callback_query):
    parts = callback_query.data.split("_")
    source = parts[2]
    offset = parts[-1]
    manga_id = "_".join(parts[3:-1])
    
    user_id = callback_query.from_user.id
    user_settings = await Seishiro.settings_db.get_settings(user_id)
    current_format = user_settings.get("file_type", "PDF")
    new_format = "CBZ" if current_format == "PDF" else "PDF"
    
    await Seishiro.settings_db.update_setting(user_id, "file_type", new_format)
    await callback_query.answer(f"Format changed to Single {new_format}!", show_alert=False)
    
    # Refresh the menu to show the new button text
    callback_query.data = f"chapters_{source}_{manga_id}_{offset}"
    await chapters_list_cb(client, callback_query)


@Client.on_callback_query(filters.regex("^dl_pg_"))
async def dl_full_page_cb(client, callback_query):
    parts = callback_query.data.split("_")
    source = parts[2]
    offset = int(parts[-1])
    manga_id = "_".join(parts[3:-1])
    user_id = callback_query.from_user.id
    
    await callback_query.answer("Starting download for this page...", show_alert=False)
    
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
        await execute_download(client, callback_query.message.chat.id, source, manga_id, ch['id'], user_id)


@Client.on_callback_query(filters.regex("^dl_all_"))
async def dl_all_chapters_cb(client, callback_query):
    parts = callback_query.data.split("_")
    source = parts[2]
    manga_id = "_".join(parts[3:])
    user_id = callback_query.from_user.id
    
    await callback_query.answer("Starting download for ALL chapters...", show_alert=True)
    
    API = get_api_class(source)
    all_chapters = []
    
    status_msg = await callback_query.message.reply("<i>⏳ fetching all chapters...</i>", parse_mode=enums.ParseMode.HTML)
    
    async with API(Config) as api:
        c_offset = 0
        while True:
            batch = await api.get_manga_chapters(manga_id, limit=100, offset=c_offset)
            if not batch: break
            all_chapters.extend(batch)
            if len(batch) < 100: break
            c_offset += 100
            
    if not all_chapters:
        await status_msg.edit_text("❌ no chapters found.")
        return
        
    await status_msg.edit_text(f"✅ Found {len(all_chapters)} chapters. Queueing downloads...")
    
    all_chapters.sort(key=lambda x: float(x['chapter']))
    
    for ch in all_chapters:
        import Plugins.helper as helper
        if helper.CANCEL_TASKS.get(callback_query.message.chat.id, False):
            helper.CANCEL_TASKS[callback_query.message.chat.id] = False
            break
        await execute_download(client, callback_query.message.chat.id, source, manga_id, ch['id'], user_id)
