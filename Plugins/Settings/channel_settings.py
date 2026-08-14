# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat


from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Database.database import Seishiro
from Plugins.helper import admin, get_styled_text, user_states, edit_msg_with_pic
from Plugins.Settings.input_helper import timeout_handler
import asyncio
import logging
import difflib
from Database.subscriptions import SubscriptionDB

logger = logging.getLogger(__name__)

@Client.on_callback_query(filters.regex("^header_auto_update_channels$"))
async def auc_menu(client, callback_query):
    text = get_styled_text("Your Auto Update Channel")
    
    buttons = [
        [
            InlineKeyboardButton("+ add +", callback_data="auc_add"),
            InlineKeyboardButton("- remove all -", callback_data="auc_rem_all")
        ],
        [
            InlineKeyboardButton("- remove channel -", callback_data="auc_rem_channel")
        ],
        [
            InlineKeyboardButton("refresh", callback_data="header_auto_update_channels"),
            InlineKeyboardButton("import", callback_data="auc_import")
        ],
        [
            InlineKeyboardButton("⬅ back", callback_data="settings_menu"),
            InlineKeyboardButton("* close *", callback_data="stats_close")
        ]
    ]
    
    channels = await Seishiro.get_auto_update_channels()
    text = (
        "<b>Auto Update Channels (AUC)</b>\n\n"
        f"<b>Channels:</b> {len(channels)}\n"
        "<i>These channels automatically receive new chapter posts.</i>\n\n"
        "<blockquote>Select a channel to manage or add a new one.</blockquote>"
    )

    try:
        await edit_msg_with_pic(callback_query.message, text, InlineKeyboardMarkup(buttons))
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            logger.error(f"Error editing AUC menu: {e}")
            
    await callback_query.answer()

@Client.on_callback_query(filters.regex("^auc_add$"))
async def auc_add_cb(client, callback_query):
    text = get_styled_text(
        "<b>➕ Add Auto Update Channel</b>\n\n"
        "Send the Channel ID (e.g. -100xxx) to add.\n"
        "<i>Bot must be admin in the channel to verify!</i>\n"
        "<i>(Auto-close in 30s)</i>"
    )
    user_states[callback_query.from_user.id] = {"state": "waiting_auc_id"}
    
    buttons = [[InlineKeyboardButton("❌ cancel", callback_data="cancel_input")]]
    await edit_msg_with_pic(callback_query.message, text, InlineKeyboardMarkup(buttons))
    
    asyncio.create_task(timeout_handler(client, callback_query.message, callback_query.from_user.id, "waiting_auc_id"))

@Client.on_callback_query(filters.regex("^auc_rem_all$"))
async def auc_rem_all_cb(client, callback_query):
    await Seishiro.clear_auto_update_channels()
    await callback_query.answer("✅ All channels removed!", show_alert=True)
    await auc_menu(client, callback_query) # Refresh menu

@Client.on_callback_query(filters.regex("^auc_import$"))
async def auc_import_cb(client, callback_query):
    await callback_query.answer("Import feature coming soon!", show_alert=True)

@Client.on_callback_query(filters.regex("^auc_rem_channel$"))
async def auc_rem_channel_cb(client, callback_query):
    text = get_styled_text(
        "<b>➖ Remove Auto Update Channel</b>\n\n"
        "Send the Channel ID (e.g. -100xxx) to remove.\n"
        "<i>(Auto-close in 30s)</i>"
    )
    user_states[callback_query.from_user.id] = {"state": "waiting_auc_rem_id"}
    
    buttons = [[InlineKeyboardButton("❌ cancel", callback_data="cancel_input")]]
    await edit_msg_with_pic(callback_query.message, text, InlineKeyboardMarkup(buttons))
    
    asyncio.create_task(timeout_handler(client, callback_query.message, callback_query.from_user.id, "waiting_auc_rem_id"))


