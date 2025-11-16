# bot.py
import asyncio
import random
from typing import List, Optional

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, ChatMember

from utils.db import groups_col, users_col, sessions_col, questions_col, admins_col
from data.helpers import is_admin, add_points, use_coin
from data.keyboards import build_keyboard
from config import BOT_TOKEN, API_ID, API_HASH, OWNER_ID, QUESTION_CHANNEL

# Create the client but DO NOT start it here (start in start.py)
app = Client(
    "quiz_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    # optional: parse_mode="html"
)

# --- Helper utilities used inside handlers ---


def normalize_username(username: str) -> str:
    """strip @ if present"""
    return username.lstrip("@").strip()


async def safe_get_user(client: Client, username_or_id: str):
    """
    Accepts either username like '@user' or a numeric id string.
    Returns User object or raises the underlying error.
    """
    username_or_id = username_or_id.strip()
    # try numeric id first
    if username_or_id.isdigit():
        return await client.get_users(int(username_or_id))
    return await client.get_users(username_or_id)


# ------------- Handlers -------------


@app.on_message(filters.command("addadmin") & filters.user(OWNER_ID))
async def add_admin(client: Client, message: Message):
    """
    /addadmin @username  (owner only)
    """
    if len(message.command) < 2:
        return await message.reply_text("Usage: /addadmin @username")

    username = normalize_username(message.command[1])
    try:
        user = await safe_get_user(client, username)
    except Exception as e:
        return await message.reply_text(f"❌ Could not find user `{username}`.\n{e}")

    admins_col.update_one(
        {"user_id": user.id},
        {"$set": {"user_id": user.id, "username": user.username or username}},
        upsert=True,
    )

    await message.reply_text(f"✅ @{(user.username or user.id)} added as admin.")


@app.on_message(filters.command("startquiz") & filters.group)
async def start_quiz(client: Client, message: Message):
    """
    /startquiz [Category]
    Any group member can start a quiz.
    """
    group_id = message.chat.id
    args = message.text.split()
    category = args[1] if len(args) > 1 else "Random"

    group = groups_col.find_one({"group_id": group_id}) or {}
    if group.get("running", False):
        return await message.reply_text("❌ Quiz already running!")

    timer = int(group.get("timer", 30))
    groups_col.update_one(
        {"group_id": group_id}, {"$set": {"running": True, "timer": timer}}, upsert=True
    )

    await message.reply_text(f"🎉 Quiz started!\nCategory: {category}\nTimer: {timer}s")

    # Fetch questions
    if category.lower() == "random":
        qs = list(questions_col.find())
    else:
        qs = list(questions_col.find({"category": category}))

    if not qs:
        await message.reply_text("❌ No questions found for this category.")
        groups_col.update_one({"group_id": group_id}, {"$set": {"running": False}})
        return

    random.shuffle(qs)

    for q in qs:
        group_status = groups_col.find_one({"group_id": group_id}) or {}
        if not group_status.get("running", False):
            break

        # Insert session
        sessions_col.insert_one(
            {
                "group_id": group_id,
                "question_id": q["question"],
                "answered": False,
                "timestamp": int(asyncio.get_event_loop().time()),
            }
        )

        # Send question
        try:
            keyboard = build_keyboard(q["options"], q["question"])
            await client.send_message(
                group_id,
                f"📝 {q['category']} Question:\n{q['question']}",
                reply_markup=keyboard,
            )
        except Exception as exc:
            # log then continue
            await client.send_message(group_id, f"⚠️ Failed to send question: {exc}")
            continue

        # wait timer seconds
        await asyncio.sleep(timer)

        # Show results for this question
        # NOTE: this is a simple overall scoreboard across users_col
        scores_cursor = users_col.find().sort("points", -1)
        text = f"⏰ Time's up!\nCorrect answer: {q['answer']}\n\n🏆 Scores:\n"

        for user in scores_cursor:
            text += (
                f"{user.get('username', 'User')} - "
                f"{user.get('points', 0)} pts | "
                f"{user.get('coins', 0)} coins\n"
            )

        await client.send_message(group_id, text)

    groups_col.update_one({"group_id": group_id}, {"$set": {"running": False}})
    await client.send_message(group_id, "🏁 Quiz ended!")


