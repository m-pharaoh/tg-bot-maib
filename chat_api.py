from contextlib import asynccontextmanager
from http import HTTPStatus
from telegram import Update
import requests
import base64
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, ConversationHandler, filters, Updater
from telegram.ext._contexttypes import ContextTypes
from fastapi import FastAPI, Request, Response
from cryptography.fernet import Fernet

from agents.email_agent import email_action_agent
from utils.blockchain.verify_wallet import verify_user_wallet
from utils.blockchain.verify_email_bot_access import verify_access_for_email_bot
from utils.chat_history_for_llm import set_chat_history_for_llm
from utils.gmail.gmail_actions import create_authenticated_service, send_email, draft_email, read_email_from_sender

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
#######################################################




# CONSTANTS
#######################################################
secret_key = bytes.fromhex(constants.CIPHER_KEY) # cipher key is in hex format
cipher_suite = Fernet(secret_key)
#######################################################



# START FLOW
#######################################################
USER_WALLET = 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.message.from_user.id

    # print(update.effective_chat.id)
    
    context.user_data[user_id] = {} # init a user

    # context.user_data[user_id]["verified"] = False # check if wallet has been verified yet

    # create encrypted username
    encrypted_username = cipher_suite.encrypt(str(user_id).encode())
    encrypted_username = base64.urlsafe_b64encode(encrypted_username).decode()

    context.user_data[user_id]["encrypted_username"] = encrypted_username


    # context._chat_id -- might need to add back

    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! Welcome to your personalized META AI BOTS.\n\nBelow is your UNIQUE ACCESS CODE:"
    )


    """
    # the below only requires the smart contract, NOT the flask app.

    1. encrypt the username (access code)

    2. The user will connect to the verify website

    3. In the website, the user connects their wallet, gives the encrypted usernmae, and send a transaction
       to a smart contract which stores the following:

       wallet address -> encrypted_username

    4. Now, for wallet/token verification:
        i) we read the wallet from the CONTEXT (which the user provides) 
        ii) we then get the encrypted_username from the smart contract
        iii) VERIFICATION HERE: we then check if the encrypted_username matches that of current user; if not, fail wallet verification.
        iv) if the encrypted (not decrypted, since we already have encrypted) username mathces that of the user, then use balanceOf with given wallet address to check balance of $MAIB tokens.
    """

    await update.message.reply_text(
        f"{encrypted_username}"
    )

    await update.message.reply_text(
        "Please go to the link below, you will be asked for your unique access code\n\nhttp://localhost:3000/verify"
    )

    await update.message.reply_text(
        "After you have finished with the above link, please provide me with your wallet address (which you used on the above link to verify):"
    )

    
    return USER_WALLET


async def verify_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """verify the USER_WALLET"""
    user_id = update.message.from_user.id

    user_wallet = update.message.text # user wallet
    encrypted_username = context.user_data[user_id]["encrypted_username"]

    # verified_wallet = await verify_user_wallet(user_wallet, encrypted_username)
    verified_wallet = await verify_user_wallet(user_wallet, encrypted_username)


    if verified_wallet:
        # Successful validation
        context.user_data[user_id]["bot_configured"] = False # checks whether user has configured a bot yet. Init to False (not configured yet)
        context.user_data[user_id]["wallet"] = user_wallet
        await update.message.reply_text(f"SUCCESS! Welcome to your personalized META AI BOTS. To get started with configuring your bots, input one of the following commands:\n\n/start_email_bot")
        return ConversationHandler.END
    else:
        # Prompt the user again for valid input
        await update.message.reply_text("Wallet address does not match with your unique access code. Please provide me with your wallet address which matches the access code, or re-verify:")
        return USER_WALLET


#######################################################




# GENERAL COMMANDS
#######################################################

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help Me!")


