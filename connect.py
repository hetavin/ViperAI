import pymysql.cursors
from concurrent.futures import ThreadPoolExecutor, TimeoutError

_executor = ThreadPoolExecutor(max_workers=4)


def _connect():
    return pymysql.connect(
        host="mysql-24dc61de-hetavinpokiya4672-3a92.e.aivencloud.com",
        user="avnadmin",
        password="AVNS_WNKhz5moqAbf9Nlo5uq",
        database="chatboat",
        port=17627,
        ssl={"ssl": {}},
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10
    )


def db_connection(timeout=6):
    try:
        future = _executor.submit(_connect)
        return future.result(timeout=timeout)
    except TimeoutError:
        print("Database connection timed out")
        return None
    except Exception as e:
        print(f"Database connection error: {e}")
        return None
