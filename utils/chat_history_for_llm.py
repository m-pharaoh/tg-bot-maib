def set_chat_history_for_llm(chat_history: list) -> str:
    formatted_chat_history = ""
    i = 0
    for message_pair in chat_history:
        # user message
        user_msg = message_pair[0]        
        if i == 0:
            formatted_chat_history += f"{user_msg} [/INST] \n" # first human message
        else:
            formatted_chat_history += f"[INST] {user_msg} [/INST] \n"
        
        i += 1

        # bot message
        if len(message_pair) == 2:
            bot_msg = message_pair[1]
            formatted_chat_history += f" {bot_msg} \n"
    
    return formatted_chat_history
    