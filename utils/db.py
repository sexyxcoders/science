from pymongo import MongoClient
from config import MONGO_URI

# ------------------------
# MongoDB Client
# ------------------------
client = MongoClient(MONGO_URI)
db = client["science_quiz_bot"]

# ------------------------
# Collections
# ------------------------
groups_col = db["groups"]         # Stores group info: running quiz, timer
users_col = db["users"]           # Stores user points, coins, etc.
sessions_col = db["sessions"]     # Stores current quiz sessions per group
questions_col = db["questions"]   # Stores all quiz questions
admins_col = db["admins"]         # Stores bot admins
