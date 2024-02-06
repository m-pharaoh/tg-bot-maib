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
from utils.general import find_subject_and_content

import constants

# DB
from motor.motor_asyncio import AsyncIOMotorClient


# WEBHOOK SETUP
#######################################################
ptb = (
    Application.builder()
    .updater(None)
    .token(constants.TOKEN) 
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


# DB SETUP
#######################################################
CONNECTION_STRING = constants.MONGO_URI

# Create an async MongoDB client
client = AsyncIOMotorClient(CONNECTION_STRING)

# Access your MongoDB Atlas database and collection
db = client["MAI"]["user_data_mai"]


# CONSTANTS
#######################################################
secret_key = bytes.fromhex(constants.CIPHER_KEY) # cipher key is in hex format
cipher_suite = Fernet(secret_key)
#######################################################



# START FLOW
#######################################################
async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.message.from_user.id

    # print(update.effective_chat.id)
    # context._chat_id -- might need to add back
    # context.user_data[user_id]["verified"] = False # check if wallet has been verified yet

    user = await db.find_one({"_id": user_id})
    encrypted_username = ""
    if user:
        encrypted_username = user["encrypted_username"]
        if user["flow"] != 0:
            await db.find_one_and_update({"_id": user_id}, {"$set": {"flow": 0}})
    else:

        # create encrypted username
        encrypted_username = cipher_suite.encrypt(str(user_id).encode())
        encrypted_username = base64.urlsafe_b64encode(encrypted_username).decode()


        doc = {
            "_id": user_id,
            "encrypted_username": encrypted_username,
            "flow": 0 # keeps track of the convo flow
        }
        await db.insert_one(doc)


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
        i) we read the wallet from the DATABASE
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


