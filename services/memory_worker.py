import threading

from services.memory_service import process_chat_memory


# Extraction re-reads the last 20 messages of a chat, so firing one per message
# means the same work runs concurrently several times over. Keep at most one
# in-flight run per chat and let the next message pick up the rest.
_in_flight = set()
_lock = threading.Lock()


def start_memory_worker(
    user_email: str,
    chat_id: int
):
    """
    Run memory extraction
    in background.
    """

    with _lock:
        if chat_id in _in_flight:
            return
        _in_flight.add(chat_id)

    def _run():
        try:
            process_chat_memory(user_email, chat_id)
        finally:
            with _lock:
                _in_flight.discard(chat_id)

    thread = threading.Thread(
        target=_run,
        daemon=True
    )

    thread.start()
