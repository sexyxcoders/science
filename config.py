import os

# ------------------------
# Pyrogram Bot Configuration
# ------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8340952338:AAEBc1ADx1GDN3crCbXskzcW-bSHa6E7uwM")          # Bot token from BotFather
API_ID = int(os.environ.get("API_ID", "22657083"))           # Your Telegram API ID
API_HASH = os.environ.get("API_HASH", "d6186691704bd901bdab275ceaab88f3")           # Your Telegram API HASH
OWNER_ID = int(os.environ.get("OWNER_ID", "8449801101"))       # Telegram user ID of the bot owner

# ------------------------
# MongoDB Configuration
# ------------------------
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://pikachuxivan_db_user:pikachuxivan@cluster0.9c3hko7.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")         # MongoDB connection URI

# ------------------------
# Question Channel (Optional)
# ------------------------
# All questions can be synced to this channel for backup or public reference
QUESTION_CHANNEL = os.environ.get("QUESTION_CHANNEL", "@Sciencedatabased")  # e.g., "@my_question_channel"
