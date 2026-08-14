# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat


import logging

from pyrogram import Client, filters, enums

logger = logging.getLogger(__name__)

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from Database.database import Seishiro
from Database.database import Seishiro
from Plugins.helper import get_styled_text, admin, edit_msg_with_pic

@Client.on_callback_query(filters.regex("^settings_menu$|^settings_menu_1$|^settings_menu_2$"))
async def settings_main_menu(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        
        # Get settings from the new settings DB
        user_settings = await Seishiro.settings_db.get_settings(user_id)
        
        file_name = user_settings.get("file_name", "None")
        caption = user_settings.get("caption_format", "None")
        thumbnail = user_settings.get("thumbnail_enabled", True)
        
        text = (
            f"<blockquote><b>➥ File Name:</b> {file_name}[None]\n"
            f"<b>➥ Caption:</b> {caption}\n"
            f"<b>➥ Thumbnail:</b> {thumbnail}</blockquote>"
        )

        buttons = [
            [InlineKeyboardButton("AUTO UPDATE CHANNELS", callback_data="header_auto_update_channels")],
            [
                InlineKeyboardButton("BANNER", callback_data="set_banner_btn"),
                InlineKeyboardButton("CAPTION", callback_data="set_caption_btn")
            ],
            [
                InlineKeyboardButton("CHANNEL STICKERS", callback_data="set_channel_stickers_btn"),
                InlineKeyboardButton("COMPRESS", callback_data="set_compress_btn")
            ],
            [
                InlineKeyboardButton("FILE NAME", callback_data="set_format_btn"),
                InlineKeyboardButton("FILE TYPE", callback_data="set_file_type_btn")
            ],
            [InlineKeyboardButton("AUTO UPLOAD CHANNELS", callback_data="header_auto_upload_channels")],
            [
                InlineKeyboardButton("HYPERLINK", callback_data="set_hyperlink_btn"),
                InlineKeyboardButton("MERGE SIZE", callback_data="set_merge_size_btn")
            ],
            [
                InlineKeyboardButton("PASSWORD", callback_data="set_password_btn"),
                InlineKeyboardButton("REGEX", callback_data="set_regex_btn")
            ],
            [InlineKeyboardButton("DUMP CHANNEL", callback_data="set_dump_channel_btn")],
            [
                InlineKeyboardButton("THUMBNAIL", callback_data="set_thumb_btn"), 
                InlineKeyboardButton("UPDATE CHANNEL", callback_data="set_channel_btn")
            ],
            [InlineKeyboardButton("🌐 MANAGE SOURCES", callback_data="header_manage_sources")],
            [
                InlineKeyboardButton("UPDATE TEXT", callback_data="set_update_text_btn"),
                InlineKeyboardButton("UPDATE STICKER", callback_data="set_update_sticker_btn")
            ],
            [InlineKeyboardButton("UPDATE BUTTON", callback_data="set_update_button_btn")],
            [
                InlineKeyboardButton("Before Post", callback_data="set_before_post_btn"),
                InlineKeyboardButton("After Post", callback_data="set_after_post_btn")
            ],
            [
                InlineKeyboardButton("✧ HOME ✧", callback_data="start_menu"),
                InlineKeyboardButton("✧ CLOSE ✧", callback_data="close")
            ]
        ]
        
        await edit_msg_with_pic(
            message=callback_query.message,
            text=text,
            buttons=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.error(f"Error opening settings: {e}")
        await callback_query.answer("Error opening settings")


@Client.on_callback_query(filters.regex("^header_(?!dump_channel|source|auto_update_channels|auto_upload_channels|new_items)"))
async def header_callback(client, callback_query):
    await callback_query.answer("Values in this section:", show_alert=False)

@Client.on_callback_query(filters.regex("^(stats_close|close)$"))
async def close_callback(client, callback_query):
    await callback_query.message.delete()

@Client.on_callback_query(filters.regex("^start_menu$"))
async def start_menu_cb(client, callback_query):
    caption = (
        f"<blockquote><b>🌸 WELCOME TO MANGA BOT!!</b></blockquote>\n\n"
        f"<blockquote><b>📖 USE /search &lt;name&gt; TO FIND\n"
        f"ANY MANGA / MANHWA!</b></blockquote>\n\n"
        f"<blockquote><b>⚙️ USE /us TO CUSTOMIZE YOUR SETTINGS\n"
        f"🔔 USE /subs TO VIEW YOUR SUBSCRIPTIONS</b></blockquote>"
    )
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu"),
            InlineKeyboardButton("📥 Queue", callback_data="queue_menu")
        ],
        [
            InlineKeyboardButton("🔔 Subscribes", callback_data="subs_menu"),
            InlineKeyboardButton("❓ Help", callback_data="help_menu")
        ],
        [
            InlineKeyboardButton("❌ CLOSE", callback_data="close")
        ]
    ])
    await edit_msg_with_pic(callback_query.message, caption, buttons)



