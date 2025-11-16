# start.py
import asyncio
import sys
import signal
from pyrogram import filters
from bot import app   # <-- IMPORT the main app from bot.py


# -----------------------------------------
# /start command
# -----------------------------------------
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


# -----------------------------------------
# Safe Start function (handles runtime sync)
# -----------------------------------------
async def safe_start():
    while True:
        try:
            await app.start()
            print("🚀 Bot Started Successfully!")
            break
        except RuntimeError as e:
            print("⚠️ Time Sync Error — Retrying…", e)
            await asyncio.sleep(3)


# -----------------------------------------
# Main Runner
# -----------------------------------------
async def main():
    await safe_start()

    print("⚡ Bot is running. Press Ctrl+C to stop.")

    # Wait forever
    stop_event = asyncio.Event()
    await stop_event.wait()

    await app.stop()


# -----------------------------------------
# Run main()
# -----------------------------------------
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())