@app.on_message(filters.command("stopquiz") & filters.group)
async def stop_quiz(client: Client, message: Message):
    """
    /stopquiz — only group admins or bot admins can stop
    """
    group_id = message.chat.id
    if not message.from_user:
        return await message.reply_text("❌ Could not identify who sent the command.")

    user_id = message.from_user.id

    try:
        member: Optional[ChatMember] = await client.get_chat_member(group_id, user_id)
        status = getattr(member, "status", "")
    except Exception:
        status = ""

    if status in ["administrator", "creator"] or is_admin(user_id):
        groups_col.update_one({"group_id": group_id}, {"$set": {"running": False}})
        await message.reply_text("🛑 Quiz stopped.")
    else:
        await message.reply_text("❌ Only admins can stop the quiz.")


@app.on_message(filters.command("addquiz") & filters.private)
async def add_quiz(client: Client, message: Message):
    """
    Add a question via private message to the bot:
    Send 5 lines:
    Category: X
    Question: Y
    Options: A,B,C,D
    Answer: A
    Hint: Z
    (owner or admin only)
    """
    sender_id = message.from_user.id
    if sender_id != OWNER_ID and not is_admin(sender_id):
        return await message.reply_text("❌ Only owner/admin can add questions.")

    try:
        lines = message.text.splitlines()
        # Remove the command line if present
        if lines and lines[0].startswith("/addquiz"):
            lines = lines[1:]

        if len(lines) < 5:
            return await message.reply_text(
                "Invalid format.\n\nSend 5 lines:\n"
                "Category: X\nQuestion: Y\nOptions: A,B,C,D\nAnswer: A\nHint: Z"
            )

        category = lines[0].split(":", 1)[1].strip()
        question = lines[1].split(":", 1)[1].strip()
        options = [opt.strip() for opt in lines[2].split(":", 1)[1].strip().split(",")]
        answer = lines[3].split(":", 1)[1].strip()
        hint = lines[4].split(":", 1)[1].strip()

        questions_col.update_one(
            {"question": question},
            {
                "$set": {
                    "category": category,
                    "question": question,
                    "options": options,
                    "answer": answer,
                    "hint": hint,
                }
            },
            upsert=True,
        )

        await message.reply_text("✅ Question added.")

        if QUESTION_CHANNEL:
            try:
                await client.send_message(
                    QUESTION_CHANNEL,
                    f"Category: {category}\n"
                    f"Question: {question}\n"
                    f"Options: {','.join(options)}\n"
                    f"Answer: {answer}\n"
                    f"Hint: {hint}",
                )
            except Exception:
                pass

    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")


@app.on_message(filters.command("deletequiz") & filters.private)
async def delete_quiz(client: Client, message: Message):
    """
    Delete question by the exact question text. (owner/admin)
    Usage: /deletequiz <question text>
    """
    sender_id = message.from_user.id
    if sender_id != OWNER_ID and not is_admin(sender_id):
        return await message.reply_text("❌ Only owner/admin can delete questions.")

    if len(message.command) < 2:
        return await message.reply_text("Usage: /deletequiz <question text>")

    qtext = message.text.replace("/deletequiz", "", 1).strip()
    result = questions_col.delete_one({"question": qtext})
    if result.deleted_count:
        await message.reply_text("✅ Question deleted.")
    else:
        await message.reply_text("❌ Question not found.")


@app.on_message(filters.command("set") & filters.group)
async def set_timer(client: Client, message: Message):
    """
    /set <seconds> — Only group admins
    """
    if not message.from_user:
        return await message.reply_text("❌ Could not identify who sent the command.")

    user_id = message.from_user.id
    group_id = message.chat.id

    try:
        member = await client.get_chat_member(group_id, user_id)
        status = getattr(member, "status", "")
    except Exception:
        status = ""

    if status not in ["administrator", "creator"] and not is_admin(user_id):
        return await message.reply_text("❌ Only group admins can set timer.")

    if len(message.command) < 2:
        return await message.reply_text("Usage: /set <seconds>")

    try:
        seconds = int(message.command[1])
        groups_col.update_one({"group_id": group_id}, {"$set": {"timer": seconds}}, upsert=True)
        await message.reply_text(f"✅ Timer set to {seconds}s per question.")
    except ValueError:
        await message.reply_text("❌ seconds must be an integer.")


@app.on_message(filters.command("syncquiz") & filters.private)
async def sync_quiz(client: Client, message: Message):
    """
    Sync all questions to QUESTION_CHANNEL (owner/admin only)
    """
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
            await client.send_message(
                QUESTION_CHANNEL,
                f"Category: {q['category']}\n"
                f"Question: {q['question']}\n"
                f"Options: {','.join(q['options'])}\n"
                f"Answer: {q['answer']}\n"
                f"Hint: {q['hint']}",
            )
            sent += 1
        except Exception:
            continue

    await message.reply_text(f"✅ Synced {sent} questions.")


# Exported for start.py to use if needed
__all__ = ["app"]