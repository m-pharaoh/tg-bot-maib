# from langchain.prompts import PromptTemplate
# from langchain.llms.ollama import Ollama


# llm = Ollama(
#     model="llama2:7b-chat", temperature=0.01, top_p=0.8
# )

def email_action_agent(history: str):
    email_prompt_template = f"""<s>[INST] <<SYS>>
                                    You are an email assistant who's job it is to help a Human out with basic email tasks such as: summarizing/drafting/reading/sending emails.
                                    <<SYS>>

                                    {history}"""


    # return llm(email_prompt_template) 
    return "Subject hi there\n\n what's up"