_SOURCES_PER_PAGE = 8  # 2 per row × 4 rows


def _source_pages(current: str):
    """Build paginated InlineKeyboardMarkup for the source picker."""
    from Plugins.search import SITES
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    sources = [name for name, cls in SITES.items() if cls is not None]
    total = len(sources)
    pages = []
    for i in range(0, total, _SOURCES_PER_PAGE):
        pages.append(sources[i: i + _SOURCES_PER_PAGE])
    return pages, total


def _build_source_kb(page_idx: int, current: str):
    from Plugins.search import SITES
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    sources = [name for name, cls in SITES.items() if cls is not None]
    total = len(sources)
    n_pages = (total + _SOURCES_PER_PAGE - 1) // _SOURCES_PER_PAGE
    page_idx = max(0, min(page_idx, n_pages - 1))
    page_sources = sources[page_idx * _SOURCES_PER_PAGE: (page_idx + 1) * _SOURCES_PER_PAGE]

    buttons = []
    row = []
    for src in page_sources:
        tick = "✅ " if current.lower() == src.lower() else ""
        cb = f"set_source_{src.lower().replace(' ', '_')}"
        row.append(InlineKeyboardButton(f"{tick}{src}", callback_data=cb))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Navigation row
    nav = []
    if page_idx > 0:
        nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"src_page_{page_idx - 1}"))
    nav.append(InlineKeyboardButton(f"📄 {page_idx + 1}/{n_pages}", callback_data="noop"))
    if page_idx < n_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶", callback_data=f"src_page_{page_idx + 1}"))
    buttons.append(nav)
    buttons.append([InlineKeyboardButton("⬅ back", callback_data="settings_menu")])
    return InlineKeyboardMarkup(buttons)


@Client.on_callback_query(filters.regex("^set_source_btn$"))
async def set_source_menu(client, callback_query):
    try:
        current = await Seishiro.get_config('manga_source', 'mangadex')
        text = (
            "<b>📡 Select Manga Source</b>\n\n"
            "<blockquote>Choose which source the bot should use for automatic updates and searching.</blockquote>\n\n"
            f"<b>Current:</b> <code>{current}</code>"
        )
        await edit_msg_with_pic(
            message=callback_query.message,
            text=text,
            buttons=_build_source_kb(0, current)
        )
    except Exception as e:
        logger.error(f"set_source_menu: {e}")
        await callback_query.answer("Error opening source menu")


@Client.on_callback_query(filters.regex(r"^src_page_(\d+)$"))
async def source_page_cb(client, callback_query):
    try:
        page_idx = int(callback_query.matches[0].group(1))
        current = await Seishiro.get_config('manga_source', 'mangadex')
        text = (
            "<b>📡 Select Manga Source</b>\n\n"
            "<blockquote>Choose which source the bot should use for automatic updates and searching.</blockquote>\n\n"
            f"<b>Current:</b> <code>{current}</code>"
        )
        await callback_query.message.edit_text(
            text,
            reply_markup=_build_source_kb(page_idx, current),
            parse_mode=enums.ParseMode.HTML
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"source_page_cb: {e}")
        await callback_query.answer("Error")




# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat


@Client.on_callback_query(filters.regex("^set_source_(.+)$"))
async def set_source_callback(client, callback_query):
    new_source = callback_query.matches[0].group(1)
    await Seishiro.set_config('manga_source', new_source)
    await callback_query.answer(f"Source set to: {new_source}", show_alert=True)
    await set_source_menu(client, callback_query)


# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat