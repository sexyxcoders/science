import asyncio
import random
import logging
from pyrogram import Client, filters
from pyrogram.errors import BadMsgNotification
from data.helpers import is_admin, add_points, use_coin
from data.keyboards import build_keyboard
from utils.db import groups_col, users_col, sessions_col, questions_col, admins_col
from config import BOT_TOKEN, API_ID, API_HASH, OWNER_ID, QUESTION_CHANNEL

# ------------------------
# Logging
# ------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------
# Initialize bot
# ------------------------
app = Client("quiz_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ------------------------
# /addadmin - Owner only
# ------------------------
@app.on_message(filters.command("addadmin") & filters.user(OWNER_ID))
async def add_admin(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /addadmin @username")
    username = message.command[1].replace("@", "")
    user = await app.get_users(username)
    admins_col.update_one({"user_id": user.id}, {"$set": {"user_id": user.id, "username": username}}, upsert=True)
    await message.reply_text(f"✅ {username} added as bot admin.")

# ------------------------
# /startquiz - Any member
# ------------------------
@app.on_message(filters.command("startquiz") & filters.group)
async def start_quiz(client, message):
    group_id = message.chat.id
    args = message.text.split(" ")
    category = args[1] if len(args) > 1 else "Random"

    group = groups_col.find_one({"group_id": group_id})
    if group and group.get("running", False):
        return await message.reply_text("❌ Quiz already running!")

    timer = group.get("timer", 30) if group else 30
    groups_col.update_one({"group_id": group_id}, {"$set": {"running": True, "timer": timer}}, upsert=True)
    await message.reply_text(f"🎉 Quiz started! Category: {category}, Timer: {timer}s")

    qs = list(questions_col.find({"category": category})) if category.lower() != "random" else list(questions_col.find())
    random.shuffle(qs)

    for q in qs:
        group_status = groups_col.find_one({"group_id": group_id})
        if not group_status.get("running", False):
            break

        sessions_col.insert_one({"group_id": group_id, "question_id": q["question"], "answered": False})
        await app.send_message(group_id, f"📝 {q['category']} Question:\n{q['question']}",
                               reply_markup=build_keyboard(q["options"], q["question"]))
        await asyncio.sleep(timer)

        scores = users_col.find().sort("points", -1)
        text = f"⏰ Time's up! Correct answer: {q['answer']}\n\n🏆 Scores:\n"
        for user in scores:
            text += f"{user.get('username','User')} - {user.get('points',0)} pts | {user.get('coins',0)} coins\n"
        await app.send_message(group_id, text)

    groups_col.update_one({"group_id": group_id}, {"$set": {"running": False}})
    await app.send_message(group_id, "🏁 Quiz ended!")

# ------------------------
# /stopquiz - Admins only
# ------------------------
@app.on_message(filters.command("stopquiz") & filters.group)
async def stop_quiz(client, message):
    group_id = message.chat.id
    user_id = message.from_user.id
    member = await app.get_chat_member(group_id, user_id)
    if member.status in ["administrator", "creator"] or is_admin(user_id):
        groups_col.update_one({"group_id": group_id}, {"$set": {"running": False}})
        await message.reply_text("🛑 Quiz stopped by admin.")
    else:
        await message.reply_text("❌ Only group admins can stop the quiz.")

# ------------------------
# /addquiz - Admin/Owner
# ------------------------
@app.on_message(filters.command("addquiz") & filters.private)
async def add_quiz(client, message):
    if message.from_user.id != OWNER_ID and not is_admin(message.from_user.id):
        return await message.reply_text("❌ Only owner/admin can add questions.")
    try:
        lines = message.text.splitlines()
        if len(lines) < 5:
            return await message.reply_text("Send 5 lines: Category, Question, Options, Answer, Hint.")
        category = lines[0].split(":")[1].strip()
        question = lines[1].split(":")[1].strip()
        options = lines[2].split(":")[1].strip().split(",")
        answer = lines[3].split(":")[1].strip()
        hint = lines[4].split(":")[1].strip()
        questions_col.update_one(
            {"question": question},
            {"$set": {"category": category, "question": question, "options": options, "answer": answer, "hint": hint}},
            upsert=True
        )
        await message.reply_text("✅ Question added successfully.")
        if QUESTION_CHANNEL:
            await app.send_message(QUESTION_CHANNEL, f"{category} | {question} | {','.join(options)} | {answer} | {hint}")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

# ------------------------
# /deletequiz - Admin/Owner
# ------------------------
@app.on_message(filters.command("deletequiz") & filters.private)
async def delete_quiz(client, message):
    if message.from_user.id != OWNER_ID and not is_admin(message.from_user.id):
        return await message.reply_text("❌ Only owner/admin can delete questions.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: /deletequiz <question>")
    qtext = message.text.replace("/deletequiz", "").strip()
    questions_col.delete_one({"question": qtext})
    await message.reply_text("✅ Question deleted.")

# ------------------------
# /set - Group admins only
# ------------------------
@app.on_message(filters.command("set") & filters.group)
async def set_timer(client, message):
    user_id = message.from_user.id
    group_id = message.chat.id
    member = await app.get_chat_member(group_id, user_id)
    if member.status not in ["administrator", "creator"] and not is_admin(user_id):
        return await message.reply_text("❌ Only group admins can set timer.")
    if len(message.command) < 2:
        return await message.reply_text("Usage: /set <seconds>")
    seconds = int(message.command[1])
    groups_col.update_one({"group_id": group_id}, {"$set": {"timer": seconds}}, upsert=True)
    await message.reply_text(f"✅ Timer set to {seconds} seconds per question.")

# ------------------------
# /synsquiz - Sync all questions to channel
# ------------------------
@app.on_message(filters.command("synsquiz") & filters.private)
async def sync_quiz(client, message):
    user_id = message.from_user.id
    if user_id != OWNER_ID and not is_admin(user_id):
        return await message.reply_text("❌ Only owner/admin can sync questions.")
    if not QUESTION_CHANNEL:
        return await message.reply_text("❌ QUESTION_CHANNEL not set in config.py")
    all_questions = list(questions_col.find())
    if not all_questions:
        return await message.reply_text("❌ No questions found to sync.")
    sent_count = 0
    for q in all_questions:
        try:
            await app.send_message(
                QUESTION_CHANNEL,
                f"Category: {q['category']}\nQuestion: {q['question']}\nOptions: {','.join(q['options'])}\nAnswer: {q['answer']}\nHint: {q['hint']}"
            )
            sent_count += 1
        except:
            continue
    await message.reply_text(f"✅ Synced {sent_count} questions to the channel.")

# ------------------------
# MAIN LOOP WITH RETRY
# ------------------------
if __name__ == "__main__":
    while True:
        try:
            logger.info("🚀 Science Quiz Bot is running...")
            app.run()
        except BadMsgNotification:
            logger.warning("⏳ Time sync issue, retrying in 3 seconds...")
            asyncio.sleep(3)
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            asyncio.sleep(5)