async def bot_messenger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    if not context.user_data[user_id]["bot_configured"]: # checks whether user has configured a bot yet
        await update.message.reply_text("You have not configured any bots yet. Please configure a bot by running one of the following commands:\n\n/start_email_bot")
        return
    
    # make sure user ALWAYS has enough tokens to access the bot
    user_wallet = context.user_data[user_id]["wallet"]
    if not await verify_access_for_email_bot(user_wallet):
        await update.message.reply_text("You do not have enough $MAIB tokens to access the email bot. You need at least 2,500 $MAIB tokens for access.")
        return


    user_reply = update.message.text

    if not context.user_data[user_id].get("chat_history"): # chat history hasn't been set yet
        context.user_data[user_id]["chat_history"] = []

    # [ [user_reply, bot_reply], [user_reply, bot_reply], ... ]

    processing_msg = await update.message.reply_text("Processing 🤖")

    # set new chat history
    chat_history = context.user_data[user_id]["chat_history"]
    MAX_CHAT_HISTORY = 10 # max amount of human/bot messages

    if len(chat_history) == MAX_CHAT_HISTORY:
        del chat_history[0]

    chat_history.append([user_reply])



    # llm getting ready to reply
    history = set_chat_history_for_llm(chat_history)
    llm_reply = email_action_agent(history=history)

    chat_history[-1].append(llm_reply) # append the bot reply

    # Delete 'Processing' message
    await context.bot.delete_message(chat_id=update.message.chat_id, message_id=processing_msg.message_id)

    # set new chat history
    context.user_data[user_id]["chat_history"] = chat_history
    context.user_data[user_id]["llm_reply"] = llm_reply # the latest llm reply will typically be used for sending emails etc.


    # send the new llm reply to the user
    await update.message.reply_text(llm_reply)



#######################################################




# EMAIL BOT FLOW/COMMANDS
#######################################################
GMAIL_CLIENT_SECRET = 10
GMAIL_CLIENT_TOKENS = 11
GMAIL_CLIENT_ATTEMPT_AUTH = 12

async def init_email_agent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id
    
    # NOTE: below likely not needed since we do wallet verification later on for messages
    # if not context.user_data[user_id]["verified"]:
    #     await update.message.reply_text("You have not verified your wallet. Please run the /start command to verify.")
    #     return

    context.user_data[user_id]["email"] = {}

    await update.message.reply_text("Welcome to your personal Email AI Agent. Please provide your CLIENT ID: ")
    return GMAIL_CLIENT_SECRET


