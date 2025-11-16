from utils.db import admins_col, users_col, groups_col

# ------------------------
# Check if user is a bot admin
# ------------------------
def is_admin(user_id: int) -> bool:
    """Return True if the user is a bot admin."""
    return admins_col.find_one({"user_id": user_id}) is not None

# ------------------------
# Add points to a user
# ------------------------
def add_points(user_id: int, points: int):
    """Add points to a user; creates user if not exists."""
    users_col.update_one(
        {"user_id": user_id},
        {"$inc": {"points": points}},
        upsert=True
    )

# ------------------------
# Deduct coin for hint
# ------------------------
def use_coin(user_id: int) -> bool:
    """Deduct 1 coin from user; return True if successful, False if not enough coins."""
    user = users_col.find_one({"user_id": user_id})
    if user and user.get("coins", 0) > 0:
        users_col.update_one({"user_id": user_id}, {"$inc": {"coins": -1}})
        return True
    return False

# ------------------------
# Add coins to user (e.g., for inviting bot to groups)
# ------------------------
def add_coins(user_id: int, coins: int = 1):
    """Add coins to a user."""
    users_col.update_one(
        {"user_id": user_id},
        {"$inc": {"coins": coins}},
        upsert=True
    )

# ------------------------
# Check if a group is running quiz
# ------------------------
def is_quiz_running(group_id: int) -> bool:
    """Return True if a quiz is currently running in the group."""
    group = groups_col.find_one({"group_id": group_id})
    return group.get("running", False) if group else False

# ------------------------
# Set group timer
# ------------------------
def set_group_timer(group_id: int, seconds: int):
    """Set per-group quiz timer."""
    groups_col.update_one(
        {"group_id": group_id},
        {"$set": {"timer": seconds}},
        upsert=True
    )

# ------------------------
# Get group timer
# ------------------------
def get_group_timer(group_id: int) -> int:
    """Return the timer set for the group; default 30 seconds."""
    group = groups_col.find_one({"group_id": group_id})
    return group.get("timer", 30) if group else 30
