import logging
import math
import difflib

import math
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Database.database import Seishiro
from Utils.helper import edit_msg_with_pic

logger = logging.getLogger(__name__)

SUBS_PER_PAGE = 8

async def build_subs_menu(user_id: int, page: int = 1):
    subs = await Seishiro.subs_db.get_user_subscriptions(user_id)
    total_subs = len(subs)
    
    text = (
        f"<b>Your Subscriptions (Total: {total_subs})</b>\n"
        f"<i>Page {page}</i>"
    )

    if total_subs == 0:
        buttons = [
            [InlineKeyboardButton("✶ Refresh ✶", callback_data="subs_page_1")],
            [InlineKeyboardButton("Export", callback_data="subs_export"), InlineKeyboardButton("Import", callback_data="subs_import")],
            [InlineKeyboardButton("◊ QUEUE ◊", callback_data="queue_menu"), InlineKeyboardButton("| CLOSE |", callback_data="close")]
        ]
        return text, InlineKeyboardMarkup(buttons)

    total_pages = math.ceil(total_subs / SUBS_PER_PAGE)
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * SUBS_PER_PAGE
    end_idx = start_idx + SUBS_PER_PAGE
    page_subs = subs[start_idx:end_idx]

    buttons = []
    
    for i, sub in enumerate(page_subs):
        # Format: 0. Title [Source]
        title = sub.get('title', 'Unknown')
        source = sub.get('source', 'Unknown')
        idx = start_idx + i
        # Callback data should ideally just load the manga details
        url = sub.get('url', '')
        cb_data = f"manga_{source}_{url[:20]}" # truncate url for limits
        buttons.append([InlineKeyboardButton(f"{idx}. {title} [{source}]", callback_data=cb_data)])

    # Pagination
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀ Prev", callback_data=f"subs_page_{page-1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Next ▶", callback_data=f"subs_page_{page+1}"))
    
    if nav_row:
        buttons.append(nav_row)

    buttons.extend([
        [InlineKeyboardButton("✶ Clean All Subs ✶", callback_data="clean_subs"), InlineKeyboardButton("✶ Refresh ✶", callback_data=f"subs_page_{page}")],
        [InlineKeyboardButton("Export", callback_data="subs_export"), InlineKeyboardButton("Import", callback_data="subs_import")],
        [InlineKeyboardButton("◊ QUEUE ◊", callback_data="queue_menu"), InlineKeyboardButton("| CLOSE |", callback_data="close")]
    ])

    return text, InlineKeyboardMarkup(buttons)

@Client.on_message(filters.command("subs"), group=2)
async def subs_command(client, message):
    try:
        user_id = message.from_user.id
        text, markup = await build_subs_menu(user_id, 1)
        # Use default banner if user hasn't set one
        await edit_msg_with_pic(message, text, markup)
    except Exception as e:
        logger.error(f"Error in /subs command: {e}")

@Client.on_callback_query(filters.regex(r"^subs_menu$|^subs_page_(\d+)$"))
async def subs_callback(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        match = callback_query.matches[0]
        page = 1
        if len(match.groups()) > 0 and match.group(1):
            page = int(match.group(1))
            
        text, markup = await build_subs_menu(user_id, page)
        await edit_msg_with_pic(callback_query.message, text, markup)
    except Exception as e:
        logger.error(f"Error in subs callback: {e}")
        await callback_query.answer("Error loading subscriptions", show_alert=True)

@Client.on_callback_query(filters.regex("^clean_subs$"))
async def clean_subs_callback(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        await Seishiro.subs_db.clear_all_subscriptions(user_id)
        await callback_query.answer("All subscriptions cleared!", show_alert=True)
        text, markup = await build_subs_menu(user_id, 1)
        await edit_msg_with_pic(callback_query.message, text, markup)
    except Exception as e:
        logger.error(f"Error clearing subs: {e}")
        await callback_query.answer("Error clearing subscriptions", show_alert=True)

@Client.on_callback_query(filters.regex("^sub_"))
async def add_sub_callback(client, callback_query):
    try:
        parts = callback_query.data.split("_", 2)
        source = parts[1]
        manga_id = parts[2]
        user_id = callback_query.from_user.id
        
        # We need the manga title and latest chapter. We can try fetching it.
        from Plugins.search import get_api_class
        from config import Config
        api_class = get_api_class(source)
        if not api_class:
            await callback_query.answer("Source not available", show_alert=True)
            return
            
        async with api_class(Config) as api:
            info = await api.get_manga_info(manga_id)
            if not info:
                await callback_query.answer("Could not fetch manga info", show_alert=True)
                return
                
            # Get latest chapter (just fetch first page)
            chapters = await api.get_manga_chapters(manga_id, limit=1, offset=0)
            latest = chapters[0]['chapter'] if chapters else ""
            
            # Check global auto upload channels for match
            title_lower = info.get('title', 'Unknown').lower()
            upload_chan_id = None
            aup_channels = await Seishiro.get_auto_upload_channels(user_id)
            for chan in aup_channels:
                c_title = chan.get('title', '').lower()
                if not c_title: continue
                ratio = difflib.SequenceMatcher(None, title_lower, c_title).ratio()
                if ratio > 0.8 or title_lower in c_title or c_title in title_lower:
                    upload_chan_id = chan.get('_id')
                    break
            
            sub_data = {
                "id": manga_id,
                "title": info.get('title', 'Unknown'),
                "latest_chapter": latest,
                "auto_upload_channel_id": upload_chan_id
            }
            
            success = await Seishiro.subs_db.add_subscription(user_id, sub_data, source)
            if success:
                await callback_query.answer("Subscribed! 🔔", show_alert=True)
                # Edit message to update the toggle button
                # We can just recall view_manga_cb by changing data to view_source_id
                callback_query.data = f"view_{source}_{manga_id}"
                from Plugins.search import view_manga_cb
                await view_manga_cb(client, callback_query)
            else:
                await callback_query.answer("Failed to subscribe.", show_alert=True)
    except Exception as e:
        logger.error(f"Sub error: {e}")
        await callback_query.answer("An error occurred.", show_alert=True)

@Client.on_callback_query(filters.regex("^unsub_"))
async def remove_sub_callback(client, callback_query):
    try:
        parts = callback_query.data.split("_", 2)
        source = parts[1]
        manga_id = parts[2]
        user_id = callback_query.from_user.id
        
        success = await Seishiro.subs_db.remove_subscription(user_id, manga_id, source)
        if success:
            await callback_query.answer("Unsubscribed! 🔕", show_alert=True)
            # We can just recall view_manga_cb or chapters_list_cb depending on where we are
            if "Chapter Selection" in callback_query.message.text or callback_query.message.caption:
                # We are in chapter list, but we don't have offset. It's safer to go back to manga details
                callback_query.data = f"view_{source}_{manga_id}"
                from Plugins.search import view_manga_cb
                await view_manga_cb(client, callback_query)
            else:
                callback_query.data = f"view_{source}_{manga_id}"
                from Plugins.search import view_manga_cb
                await view_manga_cb(client, callback_query)
        else:
            await callback_query.answer("Not subscribed.", show_alert=True)
    except Exception as e:
        logger.error(f"Unsub error: {e}")
        await callback_query.answer("An error occurred.", show_alert=True)


@Client.on_callback_query(filters.regex("^subs_export$"))
async def subs_export_cb(client, callback_query):
    import json
    import io
    
    try:
        user_id = callback_query.from_user.id
        subs = await Seishiro.subs_db.get_user_subscriptions(user_id)
        
        if not subs:
            await callback_query.answer("You have no subscriptions to export.", show_alert=True)
            return
            
        export_data = {"subs": []}
        for sub in subs:
            export_data["subs"].append({
                "url": sub.get('url') or sub.get('id', ''),
                "title": sub.get('title', 'Unknown'),
                "lastest_chapter": sub.get('latest_chapter', ''),
                "source": sub.get('source', '')
            })
            
        json_bytes = json.dumps(export_data, indent=2).encode('utf-8')
        doc = io.BytesIO(json_bytes)
        doc.name = f"subscriptions_{user_id}.json"
        
        await callback_query.message.reply_document(
            document=doc,
            caption="Here is your subscriptions backup!"
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Export error: {e}")
        await callback_query.answer("Failed to export.", show_alert=True)


WAITING_IMPORT_JSON = "WAITING_IMPORT_JSON"
from Utils.helper import user_states

@Client.on_callback_query(filters.regex("^subs_import$"))
async def subs_import_cb(client, callback_query):
    user_id = callback_query.from_user.id
    user_states[user_id] = WAITING_IMPORT_JSON
    await callback_query.message.reply_text(
        "Please send the `subscriptions.json` file you want to import.\n\n"
        "<i>Note: This will add to your current subscriptions.</i>",
        parse_mode=enums.ParseMode.HTML
    )
    await callback_query.answer()


@Client.on_message(filters.document & filters.private)
async def handle_json_import(client, message):
    user_id = message.from_user.id
    if user_states.get(user_id) != WAITING_IMPORT_JSON:
        return
        
    if not message.document.file_name.endswith('.json'):
        await message.reply("Please send a valid JSON file.")
        return
        
    status = await message.reply("<i>⏳ Processing import...</i>")
    import json
    import os
    
    try:
        file_path = await message.download()
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if "subs" not in data:
            await status.edit_text("❌ Invalid JSON format. 'subs' array missing.")
            os.remove(file_path)
            return
            
        imported = 0
        for item in data["subs"]:
            manga_id = item.get("url") or item.get("id")
            source = item.get("source", "Unknown") # Fallback since user json might not have source
            title = item.get("title", "Unknown")
            latest = item.get("lastest_chapter") or item.get("latest_chapter", "")
            
            if manga_id:
                sub_data = {
                    "id": manga_id,
                    "title": title,
                    "latest_chapter": latest,
                    "auto_upload_channel_id": None
                }
                # Use source if provided, else we might have to guess or set to a default.
                # Assuming source is provided in our exports, but if user uses external json without source, 
                # we'll just set it to 'mangadex' or whatever they want.
                if source == "Unknown":
                    # Try to guess source from URL if it's a URL
                    if "atsu.moe" in manga_id: source = "MangaDex" # Placeholder logic
                    
                await Seishiro.subs_db.add_subscription(user_id, sub_data, source)
                imported += 1
                
        os.remove(file_path)
        del user_states[user_id]
        
        await status.edit_text(f"✅ Successfully imported {imported} subscriptions!")
    except Exception as e:
        logger.error(f"Import error: {e}")
        await status.edit_text("❌ Failed to process the JSON file.")

