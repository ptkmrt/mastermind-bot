"""
Mastermind description.
Note: this local file may be out of date with the one running on pythonanywhere

TODO new feature ideas ...
- race mode (2 users): each sets a code that the other has to guess. 
  whoever guesses the other's first wins.
    - command: /race
- user stats across a channel/group (player: # wins, avg tries per win, etc.)
    - stored in group states ?
    - would need to keep this data and only clear upon certain command, e.g. /clearstats
    - command to view: /stats --> print out
"""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters, 
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes)

from keyboard import keyboard_reply
from game import Game, CODE_LEN, re

from functools import wraps
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env file
BOT_TOKEN = os.getenv("BOT_TOKEN")

users_str = os.getenv("USERS")
USERS = [int(id.strip()) for id in users_str.split(',')]

GUESS_LIMIT, INVALID, CORRECT = -2, -1, 0

# Define pattern
dots = ["🟣", "🔴", "🟠", "🟡", "🟢", "🔵"]
REGEX = re.compile(f"^({'|'.join(re.escape(d) for d in dots)}){{{CODE_LEN}}}$")

active_games = {}
group_states = {}

### NEW : define ai vars ###
client = genai.Client()
CHAT = client.aio.chats.create(model='gemini-2.0-flash-thinking-exp')

def restricted(func):
    """To restrict who can use this bot"""
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in USERS:
            print(f"Unauthorized access denied for {user_id}.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the bot"""
    chat_id = update.message.chat_id
    context.user_data["groupchat_id"] = chat_id

    group_states[chat_id] = {"game_active"     : False,
                             "multiplayer"     : False,
                             "setter"          : None,
                             "setter_choosing" : False,
                             "setter_ready"    : False,
                             }

    msg = "Welcome to Mastermind! Send /play to start, or check out available commands using /help."
    await update.message.reply_text(msg, reply_markup=keyboard_reply)


@restricted
async def choose_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompts user for play method (solo against bot, or multiplayer)"""
    chat_id = update.message.chat_id
    if chat_id not in group_states:
        await update.message.reply_text("Start the bot first with /start.")
        return

    msg = "Send /bot to play against the bot, or /multiplayer to play with a group."
    await update.message.reply_text(msg)


@restricted
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts a new game (solo against bot, or at the end of multiplayer path)"""
    chat_id = update.message.chat_id
    if chat_id not in group_states:
        await update.message.reply_text("Start the bot first with /start.")
        return

    group_states[chat_id]["game_active"] = True
    group_states[chat_id]["multiplayer"] = False
    group_states[chat_id]["setter_ready"] = False
    group_states[chat_id]["setter_choosing"] = False
    
    chat_id = update.message.chat_id
    if chat_id not in active_games:
        logger.info("no active games for this chat - starting new one")
        active_games[chat_id] = Game()

    msg = "The game has started! Enter your guess using 🔴🟠🟡🟢🔵🟣:"
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=keyboard_reply)
    elif update.message:
        await update.message.reply_text(msg)


async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes user's guess"""
    chat_id = update.message.chat_id
    game = active_games.get(chat_id)

    # or if not group_states[chat_id]["game_active"]
    if not game:
        await update.message.reply_text("No active game found. Type /play to start a game.")
        return
    if group_states[chat_id]["multiplayer"] and not group_states[chat_id]["setter_ready"]:
        await update.message.reply_text("The setter hasn't chosen a code yet!")
        return

    user, user_guess = update.message.from_user, update.message.text
    clue = game.add_guess(user_guess)

    # logger.info("%s user's id: %d", user.first_name, update.message.from_user.id)
    logger.info("Guess from %s: %s", user.first_name, user_guess)
    logger.info(f"Clue: {clue}, {len(game.guesses)} guesses made so far")

    if clue == INVALID:
        await update.message.reply_text("Invalid pattern - try again.", 
                                        reply_markup=keyboard_reply)

    # did user run out of guesses?
    elif clue == GUESS_LIMIT:
        await update.message.reply_text(f"😨 ... The pattern was {game.code}. Better luck next time!")
        await update.message.reply_text("Send /play to try again, or /end to exit.", 
                                        reply_markup=keyboard_reply)
        del active_games[chat_id]
        return ConversationHandler.END
    
    # player wins
    elif clue == CORRECT:
        await update.message.reply_text("That's correct! 🥳")
        await update.message.reply_text("Send /play to play again, or /end to exit.", 
                                        reply_markup=keyboard_reply)
        del active_games[chat_id]
        return ConversationHandler.END
    
    # game continues
    else:
        await update.message.reply_text(game.display_board())
        await update.message.reply_text("Enter your next guess (🔴🟠🟡🟢🔵🟣):", 
                                        reply_markup=keyboard_reply)