@Client.on_callback_query(filters.regex(r"^header_auto_upload_channels(?:_page_(\d+))?$"))
async def aup_menu(client, callback_query):
    match = callback_query.matches[0]
    page = int(match.group(1)) if match.group(1) else 1
    channels = await Seishiro.get_auto_upload_channels(callback_query.from_user.id)
    
    ITEMS_PER_PAGE = 5
    total_pages = (len(channels) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE or 1
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_channels = channels[start_idx:end_idx]
    
    text = "<b>Auto Upload Channels</b>\n\n"
    for i, ch in enumerate(page_channels):
        title = ch.get("title", "Unknown Channel")
        text += f"<b>{start_idx + i}.</b> {title}\n"
    if not page_channels:
        text += "<i>No channels found.</i>\n"
        
    buttons = []
    
    # Row for channel indices
    idx_row_1 = []
    idx_row_2 = []
    for i, ch in enumerate(page_channels):
        btn = InlineKeyboardButton(str(start_idx + i), callback_data=f"aup_view_{ch['_id']}")
        if len(idx_row_1) < 2:
            idx_row_1.append(btn)
        else:
            idx_row_2.append(btn)
            
    if idx_row_1: buttons.append(idx_row_1)
    if idx_row_2: buttons.append(idx_row_2)
    
    # Pagination row
    buttons.append([
        InlineKeyboardButton(f"Total Channels: {len(channels)}", callback_data="ignore"),
        InlineKeyboardButton(f"Page No: {page}", callback_data="ignore")
    ])
    
    # Nav row
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"header_auto_upload_channels_page_{page-1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"header_auto_upload_channels_page_{page+1}"))
    if nav_row:
        buttons.append(nav_row)
        
    # Actions row
    buttons.append([
        InlineKeyboardButton("+ Add +", callback_data="aup_add"),
        InlineKeyboardButton("- Remove All -", callback_data="aup_rem_all")
    ])
    buttons.append([
        InlineKeyboardButton("Refresh", callback_data="header_auto_upload_channels"),
        InlineKeyboardButton("Import", callback_data="aup_import")
    ])
    buttons.append([
        InlineKeyboardButton("⬅ Back", callback_data="settings_menu"),
        InlineKeyboardButton("✴ Close ✴", callback_data="stats_close")
    ])
    
    try:
        await edit_msg_with_pic(callback_query.message, text, InlineKeyboardMarkup(buttons))
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            logger.error(f"Error editing AUC menu: {e}")
            
    await callback_query.answer()

@Client.on_callback_query(filters.regex(r"^aup_view_(-?\d+)$"))
async def aup_view_channel_cb(client, callback_query):
    channel_id = int(callback_query.matches[0].group(1))
    
    text = (
        "<b>Pinned Message</b>\n"
        "And Those Who Want Muti Language Send me Al...\n\n"
        "Are you sure you want to unsubscribe/remove this channel?"
    )
    
    buttons = [
        [InlineKeyboardButton("✖ UNSUBSCRIBE ✖", callback_data=f"aup_rem_{channel_id}")],
        [
            InlineKeyboardButton("⬅ BACK", callback_data="header_auto_upload_channels"),
            InlineKeyboardButton("| CLOSE |", callback_data="stats_close")
        ]
    ]
    
    await edit_msg_with_pic(callback_query.message, text, InlineKeyboardMarkup(buttons))
    await callback_query.answer()

@Client.on_callback_query(filters.regex(r"^aup_rem_(-?\d+)$"))
async def aup_rem_specific_cb(client, callback_query):
    channel_id = int(callback_query.matches[0].group(1))
    await Seishiro.remove_auto_upload_channel(callback_query.from_user.id, channel_id)
    await callback_query.answer("Channel Unsubscribed/Removed!", show_alert=True)
    await aup_menu(client, callback_query)

@Client.on_callback_query(filters.regex("^aup_add$"))
async def aup_add_cb(client, callback_query):
    text = (
        "<b>Send me the channel username or Channel ID or Forward Message from Channel.</b>\n\n"
        "You can Send Mutiple at Once , Bot will Add all target channel in db\n\n"
        "Stop Listing By using /stop"
    )
    user_states[callback_query.from_user.id] = "WAITING_AUP_IDS"
    
    buttons = [[InlineKeyboardButton("❌ cancel", callback_data="cancel_aup_add")]]
    await edit_msg_with_pic(callback_query.message, text, InlineKeyboardMarkup(buttons))
    await callback_query.answer()

@Client.on_callback_query(filters.regex("^cancel_aup_add$"))
async def cancel_aup_add_cb(client, callback_query):
    uid = callback_query.from_user.id
    if uid in user_states and user_states[uid] == "WAITING_AUP_IDS":
        del user_states[uid]
    await callback_query.answer("Cancelled addition.", show_alert=True)
    await aup_menu(client, callback_query)

@Client.on_callback_query(filters.regex("^aup_rem_all$"))
async def aup_rem_all_cb(client, callback_query):
    await Seishiro.clear_auto_upload_channels(callback_query.from_user.id)
    await callback_query.answer("✅ All channels removed!", show_alert=True)
    await aup_menu(client, callback_query)

@Client.on_callback_query(filters.regex("^aup_import$"))
async def aup_import_cb(client, callback_query):
    await callback_query.answer("Import feature coming soon!", show_alert=True)


@Client.on_callback_query(filters.regex("^set_channel_btn$"))
async def set_channel_cb(client, callback_query):
    text = get_styled_text(
        "<b>📢 Set Upload Channel</b>\n\n"
        "Send the Channel ID (-100...) where manga chapters will be uploaded.\n"
        "<i>Make sure the bot is Admin there!</i>\n"
        "<i>(Auto-close in 30s)</i>"
    )
    user_states[callback_query.from_user.id] = {"state": "waiting_channel"}
    
    buttons = [[InlineKeyboardButton("❌ cancel", callback_data="cancel_input")]]
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
    
    asyncio.create_task(timeout_handler(client, callback_query.message, callback_query.from_user.id, "waiting_channel"))

@Client.on_callback_query(filters.regex("^(header_dump_channel|set_dump_channel_btn)$"))
async def dump_channel_menu(client, callback_query):
    user_settings = await Seishiro.settings_db.get_settings(callback_query.from_user.id)
    dump_id = user_settings.get("dump_channel_id")
    status = f"<code>{dump_id}</code>" if dump_id else "None"
    
    text = (
        f"<b>➥ Dump Channel</b>\n"
        f"<b>➥ Your Value: {status}</b>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("set / change", callback_data="set_dump_input"),
            InlineKeyboardButton("delete", callback_data="rem_dump_channel")
        ],
        [
            InlineKeyboardButton("⬅ back", callback_data="settings_menu"),
            InlineKeyboardButton("* close *", callback_data="stats_close")
        ]
    ]
    
    try:
        if callback_query.message.photo:
             await callback_query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        else:
             await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
    except Exception as e:
         pass

# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat


@Client.on_callback_query(filters.regex("^set_dump_input$"))
async def set_dump_input_cb(client, callback_query):
    text = get_styled_text(
        "<b>🗑️ Set Dump Channel</b>\n\n"
        "Send the Channel ID for the Dump Channel.\n"
        "<i>Send ID now...</i>\n"
        "<i>(Auto-close in 30s)</i>"
    )
    user_states[callback_query.from_user.id] = {"state": "waiting_dump_channel"}
    
    buttons = [
        [InlineKeyboardButton("❌ cancel", callback_data="cancel_input")],
        [InlineKeyboardButton("⬅ back", callback_data="header_dump_channel")]
    ]
    await edit_msg_with_pic(callback_query.message, text, InlineKeyboardMarkup(buttons))
    
    asyncio.create_task(timeout_handler(client, callback_query.message, callback_query.from_user.id, "waiting_dump_channel"))

@Client.on_callback_query(filters.regex("^rem_dump_channel$"))
async def rem_dump_channel_cb(client, callback_query):
    await Seishiro.settings_db.update_setting(callback_query.from_user.id, "dump_channel_id", None)
    await callback_query.answer("Removed Dump Channel!", show_alert=True)
    await dump_channel_menu(client, callback_query)


@Client.on_message(filters.command("set_chnl") & filters.private & admin)
async def set_channel_cmd(client, message):
    if len(message.command) != 2:
        return await message.reply("usage: /set_chnl <channel_id>")
    try:
        cid = int(message.command[1])
        try:
             chat = await client.get_chat(cid)
        except:
             return await message.reply("❌ bot cannot access this channel.")
        await Seishiro.set_default_channel(cid)
        await message.reply(f"<blockquote><b>✅ upload channel set: {cid}</b></blockquote>", parse_mode=enums.ParseMode.HTML)
    except ValueError:
        await message.reply("❌ invalid id")

