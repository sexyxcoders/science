import asyncio
import random
import time
import os

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.db import groups_col, users_col, sessions_col, questions_col, admins_col
from data.helpers import is_admin, add_points, use_coin
from data.keyboards import build_keyboard
from config import BOT_TOKEN, API_ID, API_HASH, OWNER_ID, QUESTION_CHANNEL


# -----------------------------------------
# Initialize Client
# -----------------------------------------
app = Client(
    "quiz_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# -----------------------------------------
# Safe Start (fixes Heroku Time Sync issue)
# -----------------------------------------
async def safe_start():
    while True:
        try:
            await app.start()
            print("🚀 Science Quiz Bot is running...")
            break
        except Exception as e:
            print("⏳ Time sync issue, retrying in 3 seconds...", e)
            time.sleep(3)


# -----------------------------------------
# /addadmin (owner only)
# -----------------------------------------
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


# -----------------------------------------
# /startquiz (any group member)
# -----------------------------------------
@app.on_message(filters.command("startquiz") & filters.group)
async def start_quiz(client, message):
    group_id = message.chat.id
    args = message.text.split(" ")
    category = args[1] if len(args) > 1 else "Random"

    group = groups_col.find_one({"group_id": group_id})
    if group and group.get("running", False):
        return await message.reply_text("❌ Quiz already running!")

    timer = group.get("timer", 30) if group else 30

    groups_col.update_one(
        {"group_id": group_id},
        {"$set": {"running": True, "timer": timer}},
        upsert=True
    )

    await message.reply_text(f"🎉 Quiz started!\nCategory: {category}\nTimer: {timer}s")

    # Fetch questions
    if category.lower() == "random":
        qs = list(questions_col.find())
    else:
        qs = list(questions_col.find({"category": category}))

    random.shuffle(qs)

    for q in qs:
        group_status = groups_col.find_one({"group_id": group_id})
        if not group_status.get("running", False):
            break

        # Insert session
        sessions_col.insert_one({
            "group_id": group_id,
            "question_id": q["question"],
            "answered": False
        })

        # Send question
        await app.send_message(
            group_id,
            f"📝 {q['category']} Question:\n{q['question']}",
            reply_markup=build_keyboard(q["options"], q["question"])
        )

        await asyncio.sleep(timer)

        # Show results
        scores = users_col.find().sort("points", -1)
        text = f"⏰ Time's up!\nCorrect answer: {q['answer']}\n\n🏆 Scores:\n"

        for user in scores:
            text += (
                f"{user.get('username', 'User')} - "
                f"{user.get('points', 0)} pts | "
                f"{user.get('coins', 0)} coins\n"
            )

        await app.send_message(group_id, text)

    groups_col.update_one({"group_id": group_id}, {"$set": {"running": False}})
    await app.send_message(group_id, "🏁 Quiz ended!")


# -----------------------------------------
# /stopquiz (group admin)
# -----------------------------------------
@app.on_message(filters.command("stopquiz") & filters.group)
async def stop_quiz(client, message):
    group_id = message.chat.id
    user_id = message.from_user.id

    member = await app.get_chat_member(group_id, user_id)

    if member.status in ["administrator", "creator"] or is_admin(user_id):
        groups_col.update_one(
            {"group_id": group_id},
            {"$set": {"running": False}}
        )
        await message.reply_text("🛑 Quiz stopped.")
    else:
        await message.reply_text("❌ Only admins can stop the quiz.")


# -----------------------------------------
# /addquiz (owner/admin only)
# -----------------------------------------
@app.on_message(filters.command("addquiz") & filters.private)
async def add_quiz(client, message):
    if message.from_user.id != OWNER_ID and not is_admin(message.from_user.id):
        return await message.reply_text("❌ Only owner/admin can add questions.")

    try:
        lines = message.text.splitlines()
        if len(lines) < 5:
            return await message.reply_text(
                "Invalid format.\n\nSend 5 lines:\n"
                "Category: X\nQuestion: Y\nOptions: A,B,C,D\nAnswer: A\nHint: Z"
            )

        category = lines[0].split(":")[1].strip()
        question = lines[1].split(":")[1].strip()
        options = lines[2].split(":")[1].strip().split(",")
        answer = lines[3].split(":")[1].strip()
        hint = lines[4].split(":")[1].strip()

        questions_col.update_one(
            {"question": question},
            {
                "$set": {
                    "category": category,
                    "question": question,
                    "options": options,
                    "answer": answer,
                    "hint": hint
                }
            },
            upsert=True
        )

        await message.reply_text("✅ Question added.")

        if QUESTION_CHANNEL:
            await app.send_message(
                QUESTION_CHANNEL,
                f"{category} | {question} | {','.join(options)} | {answer} | {hint}"
            )

    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")


# -----------------------------------------
# /deletequiz
# -----------------------------------------
@app.on_message(filters.command("deletequiz") & filters.private)
async def delete_quiz(client, message):
    if message.from_user.id != OWNER_ID and not is_admin(message.from_user.id):
        return await message.reply_text("❌ Only owner/admin can delete questions.")

    if len(message.command) < 2:
        return await message.reply_text("Usage: /deletequiz <question>")

    qtext = message.text.replace("/deletequiz", "").strip()

    questions_col.delete_one({"question": qtext})

    await message.reply_text("✅ Question deleted.")


# -----------------------------------------
# /set (group admin)
# -----------------------------------------
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

    groups_col.update_one(
        {"group_id": group_id},
        {"$set": {"timer": seconds}},
        upsert=True
    )

    await message.reply_text(f"✅ Timer set to {seconds}s per question.")


# -----------------------------------------
# /synsquiz - Sync all questions to channel
# -----------------------------------------
@app.on_message(filters.command("synsquiz") & filters.private)
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
                f"Category: {q['category']}\n"
                f"Question: {q['question']}\n"
                f"Options: {','.join(q['options'])}\n"
                f"Answer: {q['answer']}\n"
                f"Hint: {q['hint']}"
            )
            sent += 1
        except:
            pass

    await message.reply_text(f"✅ Synced {sent} questions.")


# -----------------------------------------
# Start the bot safely (Heroku fix)
# -----------------------------------------
asyncio.get_event_loop().run_until_complete(safe_start())

# Pyrogram sync method (NO idle())
app.run()