async def gmail_client_secret(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    user_input = update.message.text # client id

    context.user_data[user_id]["email"]["client_id"] = user_input


    await update.message.reply_text("Please provide your CLIENT SECRET: ")
    return GMAIL_CLIENT_TOKENS


async def gmail_client_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    user_input = update.message.text # client secret

    context.user_data[user_id]["email"]["client_secret"] = user_input

    client_id = context.user_data[user_id]["email"]["client_id"]
    client_secret = context.user_data[user_id]["email"]["client_secret"]




    # Combine client_id, and client_secret into a single string
    combined = f"{client_id}:{client_secret}"

    # Encrypt the combined string
    encrypted_credentials = cipher_suite.encrypt(combined.encode())

    # Encode the encrypted data into a URL-safe format
    url_safe_token = base64.urlsafe_b64encode(encrypted_credentials).decode()

    # Parameters to send in the GET request
    params = {
        "encoded_credentials": url_safe_token
    }

    # Make a GET request to the authorize endpoint with the specified parameters
    response = requests.get(f"{constants.AUTH_URL}/authorize", params=params, verify=False)


    auth_url = response.text


    # await update.message.reply_text(f"Please follow the below link to authenticate: \n{auth_url}")
    await update.message.reply_html(f"Please follow this link to authenticate: <a href='{auth_url}'>LINK</a>")    
    await update.message.reply_text(f"If you have successfully authenticated, please provide the long piece of text given in your browser: ")
    return GMAIL_CLIENT_ATTEMPT_AUTH


async def gmail_client_attempt_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    user_input = update.message.text # access_token:refresh_token encoded


    # Decode the URL-safe token back to bytes
    url_safe_token_bytes = base64.urlsafe_b64decode(user_input.encode())

    # Decrypt the token to get the encrypted combined string
    encrypted_combined = cipher_suite.decrypt(url_safe_token_bytes)

    # Decode the decrypted bytes back to a string
    decoded_combined = encrypted_combined.decode()

    # Extract access_token and refresh_token from the combined string
    access_token, refresh_token = decoded_combined.split(':')


    context.user_data[user_id]["email"]["access_token"] = access_token
    context.user_data[user_id]["email"]["refresh_token"] = refresh_token


    client_id = context.user_data[user_id]["email"]["client_id"]
    client_secret = context.user_data[user_id]["email"]["client_secret"]
    access_token = context.user_data[user_id]["email"]["access_token"]
    refresh_token = context.user_data[user_id]["email"]["refresh_token"]
   

    # attempt an auth
    auth = create_authenticated_service(access_token, refresh_token, client_id, client_secret)

    if auth:
        await update.message.reply_text("SUCCESSFULLY LOGGED IN TO GMAIL!\n\nYou are now able to read/draft/send emails from your GMAIL with the power of AI!\n\nTry typing the following 😉\n\nDraft me an email about how awesome Bitcoin is🤑")
        context.user_data[user_id]["bot_configured"] = True # a bot has been configured
        return ConversationHandler.END
    else:
        await update.message.reply_text("Unable to authenticate to Gmail. Please ensure you provided the long piece of text given in your browser at the end of successfully authenticating!")
        return GMAIL_CLIENT_ATTEMPT_AUTH




async def send_gmail_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    client_id = context.user_data[user_id]["email"]["client_id"]
    client_secret = context.user_data[user_id]["email"]["client_secret"]
    access_token = context.user_data[user_id]["email"]["access_token"]
    refresh_token = context.user_data[user_id]["email"]["refresh_token"]


    user_input = update.message.text.split(" ") # /send address1 address2 ....

    if len(user_input) < 2:
        await update.message.reply_text("use this format to send an email\n \\send_email email_address_to_send_to_1 email_address_to_send_to_2 ...")
        return 
    
    llm_reply = context.user_data[user_id]["llm_reply"].split('\n', 1) # returns [first_line_of string, rest_of_string]

    # construct and send email
    service = create_authenticated_service(access_token, refresh_token, client_id, client_secret)
    to = user_input[1:]
    subject = llm_reply[0] # first line with the subject
    body = llm_reply[1] # the rest of the email
    

    send = send_email(service, to, subject, body)
    await update.message.reply_text("Email sent successfully")


async def draft_gmail_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    client_id = context.user_data[user_id]["email"]["client_id"]
    client_secret = context.user_data[user_id]["email"]["client_secret"]
    access_token = context.user_data[user_id]["email"]["access_token"]
    refresh_token = context.user_data[user_id]["email"]["refresh_token"]


    user_input = update.message.text.split(" ") # /draft address1 address2 ....

    if len(user_input) < 2:
        await update.message.reply_text("use this format to draft an email\n \\draft_email email_address_to_draft_to_1 email_address_to_draft_to_2 ...")
        return 
    
    llm_reply = context.user_data[user_id]["llm_reply"].split('\n', 1) # returns [first_line_of string, rest_of_string]

    # construct and draft email
    service = create_authenticated_service(access_token, refresh_token, client_id, client_secret)
    to = user_input[1:]
    subject = llm_reply[0] # first line with the subject
    body = llm_reply[1] # the rest of the email
    

    draft = draft_email(service, to, subject, body)
    await update.message.reply_text("Email drafted successfully")


async def read_gmail_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    client_id = context.user_data[user_id]["email"]["client_id"]
    client_secret = context.user_data[user_id]["email"]["client_secret"]
    access_token = context.user_data[user_id]["email"]["access_token"]
    refresh_token = context.user_data[user_id]["email"]["refresh_token"]


    user_input = update.message.text.split(" ") # /read address1

    if len(user_input) > 2:
        await update.message.reply_text("use this format to read an email\n \\read_email email_address_to_read_from")
        return 
    

    # read email
    service = create_authenticated_service(access_token, refresh_token, client_id, client_secret)

    read_email = read_email_from_sender(service, user_input[1])

    await update.message.reply_text(read_email)



# CONVO FLOW SETUP
#######################################################

# /start convo flow
start_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        USER_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_wallet)]
    },
    fallbacks=[]
)

# /email convo flow
email_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start_email_bot", init_email_agent)],
    states={
        GMAIL_CLIENT_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, gmail_client_secret)],
        GMAIL_CLIENT_TOKENS: [MessageHandler(filters.TEXT & ~filters.COMMAND, gmail_client_tokens)],
        GMAIL_CLIENT_ATTEMPT_AUTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, gmail_client_attempt_auth)]
    },
    fallbacks=[]
)


# convo handlers
ptb.add_handler(start_conv_handler)
ptb.add_handler(email_conv_handler)

# general commands
ptb.add_handler(CommandHandler("start", start))
ptb.add_handler(CommandHandler("help", help_command))

# email commands
ptb.add_handler(CommandHandler("start_email_bot", init_email_agent))
ptb.add_handler(CommandHandler("send_email", send_gmail_email))
ptb.add_handler(CommandHandler("draft_email", draft_gmail_email))
ptb.add_handler(CommandHandler("read_email", read_gmail_email))

# on non command i.e message - echo the message on Telegram
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_messenger))
# for this guy^ remember to use user_data context to know which bot is being used (email, twitter etc.)