@restricted
async def multiplayer(update: Update, context: CallbackContext):
    """Begins logic for handling multiplayer game"""
    chat_id = update.message.chat_id
    if chat_id not in group_states:
        await update.message.reply_text("Start the bot first with /start.")
        return

    chat_id = update.message.chat_id
    group_states[chat_id]["multiplayer"] = True

    logger.info("multiplayer game for chat %d", chat_id)

    await update.message.reply_text("Choose your roles! The person who's \
                                     setting should send /setter")


@restricted
async def handle_setter(update: Update, context: CallbackContext):
    """Responds to user who sent /setter to set code in a multiplayer game."""
    chat_id = update.message.chat_id
    if chat_id not in group_states:
        await update.message.reply_text("Start the bot first with /start.")
        return

    user_id = update.message.from_user.id
    group_states[chat_id]["setter"] = user_id

    logger.info("User %s choosing code for chat %d", 
                update.message.from_user.first_name,
                chat_id)

    try:
        group_states[chat_id]["setter_choosing"] = True
        msg = ("Set the secret pattern! It should be 4 dots using any of the "
                "following, repeats allowed: 🔴🟠🟡🟢🔵🟣")
        await context.bot.send_message(chat_id=user_id, text=msg)
    except:
        await update.message.reply_text("Please start a private chat first.")


async def set_pattern(update: Update, context: CallbackContext):
    """For multiplayer; sets custom pattern from the setter"""

    # 1) check if this user is designated setter
    user_id = get_user(update).id
    chat_id = context.user_data["groupchat_id"]

    if group_states[chat_id]["setter"] != user_id:
        await update.message.reply_text("You're not the setter for this game!")
        return

    # 2) validate pattern
    custom_pattern = update.message.text
    if not await is_valid_pattern(custom_pattern):
        await update.message.reply_text("Invalid pattern - try another one.")
    
    # 3) create game associated with groupchat id
    active_games[chat_id] = Game(code=custom_pattern)
    
    group_states[chat_id]["game_active"] = True
    group_states[chat_id]["setter_choosing"] = False
    group_states[chat_id]["setter_ready"] = True

    await update.message.reply_text("Pattern set!")
    await context.bot.send_message(
        chat_id=chat_id,
        text="The secret pattern has been set! Enter your guess (🔴🟠🟡🟢🔵🟣):",
    )


async def is_valid_pattern(pattern):
    """Helper function for validating custom user-set pattern"""
    dots = ["🟣", "🔴", "🟠", "🟡", "🟢", "🔵"]
    regex = f"^({'|'.join(re.escape(d) for d in dots)}){{{CODE_LEN}}}$"

    return bool(re.match(regex, pattern))


@restricted
async def help(update: Update, context: CallbackContext):
    """Help command"""
    msg = """Here are the available commands: 
    /start  - start the bot
    /rules  - how to play
    /play   - start a new game
    /quit   - quit an active game
    /chat   - just to chat. no game :)
    /end    - stop the bot
    /help   - see this list again"""

    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=keyboard_reply)
    elif update.message:
        await update.message.reply_text(msg, reply_markup=keyboard_reply)


