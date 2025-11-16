from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ------------------------
# Build quiz options keyboard
# ------------------------
def build_keyboard(options: list, question_id: str) -> InlineKeyboardMarkup:
    """
    Create inline keyboard for a question.
    Each option is a button. Also adds a hint button.
    
    :param options: List of answer options (strings)
    :param question_id: Unique ID of the question
    :return: InlineKeyboardMarkup object
    """
    keyboard = []
    
    # Add each option as a separate button
    for opt in options:
        keyboard.append([InlineKeyboardButton(opt, callback_data=f"answer|{question_id}|{opt}")])
    
    # Add hint button at the bottom
    keyboard.append([InlineKeyboardButton("💡 Hint", callback_data=f"hint|{question_id}")])
    
    return InlineKeyboardMarkup(keyboard)
