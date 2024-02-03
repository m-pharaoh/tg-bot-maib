import constants
import ssl
import certifi
from aiohttp import ClientSession, TCPConnector


HF_TOKEN = constants.HF_TOKEN
API_URL = "https://api-inference.huggingface.co/models/meta-llama/Llama-2-7b-chat-hf"
headers = {"Authorization": f"Bearer {HF_TOKEN}"} 
ssl_context = ssl.create_default_context(cafile=certifi.where())
connector = TCPConnector(ssl=ssl_context)

async def email_action_agent(history: str):
    email_prompt_template = f"""<s>[INST] <<SYS>>
                                    You are an email assistant who's job it is to help a Human out with basic email tasks such as: summarizing/drafting/reading/sending emails.
                                    <<SYS>>

                                    {history}"""
    
    async with ClientSession(connector=connector) as session:
        output = await session.post(url=API_URL, headers=headers, json={
            "inputs": email_prompt_template,
            "parameters": {"temperature": 0.01, "top_p": 0.8, "max_new_tokens": 2000}
        })

        output_json = await output.json()
        return output_json[0]["generated_text"]