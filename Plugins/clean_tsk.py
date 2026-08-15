from pyrogram import Client, filters
import Plugins.helper as helper
from Plugins.task_manager import task_manager

@Client.on_message(filters.command("clean_tsk") & filters.private)
async def clean_tasks_cmd(client, message):
    user_id = message.from_user.id
    helper.CANCEL_TASKS[user_id] = True
    task_manager.clear_queue(message.chat.id)
    await message.reply("🗑️ All pending tasks in your queue have been cancelled. The currently downloading task has been marked to stop.")
