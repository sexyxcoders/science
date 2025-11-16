# start.py
import asyncio
import sys
import signal
from pyrogram import errors

@app.on_message(filters.command("start"))
async def start_cmd(client, message):

    if message.chat.type == "private":
        return await message.reply_text(
            "👋 **Welcome to the Science Quiz Bot!**\n\n"
            "I can run quiz games in any group.\n\n"
            "➤ Add me to a group\n"
            "➤ Use /startquiz to begin\n\n"
            "You can also add questions using:\n"
            "• /addquiz\n"
            "• /deletequiz\n"
            "• /syncquiz\n\n"
            "Enjoy learning! 🚀"
        )

    else:
        return await message.reply_text(
            "👋 Bot is active in this group!\n"
            "Use **/startquiz** to begin the quiz."
        )