from datetime import datetime

from memory.long_term import save_memory


def store_interaction(
    user_message: str,
    assistant_response: str
):

    memory_text = f"""
    User: {user_message}

    Assistant: {assistant_response}

    Time: {datetime.now()}
    """

    save_memory(memory_text)