import pymysql.cursors

def db_connection():
    try:
        conn = pymysql.connect(
            host="mysql-24dc61de-hetavinpokiya4672-3a92.e.aivencloud.com",
            user="avnadmin",
            password="AVNS_WNKhz5moqAbf9Nlo5uq",
            database="chatoat",
            port=17627,
            ssl={"ssl": {}},
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None