import sqlite3
import re
import telebot
from telebot import types

# ===== ТОКЕНЫ =====
TOKEN1 = "8650713388:"
TOKEN2 =
"AAGZAvvzSHcUiL5AeWUbk5kLJ8BGaiu8Ss8"

# Выбираем, какой токен использовать (например, TOKEN1)
TOKEN = TOKEN1

bot = telebot.TeleBot(TOKEN)

# ===== БАЗА =====
conn = sqlite3.connect("usernames.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    username TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER,
    uname TEXT UNIQUE,
    price INTEGER DEFAULT 100
)
""")
conn.commit()

SELL_PRICE = 100  # цена продажи барыге

# ===== УТИЛИТЫ =====
def normalize(u: str) -> str:
    u = u.strip().lower()
    if not u.startswith("@"):
        u = "@" + u
    return u

def get_inventory(tg_id: int):
    cur.execute("SELECT uname FROM inventory WHERE tg_id=?", (tg_id,))
    return [r[0] for r in cur.fetchall()]

def owner_of(uname: str):
    cur.execute("SELECT tg_id FROM inventory WHERE uname=?", (uname,))
    r = cur.fetchone()
    return r[0] if r else None

def find_tg_by_username(uname: str):
    uname = normalize(uname)
    cur.execute("SELECT tg_id FROM users WHERE username=?", (uname,))
    r = cur.fetchone()
    return r[0] if r else None

# ===== ХЕНДЛЕРЫ =====

@bot.message_handler(commands=["start"])
def start(m):
    bot.reply_to(m, "Привет! Команды:\n"
                     "• взять @username\n"
                     "• дать @username (ответом на сообщение получателя или по @username, если он писал боту)\n"
                     "• инвентарь\n"
                     "• барыга продать @username")

# регистрируем username игрока, чтобы можно было передавать по @username
@bot.message_handler(func=lambda m: True, content_types=["text"])
def track_user(m):
    if m.from_user.username:
        cur.execute("INSERT OR REPLACE INTO users(tg_id, username) VALUES(?,?)",
                    (m.from_user.id, normalize(m.from_user.username)))
        conn.commit()

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("взять"))
def take(m):
    parts = m.text.split()
    if len(parts) < 2:
        return bot.reply_to(m, "Формат: взять @username")
    uname = normalize(parts[1])
    if not re.fullmatch(r"@[a-z0-9_]{3,32}", uname):
        return bot.reply_to(m, "Некорректный юз.")
    if owner_of(uname):
        return bot.reply_to(m, f"{uname} уже занят.")
    cur.execute("INSERT INTO inventory(tg_id, uname) VALUES(?,?)", (m.from_user.id, uname))
    conn.commit()
    bot.reply_to(m, f"✅ {uname} теперь в твоём инвентаре.")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("дать"))
def give(m):
    parts = m.text.split()
    if len(parts) < 2:
        return bot.reply_to(m, "Формат: дать @username (ответом на сообщение получателя)")
    uname = normalize(parts[1])

    if owner_of(uname) != m.from_user.id:
        return bot.reply_to(m, "У тебя нет такого юза.")

    # получатель: если ответ на сообщение — берём автора, иначе ищем по @username
    target_id = None
    if m.reply_to_message:
        target_id = m.reply_to_message.from_user.id
    else:
        target_id = find_tg_by_username(parts[1])  # тут @username получателя

    if not target_id:
        return bot.reply_to(m, "Не нашёл получателя. Ответь на его сообщение или пусть он напишет боту.")

    cur.execute("UPDATE inventory SET tg_id=? WHERE uname=?", (target_id, uname))
    conn.commit()
    bot.reply_to(m, f"➡️ {uname} передан пользователю {target_id}.")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "инвентарь")
def inv(m):
    items = get_inventory(m.from_user.id)
    if not items:
        return bot.reply_to(m, "Инвентарь пуст.")
    text = "🎒 Твой инвентарь:\n" + "\n".join(f"• {u}" for u in items)
    bot.reply_to(m, text)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("барыга продать"))
def sell(m):
    parts = m.text.split()
    if len(parts) < 3:
        return bot.reply_to(m, "Формат: барыга продать @username")
    uname = normalize(parts[2])
    if owner_of(uname) != m.from_user.id:
        return bot.reply_to(m, "У тебя нет такого юза.")
    cur.execute("DELETE FROM inventory WHERE uname=?", (uname,))
    conn.commit()
    bot.reply_to(m, f"💰 Продал {uname} барыге за {SELL_PRICE} монет.")

print("Бот запущен...")
bot.infinity_polling()