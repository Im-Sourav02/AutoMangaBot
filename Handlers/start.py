# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat


import logging
import random
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Database.database import Seishiro
from config import Config
from Utils.helper import edit_msg_with_pic

logger = logging.getLogger(__name__)
logger.info("PLUGIN LOAD: start.py loaded successfully")


@Client.on_message(filters.command("start"), group=1)
async def start_msg(client, message):
    try:
        from Utils.helper import check_fsub
        missing = await check_fsub(client, message.from_user.id)
        if missing:
            buttons = []
            for ch in missing:
                buttons.append([InlineKeyboardButton(f"Join {ch['title']}", url=ch['url'])])
            
            if len(message.command) > 1:
               deep_link = message.command[1]
               buttons.append([InlineKeyboardButton("done ✅", url=f"https://t.me/{client.me.username}?start={deep_link}")])
            else:
               buttons.append([InlineKeyboardButton("done ✅", url=f"https://t.me/{client.me.username}?start=True")])
               
            await message.reply_text(
                "<b>⚠️ you must join our channels to use this bot!</b>\n\n"
                "Please join the channels below and try again.",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
            return

        if len(message.command) > 1:
            payload = message.command[1]
            if payload.startswith("dl_"):
                chapter_id = payload.replace("dl_", "")
                
                file_id = await Seishiro.get_chapter_file(chapter_id)
                if file_id:
                     try:
                        await message.reply_document(file_id)
                     except Exception as e:
                        logger.error(f"Failed to send file {file_id}: {e}")
                        await message.reply("❌ error sending file. it might have been deleted.")
                else:
                     await message.reply("❌ file not found or deleted from db.")
                return

        try:
            if await Seishiro.is_user_banned(message.from_user.id):
                await message.reply_text("🚫 **access denied**\n\nyou are banned from using this bot.")
                return
        except Exception as db_e:
            logger.error(f"Database error (Ban Check): {db_e}")

        try:
            await Seishiro.add_user(client, message)
        except Exception as db_e:
            logger.error(f"Database error (Add User): {db_e}")

        caption = (
            f"<blockquote><b>🌸 WELCOME TO MANGA BOT!!</b></blockquote>\n\n"
            f"<blockquote><b>📖 USE /search <name> TO FIND\n"
            f"ANY MANGA / MANHWA!</b></blockquote>\n\n"
            f"<blockquote><b>⚙️ USE /us TO CUSTOMIZE YOUR SETTINGS\n"
            f"🔔 USE /subs TO VIEW YOUR SUBSCRIPTIONS</b></blockquote>"
        )
        
        START_PIC = "https://pictr.com/images/2026/08/14/xqMrZq.jpg"

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

        try:
            await message.reply_photo(
                photo=START_PIC,
                caption=caption,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as img_e:
            logger.error(f"Image failed to load: {img_e}")
            await message.reply_text(
                text=caption,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"/start failed: {e}", exc_info=True)
        try:
            await message.reply_text(f"✅ Bot is alive! (Error displaying menu: {e})")
        except:
            pass

# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat


@Client.on_callback_query(filters.regex("^help_menu$"))
async def help_menu(client, callback_query):
    paraphrased = (
        "<b>📚 How to Use</b>\n\n"
        "• <b>Search Manga:</b> Just send me the manga name (e.g. `One Piece`) to begin.\n\n"
        "• <b>Select Source:</b> Choose your preferred Language and Website from the options.\n\n"
        "• <b>Download or Subscribe:</b> You can download individual chapters or Subscribe to get auto-updates when new chapters are released.\n\n"
        "<b>📢 Updates Channel:</b> @RexBots_Official"
    )
    
    buttons = [[InlineKeyboardButton("🔙 back", callback_data="start_menu")]]
    
    await edit_msg_with_pic(callback_query.message, paraphrased, InlineKeyboardMarkup(buttons))


# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat