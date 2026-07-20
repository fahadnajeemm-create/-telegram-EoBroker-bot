import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("subscriptions.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    expire TEXT
)
""")

conn.commit()


def add_subscription(user_id, days):
    expire = datetime.now() + timedelta(days=days)

    cursor.execute("""
    INSERT OR REPLACE INTO users(user_id, expire)
    VALUES(?,?)
    """, (user_id, expire.strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()


def remove_subscription(user_id):
    cursor.execute(
        "DELETE FROM users WHERE user_id=?",
        (user_id,)
    )
    conn.commit()


def check_subscription(user_id):
    cursor.execute(
        "SELECT expire FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    if row is None:
        return False

    expire = datetime.strptime(
        row[0],
        "%Y-%m-%d %H:%M:%S"
    )

    return expire > datetime.now()


def days_left(user_id):
    cursor.execute(
        "SELECT expire FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    if row is None:
        return 0

    expire = datetime.strptime(
        row[0],
        "%Y-%m-%d %H:%M:%S"
    )

    return max((expire - datetime.now()).days, 0)


def all_users():
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()