@restricted
async def rules(update: Update, context: CallbackContext):
    """Displays game rules"""
    msg = ("After starting a game, you will have 8 tries to\n guess the secret"
    " pattern, which is a 4-dot combination of the colors: 🔴🟠🟡🟢🔵🟣"
    "\n\nThe bot will respond with a new 4-square sequence: ◼ means you have a dot"
    " in the correct spot, while ◻ means you have a dot in the incorrect spot."
    "\n\nGood luck! 😎")

    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=keyboard_reply)
    elif update.message:
        await update.message.reply_text(msg, reply_markup=keyboard_reply)


async def quit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ends active game"""
    chat_id = update.message.chat_id
    
    game = active_games.get(chat_id)   
    if chat_id in active_games:
        logger.info("Deleting active game")
        del active_games[chat_id]  # remove the game instance
    else:
        await update.message.reply_text("No active game found. Type /play to start a game.")
        return
    
    msg = f"🙄 ... The pattern was {game.code} \n\n Send /play to try again, or /end to exit."
    await update.message.reply_text(msg)
    return ConversationHandler.END


@restricted
async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ends the game/bot interaction"""
    if update.callback_query:
        logger.info("User %s ending chat", update.callback_query.from_user.first_name)
    elif update.message:
        logger.info("User %s ending chat", update.message.from_user.first_name)  

    chat_id = update.message.chat_id
    msg = ("You have to /quit the active game first to end!" if chat_id in active_games 
           else "Bye bye for now! Send /start whenever you want to play again 🤗")
    
    if update.callback_query:
        await update.callback_query.message.reply_text(msg)
    elif update.message:
        await update.message.reply_text(msg)
    
    global game_start
    game_start = False

    context.chat_data.clear()
    group_states[chat_id].clear()
    del group_states[chat_id]

    return ConversationHandler.END


### NEW : CHATBOT FEATURE ###
@restricted
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Begins a chat with a GEMINI AI chatbot"""
    await update.message.reply_text("Let's chat! 🤗🤳 Send \"bye\" anytime you're finished.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    if user_input.lower() == "bye":
        await update.message.reply_text("Goodbye!")
    else:
        response = await CHAT.send_message(user_input)
        await update.message.reply_text(response.text)


async def unknown(update: Update, context: CallbackContext):
    """Handles invalid user input"""
    await update.message.reply_text("Unknown message or command.")


async def button(update, context):
    """Handles inline keyboard button selection"""
    query = update.callback_query
    await query.answer()
    command = query.data
    
    # Process the command
    if command == "/rules":
        await rules(update, context)
    elif command == "/help":
        await help(update, context)


def get_user(update):
    """Helper for returning user id"""
    if update.callback_query:
        return update.callback_query.from_user
    elif update.message:
        return update.message.from_user


async def handle_regex_match(update: Update, context: CallbackContext):
    """Handles pattern input"""
    chat_id = context.user_data["groupchat_id"]
    if chat_id not in group_states:
        await update.message.reply_text("Start the bot first with /start.")
        return
    
    logger.info("chat id: %d", update.message.chat_id)
    
    if group_states[chat_id]["setter_choosing"]:
        await set_pattern(update, context)
    elif group_states[chat_id]["multiplayer"] and not group_states[chat_id]["game_active"]:
        await handle_setter(update, context)
    else:
        await handle_guess(update, context)


class RegexFilter(filters.MessageFilter):
    """Custom regex filter class for valid patterns"""
    def filter(self, message):
        return REGEX.match(message.text)


def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("rules", rules))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("quit", quit))
    application.add_handler(CommandHandler("end", end))

    application.add_handler(CommandHandler("play", choose_play))
    application.add_handler(CommandHandler("bot", play))
    application.add_handler(CommandHandler("multiplayer", multiplayer))
    application.add_handler(CommandHandler("setter", handle_setter))

    application.add_handler(CommandHandler("chat", chat))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.add_handler(MessageHandler(RegexFilter(), handle_regex_match))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()