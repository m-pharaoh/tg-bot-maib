from contextlib import asynccontextmanager
from http import HTTPStatus
from telegram import Update
from telegram.ext import Application, CommandHandler
from telegram.ext._contexttypes import ContextTypes
from fastapi import FastAPI, Request, Response
import constants


# Initialize python telegram bot
ptb = (
    Application.builder()
    .token(constants.TOKEN) 
    .build()
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    await ptb.stop()
    await ptb.bot.setWebhook(url=constants.WEB_URL) 
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

# Example handler
async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text("starting...")

ptb.add_handler(CommandHandler("start", start))
