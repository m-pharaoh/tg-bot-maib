import os
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.environ["TOKEN"] # TG bot token
CIPHER_KEY = os.environ["CIPHER_KEY"] 
AUTH_URL = os.environ["AUTH_URL"] # Gmail auth url
