import constants
from huggingface_hub import AsyncInferenceClient

HF_TOKEN = constants.HF_TOKEN
client = AsyncInferenceClient(model="https://api-inference.huggingface.co/models/meta-llama/Llama-2-7b-chat-hf", token=HF_TOKEN, timeout=60*5)

async def email_action_agent(history: str):
    email_prompt_template = f"""<s>[INST] <<SYS>>
                                    You are an email assistant who's job it is to help a Human out with basic email tasks such as: summarizing/drafting/reading/sending emails.
                                    <<SYS>>

                                    {history}"""
    
    try:
        output = await client.text_generation(
            prompt=email_prompt_template,
            temperature=0.01,
            top_p=0.8,
            max_new_tokens=2000
        )

        return output
    except:
        return None