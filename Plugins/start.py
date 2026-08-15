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
from Plugins.helper import edit_msg_with_pic

logger = logging.getLogger(__name__)
logger.info("PLUGIN LOAD: start.py loaded successfully")


@Client.on_message(filters.command("start"), group=1)
async def start_msg(client, message):
    try:
        from Plugins.helper import check_fsub
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
            f"<blockquote><b>🌸 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴍᴀɴɢᴀ ʙᴏᴛ!!</b></blockquote>\n\n"
            f"<blockquote><b>📖 ᴜsᴇ /search <name> ᴛᴏ ғɪɴᴅ\n"
            f"ᴀɴʏ ᴍᴀɴɢᴀ/ᴍᴀɴʜᴡᴀ!</b></blockquote>\n\n"
            f"<blockquote><b>⚙️ ᴜsᴇ /us ᴛᴏ ᴄᴜsᴛᴏᴍɪᴢᴇ ʏᴏᴜʀ sᴇᴛᴛɪɴɢs\n"
            f"🔔 ᴜsᴇ /subs ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ sᴜʙsᴄʀɪᴘᴛɪᴏɴs</b></blockquote>"
        )
        
        START_PIC = "https://pictr.com/images/2026/08/14/xqMrZq.jpg"

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚙️ 𝖲𝖾𝗍𝗍𝗂𝗇𝗀𝗌", callback_data="settings_menu"),
                InlineKeyboardButton("📥 𝖰𝗎𝖾𝗎𝖾", callback_data="queue_menu")
            ],
            [
                InlineKeyboardButton("🔔 𝖲𝗎𝖻𝗌𝖼𝗋𝗂𝖻𝖾𝗌", callback_data="subs_menu"),
                InlineKeyboardButton("❓ 𝖧𝖾𝗅𝗉", callback_data="help_menu")
            ],
            [
                InlineKeyboardButton("❌ 𝖢𝖫𝖮𝖲𝖤", callback_data="close")
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
            await message.reply_text(f"✅ 𝘉𝘰𝘵 𝘪𝘴 𝘈𝘭𝘪𝘷𝘦! (𝘌𝘳𝘳𝘰𝘳 𝘥𝘪𝘴𝘱𝘭𝘢𝘺𝘪𝘯𝘨 𝘮𝘦𝘯𝘶: {e})")
        except:
            pass


@Client.on_callback_query(filters.regex("^help_menu$"))
async def help_menu(client, callback_query):
    paraphrased = (
        "<b>📚 𝖧𝗈𝗐 𝗍𝗈 𝖴𝗌𝖾</b>\n\n"
        "• <b>𝖲𝖾𝖺𝗋𝖼𝗁 𝖬𝖺𝗇𝗀𝖺:</b> Just send me the manga name (e.g. `One Piece`) to begin.\n\n"
        "• <b>𝖲𝖾𝗅𝖾𝖼𝗍 𝖲𝗈𝗎𝗋𝖼𝖾:</b> Choose your preferred Language and Website from the options.\n\n"
        "• <b>𝖣𝗈𝗐𝗇𝗅𝗈𝖺𝖽 𝗈𝗋 𝖲𝗎𝖻𝗌𝖼𝗋𝗂𝖻𝖾:</b> You can download individual chapters or Subscribe to get auto-updates when new chapters are released.\n\n"
        "<b>📢 Updates Channel:</b> @Infinix_Botz"
    )
    
    buttons = [[InlineKeyboardButton("🔙 𝘉𝘢𝘤𝘬", callback_data="start_menu")]]
    
    await edit_msg_with_pic(callback_query.message, paraphrased, InlineKeyboardMarkup(buttons))

