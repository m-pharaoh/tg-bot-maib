import os
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.environ["TOKEN"] # TG bot token
SECRET_TOKEN = os.environ["SECRET_TOKEN"] # secret token to be sent with all requests
WEB_URL = os.environ["WEB_URL"]
# CIPHER_KEY = os.environ["CIPHER_KEY"] 
# AUTH_URL = os.environ["AUTH_URL"] # Gmail auth url