@Client.on_message(filters.command("view_chnl") & filters.private & admin)
async def view_channel_cmd(client, message):
    cid = await Seishiro.get_default_channel()
    await message.reply(f"<blockquote><b>📺 Upload Channel: {cid}</b></blockquote>", parse_mode=enums.ParseMode.HTML)

@Client.on_message(filters.command("rem_chnl") & filters.private & admin)
async def rem_channel_cmd(client, message):
    await Seishiro.set_default_channel(None)
    await message.reply(f"<blockquote><b>✅ Upload Channel Removed</b></blockquote>", parse_mode=enums.ParseMode.HTML)


# CantarellaBots
# Don't Remove Credit
# Telegram Channel @CantarellaBots
#Supoort group @rexbotschat


@Client.on_message(filters.private & ~filters.command(['start', 'help', 'settings', 'search']), group=99)
async def aup_id_input_handler(client, message):
    uid = message.from_user.id
    if uid in user_states and user_states[uid] == 'WAITING_AUP_IDS':
        if message.text and message.text.lower() == '/stop':
            del user_states[uid]
            await message.reply('Finished adding channels.')
            
            class DummyQuery:
                def __init__(self, msg, uid):
                    self.message = msg
                    self.from_user = type('User', (), {'id': uid})()
                    self.matches = [type('Match', (), {'group': lambda self, i: '1'})()]
                async def answer(self, *args, **kwargs):
                    pass
            dummy_q = DummyQuery(message, uid)
            await aup_menu(client, dummy_q)
            return

        chat_id = None
        if message.forward_from_chat:
            chat_id = message.forward_from_chat.id
        elif message.text:
            try:
                chat_id = int(message.text.strip())
            except ValueError:
                chat_id = message.text.strip()
                
        if not chat_id:
            await message.reply('Please send a valid Channel ID, Username, or forward a message.')
            return
            
        try:
            chat = await client.get_chat(chat_id)
            title = chat.title or str(chat.id)
            await Seishiro.add_auto_upload_channel(uid, chat.id, title)
            
            # Fuzzy match and link subscriptions for this user
            subs_db = SubscriptionDB(Seishiro.database)
            user_subs = await subs_db.get_user_subscriptions(uid)
            linked_count = 0
            
            for sub in user_subs:
                sub_title = sub.get('title', '')
                if not sub_title: continue
                # Match threshold 0.8
                ratio = difflib.SequenceMatcher(None, sub_title.lower(), title.lower()).ratio()
                if ratio > 0.8 or sub_title.lower() in title.lower() or title.lower() in sub_title.lower():
                    await subs_db.update_auto_upload_channel_id(uid, sub['url'], chat.id)
                    linked_count += 1
            
            msg = f'✅ Channel Added: {chat.id} ({title})'
            if linked_count > 0:
                msg += f'\n🔗 Linked to {linked_count} subscribed manga(s).'
            await message.reply(msg)
        except Exception as e:
            await message.reply(f'Failed to add channel: {e}')
