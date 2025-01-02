#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""
First, a few callback functions are defined. Then, those functions are passed to
the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Example of a bot-user conversation using ConversationHandler.
Send /start to initiate the conversation.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)

from keyboard import keyboard_reply
from game import Game

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

PLAYING, PHOTO, LOCATION, BIO = range(4)

active_games = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the bot"""

    msg = "Welcome to Mastermind! Send /play to start, or check out available commands using /help."
    await update.message.reply_text(msg, reply_markup=keyboard_reply)


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the game."""

    user_id = update.message.from_user.id  # Use user ID as a key for tracking
    active_games[user_id] = Game()  # Create a new game instance for the user

    msg = "The game has started! Enter your guess using 🔴🟠🟡🟢🔵⚪️:"
    if update.callback_query:
        await update.callback_query.message.reply_text(msg)
    elif update.message:
        await update.message.reply_text(msg)

    return PLAYING


async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes user's guess"""

    user_id = update.message.from_user.id
    game = active_games.get(user_id)

    if not game:
        await update.message.reply_text("No active game found. Type /play to start a game.")
        return

    user, user_guess = update.message.from_user, update.message.text
    logger.info("Guess from %s: %s", user.first_name, user_guess)

    clue = game.add_guess(user_guess)
    logger.info(f"Clue: {clue}, {game.guesses} guesses made so far")

    if clue == -1:
        await update.message.reply_text("Invalid pattern - try again.")
        return PLAYING   
    
    # player wins
    elif clue == "⬜️⬜️⬜️⬜️":
        await update.message.reply_text("DING DING DING!! YOU WIN! :D")
        return ConversationHandler.END
    
    # did user run out of guesses?
    elif len(game.guesses) == game.max_guesses:
        await update.message.reply_text("😨 ... The pattern was ", game.code)
        return ConversationHandler.END
    
    # game continues
    else:
        await update.message.reply_text(game.display_board)
        return PLAYING


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Bye! I hope we can talk again some day.", reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""

    msg = """Available Commands: 
    /start - start the bot
    /rules - how to play
    /play - start a new game
    /help - see this list again
    /end - end the game"""

    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=keyboard_reply)
    elif update.message:
        await update.message.reply_text(msg, reply_markup=keyboard_reply)


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays game rules"""

    msg = """After starting a game, you will have 8 tries to guess the secret
    pattern, which is a 4-dot combination of the following: 🔴🟠🟡🟢🔵⚪️
    The bot will respond with a new 4-square sequence: ⬜️ means you have a guess
    that is the correct color in the correct spot, while 🟥 means you have a 
    correct color in the incorrect spot.
    Good luck!"""

    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=keyboard_reply)
    elif update.message:
        await update.message.reply_text(msg, reply_markup=keyboard_reply)


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ends the game/bot interaction"""

    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)

    msg = "bye bye!"
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
    elif update.message:
        await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END



def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token("7980110956:AAG_TX3jXJTwFXs1PAzGzOnebEvrQTWA-vk").build()

    # Adding these for user to manually type in instead of clicking button
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("rules", rules))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("end", end))

    # Add conversation handler with the states GENDER, PHOTO, LOCATION and BIO
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("play", play)],
        states={
            PLAYING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()