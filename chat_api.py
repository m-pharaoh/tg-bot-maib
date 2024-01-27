from contextlib import asynccontextmanager
from http import HTTPStatus
from telegram import Update
from telegram.ext import Application, CommandHandler
from telegram.ext._contexttypes import ContextTypes
from fastapi import FastAPI, Request, Response
from cryptography.fernet import Fernet

import constants


# WEBHOOK SETUP
#######################################################
ptb = (
    Application.builder()
    .updater(None)
    .token(constants.TOKEN) 
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    # await ptb.bot.setWebhook(url=constants.WEB_URL) 
    async with ptb:
        await ptb.start()
        yield
        await ptb.stop()

# Initialize FastAPI app (similar to Flask)
app = FastAPI(lifespan=lifespan)

@app.post("/")
async def process_update(request: Request):
    req = await request.json()
    update = Update.de_json(req, ptb.bot)
    await ptb.process_update(update)
    return Response(status_code=HTTPStatus.OK)
#######################################################

# CONSTANTS
#######################################################
secret_key = bytes.fromhex(constants.CIPHER_KEY) # cipher key is in hex format
cipher_suite = Fernet(secret_key)
#######################################################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.message.from_user.id

    # print(update.effective_chat.id)
    if context.user_data.get(user_id):
        await update.message.reply_html(
        f"Already here"
    )
    else:
        context.user_data[user_id] = {} # init a user
        await update.message.reply_html(
        f"Initialized"
    )

ptb.add_handler(CommandHandler("start", start))
