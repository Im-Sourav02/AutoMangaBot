from pyrogram import Client, filters
import Plugins.helper as helper

@Client.on_message(filters.command("clean_tsk") & filters.private)
async def clean_tasks_cmd(client, message):
    user_id = message.from_user.id
    helper.CANCEL_TASKS[user_id] = True
    await message.reply("🗑️ All pending tasks (downloads & uploads in queue) have been marked for cancellation. Current active task will finish, but rest will be cancelled.")
