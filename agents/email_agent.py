import constants
import ssl
import certifi
from huggingface_hub import AsyncInferenceClient
import json
# from aiohttp import ClientSession, TCPConnector

HF_TOKEN = constants.HF_TOKEN
# API_URL = "https://api-inference.huggingface.co/models/meta-llama/Llama-2-7b-chat-hf"
# headers = {"Authorization": f"Bearer {HF_TOKEN}"} 
# ssl_context = ssl.create_default_context(cafile=certifi.where())
# connector = TCPConnector(ssl=ssl_context)

client = AsyncInferenceClient(model="https://api-inference.huggingface.co/models/meta-llama/Llama-2-7b-chat-hf", token=HF_TOKEN)

async def email_action_agent(history: str):
    email_prompt_template = f"""<s>[INST] <<SYS>>
                                    You are an email assistant who's job it is to help a Human out with basic email tasks such as: summarizing/drafting/reading/sending emails.
                                    <<SYS>>

                                    {history}"""
    
    output = await client.post(json={
        "inputs": email_prompt_template,
        "parameters": {"temperature": 0.01, "top_p": 0.8, "max_new_tokens": 2000}
    })

    # Convert bytes to string and decode
    reply_str = output.decode('utf-8')

    # Use json.loads to parse the JSON directly
    parsed_data = json.loads(reply_str)

    # Extract the generated_text from the parsed data
    generated_text = parsed_data[0]['generated_text']

    # Now, parse the inner JSON in generated_text
    inner_data = json.loads(generated_text)

    # Extract the email from the inner data
    email = inner_data[0]['generated_text']

    print(email)
    
    return email
    # async with ClientSession(connector=connector) as session:
        # output = await aiohttp.post(url=API_URL, headers=headers, json={
        #     "inputs": email_prompt_template,
        #     "parameters": {"temperature": 0.01, "top_p": 0.8, "max_new_tokens": 2000}
        # })

        # output_json = await output.json()
        # return output_json[0]["generated_text"]