# flow == 0
async def verify_wallet(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """verify the USER_WALLET"""
    user_id = update.message.from_user.id

    user_wallet = update.message.text # user wallet

    doc = await db.find_one({"_id": user_id})
    encrypted_username = doc["encrypted_username"]

    verified_wallet = verify_user_wallet(user_wallet, encrypted_username) #NOTE: *await* may be needed here


    if verified_wallet:
        # Successful validation
        await db.find_one_and_update({"_id": user_id}, {"$set": {"bot_configured": False, "wallet": user_wallet, "flow": 1}})

        await update.message.reply_text(f"SUCCESS! Welcome to your personalized META AI BOTS. To get started with configuring your bots, input one of the following commands:\n\n/start_email_bot")
    else:
        # Prompt the user again for valid input
        await update.message.reply_text("Wallet address does not match with your unique access code. Please provide me with your wallet address which matches the access code, or re-verify:")


#######################################################




# MESSENGER COMMANDS
#######################################################
async def orchestrator(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Orchestrate based on flow state"""
    user_id = update.message.from_user.id
    doc: dict = await db.find_one({"_id": user_id})

    if not doc:
        await update.message.reply_text("Welcome to Meta AI Bots 🤖. Please begin by running:\n\n/start")
        return
    
    flow = doc["flow"]

    if flow == 0:
        await verify_wallet(update, _)
    elif flow == 1:
        await update.message.reply_text("To get started with configuring your bots, input one of the following commands:\n\n/start_email_bot")
    elif flow == 10:
        await gmail_client_secret(update, _)
    elif flow == 11:
        await gmail_client_tokens(update, _)
    elif flow == 12:
        await gmail_client_attempt_auth(update, _)
    elif flow == 13: 
        await bot_messenger(update, _) # allowed to use the bot


async def bot_messenger(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    doc: dict = await db.find_one({"_id": user_id})

    if not doc.get("bot_configured"): # checks whether user has configured a bot yet
        await update.message.reply_text("You have not configured any bots yet. Please configure a bot by running one of the following commands:\n\n/start_email_bot")
        return
    
    # make sure user ALWAYS has enough tokens to access the bot
    user_wallet = doc["wallet"]
    if not verify_access_for_email_bot(user_wallet):
        await update.message.reply_text("You do not have enough MAIB tokens to access the email bot. You need at least 2,500 MAIB tokens for access.")
        return


    user_reply = update.message.text

    chat_history = []
    if doc.get("chat_history"): # chat history already set
        chat_history = doc["chat_history"]

    # [ [user_reply, bot_reply], [user_reply, bot_reply], ... ]

    processing_msg = await update.message.reply_text("Processing 🤖")

    # set new chat history
    MAX_CHAT_HISTORY = 10 # max amount of human/bot messages

    chat_history.append([user_reply]) # may be the 10th msg


    # llm getting ready to reply
    history = set_chat_history_for_llm(chat_history)
    llm_reply = await email_action_agent(history=history)

    chat_history[-1].append(llm_reply) # append the bot reply

    # Delete 'Processing' message
    await ptb.bot.delete_message(chat_id=update.message.chat_id, message_id=processing_msg.message_id)

    # set new chat history
    if len(chat_history) == MAX_CHAT_HISTORY:
        update_operation = {
            "$push": {
                "chat_history": chat_history[-1]  # Add a new item to the end
            },
            "$set": {
                "llm_reply": llm_reply
            }
        }
        await db.find_one_and_update({"_id": user_id}, update_operation)

        # now, remove the first element
        update_operation = {
            "$pop": {
                "chat_history": -1  # Remove the first item
            },
        }
        await db.find_one_and_update({"_id": user_id}, update_operation)
    else:
        # only write the latest chat history update - never the whole thing
        # the latest llm reply will typically be used for sending emails etc.
        await db.find_one_and_update({"_id": user_id}, {"$push": {"chat_history": chat_history[-1]}, "$set": {"llm_reply": llm_reply}})

    # send the new llm reply to the user
    await update.message.reply_text(llm_reply)



#######################################################




# EMAIL BOT FLOW/COMMANDS
#######################################################
async def init_email_bot(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id
    
    # NOTE: below likely not needed since we do wallet verification later on for messages
    # if not context.user_data[user_id]["verified"]:
    #     await update.message.reply_text("You have not verified your wallet. Please run the /start command to verify.")
    #     return

    await db.find_one_and_update({"_id": user_id}, {"$set": {"flow": 10}})

    await update.message.reply_text("Welcome to your personal Email AI Agent. Please provide your CLIENT ID: ")


# flow == 10
async def gmail_client_secret(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    client_id = update.message.text # client id

    await db.find_one_and_update({"_id": user_id}, {"$set": {"email.client_id": client_id, "flow": 11}})

    await update.message.reply_text("Please provide your CLIENT SECRET: ")


# flow == 11
async def gmail_client_tokens(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    client_secret = update.message.text # client secret

    doc = await db.find_one_and_update({"_id": user_id}, {"$set": {"email.client_secret": client_secret, "flow": 12}})

    client_id = doc["email"]["client_id"]

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
    response = requests.get(f"{constants.AUTH_URL}/authorize", params=params)

    auth_url = response.text

    await update.message.reply_html(f"Please follow this link to authenticate: <a href='{auth_url}'>LINK</a>")    
    await update.message.reply_text(f"If you have successfully authenticated, please provide the long piece of text given in your browser: ")


# flow == 12
async def gmail_client_attempt_auth(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
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

    
    doc = await db.find_one({"_id": user_id})
    client_id = doc["email"]["client_id"]
    client_secret = doc["email"]["client_secret"]


    # attempt an auth
    auth = create_authenticated_service(access_token, refresh_token, client_id, client_secret)

    if auth:
        await db.find_one_and_update({"_id": user_id}, {"$set": {"email.access_token": access_token, "email.refresh_token": refresh_token, "bot_configured": True, "flow": 13}}) # done
        await update.message.reply_text("SUCCESSFULLY LOGGED IN TO GMAIL!\n\nYou are now able to read/draft/send emails from your GMAIL with the power of AI 🚀\n\nTry typing the following 😉\n\nDraft me an email about how awesome Bitcoin is🤑")
    else:
        await update.message.reply_text("Unable to authenticate to Gmail. Please ensure you provided the long piece of text given in your browser at the end of successfully authenticating!")



# flow == 13, no more flow updates
async def send_gmail_email(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    doc: dict = await db.find_one({"_id": user_id})

    if not doc.get("bot_configured"): # checks whether user has configured a bot yet
        await update.message.reply_text("You have not configured any bots yet. Please configure a bot by running one of the following commands:\n\n/start_email_bot")
        return

    client_id = doc["email"]["client_id"]
    client_secret = doc["email"]["client_secret"]
    access_token = doc["email"]["access_token"]
    refresh_token = doc["email"]["refresh_token"]


    user_input = update.message.text.split(" ") # /send address1 address2 ....

    if len(user_input) < 2:
        await update.message.reply_text("use this format to send an email\n \\send_email email_address_to_send_to_1 email_address_to_send_to_2 ...")
        return 
    
    llm_reply = find_subject_and_content(doc["llm_reply"]) # returns [first_line_of string, rest_of_string]

    # construct and send email
    service = create_authenticated_service(access_token, refresh_token, client_id, client_secret)
    if not service:
        await update.message.reply_text("There were some issues connecting to your gmail inbox, please re-run /start_email_bot")
        return 
    to = user_input[1:]
    subject = llm_reply[0] # first line with the subject
    body = llm_reply[1] # the rest of the email
    

    send = send_email(service, to, subject, body)
    await update.message.reply_text(send)


# flow == 13, no more flow updates
async def draft_gmail_email(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    doc: dict = await db.find_one({"_id": user_id})

    if not doc.get("bot_configured"): # checks whether user has configured a bot yet
        await update.message.reply_text("You have not configured any bots yet. Please configure a bot by running one of the following commands:\n\n/start_email_bot")
        return

    client_id = doc["email"]["client_id"]
    client_secret = doc["email"]["client_secret"]
    access_token = doc["email"]["access_token"]
    refresh_token = doc["email"]["refresh_token"]


    user_input = update.message.text.split(" ") # /draft address1 address2 ....

    if len(user_input) < 2:
        await update.message.reply_text("use this format to draft an email\n \\draft_email email_address_to_draft_to_1 email_address_to_draft_to_2 ...")
        return 
    
    llm_reply = find_subject_and_content(doc["llm_reply"]) # returns [first_line_of string, rest_of_string]

    # construct and draft email
    service = create_authenticated_service(access_token, refresh_token, client_id, client_secret)
    if not service:
        await update.message.reply_text("There were some issues connecting to your gmail inbox, please re-run /start_email_bot")
        return 
    to = user_input[1:]
    subject = llm_reply[0] # first line with the subject
    body = llm_reply[1] # the rest of the email
    

    draft = draft_email(service, to, subject, body)
    await update.message.reply_text(f"{draft}")


# flow == 13, no more flow updates
async def read_gmail_email(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """LLM to reply back to user"""
    user_id = update.message.from_user.id

    doc: dict = await db.find_one({"_id": user_id})

    if not doc.get("bot_configured"): # checks whether user has configured a bot yet
        await update.message.reply_text("You have not configured any bots yet. Please configure a bot by running one of the following commands:\n\n/start_email_bot")
        return

    client_id = doc["email"]["client_id"]
    client_secret = doc["email"]["client_secret"]
    access_token = doc["email"]["access_token"]
    refresh_token = doc["email"]["refresh_token"]
    chat_history = doc["chat_history"]


    user_input = update.message.text.split(" ") # /read address1

    if len(user_input) != 2:
        await update.message.reply_text("use this format to read an email\n \\read_email email_address_to_read_from")
        return 
    

    # read email
    service = create_authenticated_service(access_token, refresh_token, client_id, client_secret)
    if not service:
        await update.message.reply_text("There were some issues connecting to your gmail inbox, please re-run /start_email_bot")
        return 

    read_email = read_email_from_sender(service, user_input[1])

    address = user_input[1]
    new_history = [f"Please read the latest email from {address}", f"For sure! The latest email from {address} is:\n\n{read_email}"]

    MAX_CHAT_HISTORY = 10

    # set new chat history
    if len(chat_history) == MAX_CHAT_HISTORY - 1:
        update_operation = {
            "$push": {
                "chat_history": new_history  # Add a new item to the end
            }
        }
        await db.find_one_and_update({"_id": user_id}, update_operation)

        # now, remove the first element
        update_operation = {
            "$pop": {
                "chat_history": -1  # Remove the first item
            },
        }
        await db.find_one_and_update({"_id": user_id}, update_operation)
    else:
        await db.find_one_and_update({"_id": user_id}, {"$push": {"chat_history": new_history}})

    await update.message.reply_text(read_email) # only return the read email
#######################################################


# Helper commands  
#######################################################
async def help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_string = f"""
    List of commands, and what they do 😉

    Initialization Commands 🚀:
    /start - initializes the process to verify your wallet with your unique access code
    /start_email_bot - intitializes the process to link your GMAIL with the Meta AI Bot.

    
    Email AI Bot Commands ✉️:
    /send_email - Sends the last reply by the AI Bot to the provided email addresses. You can view the 'last reply by the AI bot' by running /last_reply.
    usage: /send_email email_address_1 email_address_2 ...

    /draft_email - Drafts the last reply by the AI Bot to the provided email addresses. You can view the 'last reply by the AI bot' by running /last_reply.
    usage: /draft_email email_address_1 email_address_2 ...

    /read_email - Reads the latest email from the email address provided.
    usage: /read_email email_address

    
    Extra Commands 👀:
    /last_reply - The latest reply by the AI bot. This reply is what will be used to send/draft an email.
    /help - You're already here :) 
    """
    await update.message.reply_text(help_string)

async def last_reply(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id

    doc: dict = await db.find_one({"_id": user_id})

    if not doc.get("llm_reply"): 
        await update.message.reply_text("No replies provided by the AI bot yet.")
        return
    
    llm_reply = doc["llm_reply"]
    await update.message.reply_text(f"Latest AI Bot reply:\n\n{llm_reply}")



# general commands
ptb.add_handler(CommandHandler("start", start))
ptb.add_handler(CommandHandler("help", help))
ptb.add_handler(CommandHandler("last_reply", last_reply))


# email commands
ptb.add_handler(CommandHandler("start_email_bot", init_email_bot))
ptb.add_handler(CommandHandler("send_email", send_gmail_email))
ptb.add_handler(CommandHandler("draft_email", draft_gmail_email))
ptb.add_handler(CommandHandler("read_email", read_gmail_email))

# on non command i.e message 
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, orchestrator))
