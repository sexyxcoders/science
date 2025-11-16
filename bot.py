import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.db import groups_col, users_col, sessions_col, questions_col, admins_col
from data.helpers import is_admin
from data.keyboards import build_keyboard
from config import BOT_TOKEN, API_ID, API_HASH, OWNER_ID, QUESTION_CHANNEL

# ---------------------------
# Initialize bot client
# ---------------------------
app = Client(
    "quiz_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------------------------
# /start command
# ---------------------------
@app.on_message(filters.command("start") & filters.private)
async def start_bot(client, message):
    await message.reply_text(
        "👋 Hello! I am the Science Quiz Bot.\n\n"
        "Commands:\n"
        "/addquiz - Add a new quiz question (owner/admin)\n"
        "/deletequiz - Delete a quiz question (owner/admin)\n"
        "/startquiz - Start quiz in a group\n"
        "/stopquiz - Stop quiz in a group\n"
        "/set - Set timer per question (group admin)\n"
        "/syncquiz - Sync all questions to a channel (owner/admin)"
    )

# ---------------------------
# /addadmin (owner only)
# ---------------------------
@app.on_message(filters.command("addadmin") & filters.user(OWNER_ID))
async def add_admin(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /addadmin @username")

    username = message.command[1].replace("@", "")
    user = await app.get_users(username)

    admins_col.update_one(
        {"user_id": user.id},
        {"$set": {"user_id": user.id, "username": username}},
        upsert=True
    )

    await message.reply_text(f"✅ {username} added as admin.")

# ---------------------------
# /addquiz (owner/admin)
# ---------------------------
@app.on_message(filters.command("addquiz") & filters.private)
async def add_quiz(client, message):
    user_id = message.from_user.id
    if user_id != OWNER_ID and not is_admin(user_id):
        return await message.reply_text("❌ Only owner/admin can add questions.")

    try:
        text = message.text.replace("/addquiz", "").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 5:
            return await message.reply_text(
                "Invalid format. Send in this format:\n\n"
                "Category: X\nQuestion: Y\nOptions: A,B,C,D\nAnswer: A\nHint: Z"
            )

        # Parse lines
        data = {}
        for line in lines:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            data[key.strip().lower()] = value.strip()

        category = data.get("category")
        question = data.get("question")
        options = data.get("options", "").split(",")
        answer = data.get("answer")
        hint = data.get("hint", "")

        if not all([category, question, options, answer]):
            return await message.reply_text("❌ Missing required fields.")

        questions_col.update_one(
            {"question": question},
            {"$set": {
                "category": category,
                "question": question,
                "options": options,
                "answer": answer,
                "hint": hint
            }},
            upsert=True
        )

        await message.reply_text("✅ Question added successfully!")

        if QUESTION_CHANNEL:
            await app.send_message(
                QUESTION_CHANNEL,
                f"Category: {category}\nQuestion: {question}\nOptions: {','.join(options)}\nAnswer: {answer}\nHint: {hint}"
            )

    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

# ---------------------------
# /deletequiz (owner/admin)
# ---------------------------
@app.on_message(filters.command("deletequiz") & filters.private)
async def delete_quiz(client, message):
    user_id = message.from_user.id
    if user_id != OWNER_ID and not is_admin(user_id):
        return await message.reply_text("❌ Only owner/admin can delete questions.")

    if len(message.command) < 2:
        return await message.reply_text("Usage: /deletequiz <question>")

    question_text = " ".join(message.command[1:])
    result = questions_col.delete_one({"question": question_text})
    if result.deleted_count:
        await message.reply_text(f"✅ Question '{question_text}' deleted.")
    else:
        await message.reply_text(f"❌ Question '{question_text}' not found.")

# ---------------------------
# /startquiz (group)
# ---------------------------
@app.on_message(filters.command("startquiz") & filters.group)
async def start_quiz(client, message):
    group_id = message.chat.id
    group = groups_col.find_one({"group_id": group_id})
    if group and group.get("running", False):
        return await message.reply_text("❌ Quiz already running!")

    timer = group.get("timer", 30) if group else 30
    groups_col.update_one({"group_id": group_id}, {"$set": {"running": True, "timer": timer}}, upsert=True)

    await message.reply_text(f"🎉 Quiz started!\nTimer: {timer}s per question.")

    qs = list(questions_col.find())
    if not qs:
        groups_col.update_one({"group_id": group_id}, {"$set": {"running": False}})
        return await message.reply_text("❌ No questions found.")

    random.shuffle(qs)

    for q in qs:
        group_status = groups_col.find_one({"group_id": group_id})
        if not group_status.get("running", False):
            break

        # Insert session
        sessions_col.insert_one({
            "group_id": group_id,
            "question": q["question"],
            "answered": False
        })

        # Send question
        await app.send_message(
            group_id,
            f"📝 {q['category']} Question:\n{q['question']}",
            reply_markup=build_keyboard(q["options"], q["question"])
        )

        await asyncio.sleep(timer)

        # Show correct answer
        await app.send_message(group_id, f"⏰ Time's up! Correct answer: {q['answer']}")

    groups_col.update_one({"group_id": group_id}, {"$set": {"running": False}})
    await app.send_message(group_id, "🏁 Quiz ended!")

# ---------------------------
# /stopquiz (group admin)
# ---------------------------
@app.on_message(filters.command("stopquiz") & filters.group)
async def stop_quiz(client, message):
    group_id = message.chat.id
    user_id = message.from_user.id
    member = await app.get_chat_member(group_id, user_id)

    if member.status in ["administrator", "creator"] or is_admin(user_id):
        groups_col.update_one({"group_id": group_id}, {"$set": {"running": False}})
        await message.reply_text("🛑 Quiz stopped.")
    else:
        await message.reply_text("❌ Only admins can stop the quiz.")

# ---------------------------
# /set timer (group admin)
# ---------------------------
@app.on_message(filters.command("set") & filters.group)
async def set_timer(client, message):
    user_id = message.from_user.id
    group_id = message.chat.id
    member = await app.get_chat_member(group_id, user_id)

    if member.status not in ["administrator", "creator"] and not is_admin(user_id):
        return await message.reply_text("❌ Only group admins can set timer.")

    if len(message.command) < 2:
        return await message.reply_text("Usage: /set <seconds>")

    try:
        seconds = int(message.command[1])
        groups_col.update_one({"group_id": group_id}, {"$set": {"timer": seconds}}, upsert=True)
        await message.reply_text(f"✅ Timer set to {seconds}s per question.")
    except:
        await message.reply_text("❌ Invalid number.")

# ---------------------------
# /syncquiz (owner/admin)
# ---------------------------
@app.on_message(filters.command("syncquiz") & filters.private)
async def sync_quiz(client, message):
    user_id = message.from_user.id
    if user_id != OWNER_ID and not is_admin(user_id):
        return await message.reply_text("❌ Only owner/admin can sync questions.")

    if not QUESTION_CHANNEL:
        return await message.reply_text("❌ QUESTION_CHANNEL not set!")

    all_questions = list(questions_col.find())
    if not all_questions:
        return await message.reply_text("❌ No questions found.")

    sent = 0
    for q in all_questions:
        try:
            await app.send_message(
                QUESTION_CHANNEL,
                f"Category: {q['category']}\nQuestion: {q['question']}\nOptions: {','.join(q['options'])}\nAnswer: {q['answer']}\nHint: {q['hint']}"
            )
            sent += 1
        except:
            continue

    await message.reply_text(f"✅ Synced {sent} questions.")

# ---------------------------
# Safe start
# ---------------------------
async def safe_start():
    while True:
        try:
            await app.start()
            print("🚀 Science Quiz Bot is running...")
            break
        except RuntimeError as e:
            print("⏳ RuntimeError, retrying in 3 seconds...", e)
            await asyncio.sleep(3)

# ---------------------------
# Main
# ---------------------------
async def main():
    await safe_start()
    stop_event = asyncio.Event()
    await stop_event.wait()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())