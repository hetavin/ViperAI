import os
import pymysql.cursors
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from config import _load_env

_load_env()
_executor = ThreadPoolExecutor(max_workers=4)


def _connect():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_DATABASE"],
        port=int(os.environ["DB_PORT"]),
        ssl={"ssl": {}},
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10
    )


def _close_orphaned(future):
    """
    A timed-out connect() keeps running in the worker thread. Close whatever
    it eventually hands back so the socket is not leaked.
    """
    try:
        conn = future.result()
    except Exception:
        return

    try:
        conn.close()
    except Exception:
        pass


def db_connection(timeout=6):
    future = None
    try:
        future = _executor.submit(_connect)
        return future.result(timeout=timeout)
    except TimeoutError:
        if future is not None and not future.cancel():
            future.add_done_callback(_close_orphaned)
        print("Database connection timed out")
        return None
    except Exception as e:
        print(f"Database connection error: {e}")
        return None
