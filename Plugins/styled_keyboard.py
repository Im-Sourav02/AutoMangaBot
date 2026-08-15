"""
Utility for sending messages with styled (colored) inline keyboards in Telegram.

Usage example:
    from Plugins.styled_keyboard import send_message_with_styled_keyboard, BUTTON_COLORS

    button_layout = [
        [
            {"text": "Auto Batch", "callback_data": "autobat_cb", "emoji_id": BUTTON_COLORS["primary"]},
            {"text": "Manual", "callback_data": "manual_cb", "emoji_id": None}
        ]
    ]
    
    await send_message_with_styled_keyboard(
        client=client,
        chat_id=message.chat.id,
        text="Choose an option:",
        button_layout=button_layout
    )
"""

import inspect
import logging
import json
import aiohttp
from pyrogram import Client, raw

logger = logging.getLogger(__name__)

# Known emoji IDs for Telegram button styling
BUTTON_COLORS = {
    "primary": 5368324170671202286,
    "success": 5368324170671202287,
    "danger":  5368324170671202288,
    "default": None
}

async def send_message_with_styled_keyboard(
    client: Client,
    chat_id: int,
    text: str,
    button_layout: list[list[dict]],
    parse_mode: str = "html",
    bot_token: str = None
) -> None:
    """
    Sends a message with a styled inline keyboard.
    Checks if the local Pyrogram raw types support 'icon_custom_emoji_id'.
    If they do, it uses the raw MTProto API. Otherwise, it falls back to the HTTP Bot API.
    """
    try:
        # Check if the installed Pyrogram version supports icon_custom_emoji_id
        # in KeyboardButtonCallback
        sig = inspect.signature(raw.types.KeyboardButtonCallback.__init__)
        has_emoji_support = "icon_custom_emoji_id" in sig.parameters

        if has_emoji_support:
            # ── RAW MTPROTO METHOD ──
            rows = []
            for row in button_layout:
                buttons = []
                for btn in row:
                    kwargs = {
                        "text": btn["text"],
                        "data": btn["callback_data"].encode("utf-8")
                    }
                    if btn.get("emoji_id") is not None:
                        kwargs["icon_custom_emoji_id"] = btn["emoji_id"]
                        
                    buttons.append(raw.types.KeyboardButtonCallback(**kwargs))
                rows.append(raw.types.KeyboardButtonRow(buttons=buttons))

            reply_markup = raw.types.ReplyInlineMarkup(rows=rows)
            
            # Resolve peer
            peer = await client.resolve_peer(chat_id)
            
            # Parse text entities properly using client's parser
            parsed_text, entities = await client.parser.parse(text, parse_mode)
            
            # Send message via raw function
            await client.invoke(
                raw.functions.messages.SendMessage(
                    peer=peer,
                    message=parsed_text,
                    random_id=client.rnd_id(),
                    reply_markup=reply_markup,
                    entities=entities
                )
            )
        else:
            # ── HTTP BOT API FALLBACK METHOD ──
            token = bot_token or getattr(client, "bot_token", None)
            if not token:
                raise ValueError("bot_token is required for HTTP fallback but could not be resolved.")

            # Build the JSON markup
            inline_keyboard = []
            for row in button_layout:
                json_row = []
                for btn in row:
                    json_btn = {
                        "text": btn["text"],
                        "callback_data": btn["callback_data"]
                    }
                    if btn.get("emoji_id") is not None:
                        json_btn["icon_custom_emoji_id"] = str(btn["emoji_id"])
                    json_row.append(json_btn)
                inline_keyboard.append(json_row)

            reply_markup = {"inline_keyboard": inline_keyboard}

            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "reply_markup": json.dumps(reply_markup)
            }

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as response:
                    resp_data = await response.json()
                    if not resp_data.get("ok"):
                        raise Exception(f"HTTP Bot API Error: {resp_data}")

    except Exception as e:
        logger.error(f"Failed to send styled keyboard message: {e}")
        raise
