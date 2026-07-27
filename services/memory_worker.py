import threading

from services.memory_service import process_chat_memory


def start_memory_worker(
    user_email: str,
    chat_id: int
):
    """
    Run memory extraction
    in background.
    """

    thread = threading.Thread(
        target=process_chat_memory,
        args=(
            user_email,
            chat_id
        ),
        daemon=True
    )

    thread.start()