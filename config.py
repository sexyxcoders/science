import os

# ------------------------
# Pyrogram Bot Configuration
# ------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")          # Bot token from BotFather
API_ID = int(os.environ.get("API_ID"))           # Your Telegram API ID
API_HASH = os.environ.get("API_HASH")           # Your Telegram API HASH
OWNER_ID = int(os.environ.get("OWNER_ID"))       # Telegram user ID of the bot owner

# ------------------------
# MongoDB Configuration
# ------------------------
MONGO_URI = os.environ.get("MONGO_URI")         # MongoDB connection URI

# ------------------------
# Question Channel (Optional)
# ------------------------
# All questions can be synced to this channel for backup or public reference
QUESTION_CHANNEL = os.environ.get("QUESTION_CHANNEL")  # e.g., "@my_question_channel"
