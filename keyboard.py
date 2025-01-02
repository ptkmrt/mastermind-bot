from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# TODO (maybe one day): fix the button issue for play and end
reply_keys = [[
    InlineKeyboardButton("rules", callback_data="/rules"),
    # InlineKeyboardButton("play", callback_data="/play"),  # for now :P
    InlineKeyboardButton("help", callback_data="/help"),
    # InlineKeyboardButton("quit", callback_data="/quit"),
]]
keyboard_reply = InlineKeyboardMarkup(reply_keys)

dots_keys = [[
    InlineKeyboardButton("🔴"), InlineKeyboardButton("🟠"), InlineKeyboardButton("🟡"),
    InlineKeyboardButton("🟢"), InlineKeyboardButton("🔵"), InlineKeyboardButton("⚪"), 
]]
keyboard_dots = ReplyKeyboardMarkup(keyboard=dots_keys,
                                    resize_keyboard=True,
                                    one_time_keyboard=True)