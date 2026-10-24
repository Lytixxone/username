import os, re, sqlite3, telebot

# Токен берётся из переменной окружения BOT_TOKEN — в коде его нет
TOKEN = os.getenv("8650713388:AAFbY_4Drg29xAJSYwi1qu7C3x_0q7C3tEY")
if not TOKEN:
    raise SystemExit("Задай переменную окружения BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

conn = sqlite3.connect("usernames.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(tg_id INTEGER PRIMARY KEY, username TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS inventory(id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, uname TEXT UNIQUE)")
conn.commit()

SELL_PRICE = 100

def norm(u):
    u = u.strip().lower()
    return u if u.startswith("@") else "@" + u

def owner(u):
    cur.execute("SELECT tg_id FROM inventory WHERE uname=?", (u,))
    r = cur.fetchone()
    return r[0] if r else None

def by_uname(u):
    cur.execute("SELECT tg_id FROM users WHERE username=?", (norm(u),))
    r = cur.fetchone()
    return r[0] if r else None

@bot.message_handler(commands=["start"])
def start(m):
    bot.reply_to(m, "взять @user\nдать @user\nинвентарь\nбарыга продать @user")

@bot.message_handler(func=lambda m: m.text and m.from_user.username)
def track(m):
    cur.execute("INSERT OR REPLACE INTO users VALUES(?,?)", (m.from_user.id, norm(m.from_user.username)))
    conn.commit()

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("взять"))
def take(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "взять @user")
    u = norm(p[1])
    if not re.fullmatch(r"@[a-z0-9_]{3,32}", u): return bot.reply_to(m, "Плохой юз")
    if owner(u): return bot.reply_to(m, "Занят")
    cur.execute("INSERT INTO inventory(tg_id,uname) VALUES(?,?)", (m.from_user.id, u))
    conn.commit()
    bot.reply_to(m, f"✅ {u} твой")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("дать"))
def give(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "дать @user")
    u = norm(p[1])
    if owner(u) != m.from_user.id: return bot.reply_to(m, "Нет такого")
    t = m.reply_to_message.from_user.id if m.reply_to_message else by_uname(p[1])
    if not t: return bot.reply_to(m, "Ответь на сообщение получателя")
    cur.execute("UPDATE inventory SET tg_id=? WHERE uname=?", (t, u))
    conn.commit()
    bot.reply_to(m, f"➡️ {u} передан")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "инвентарь")
def inv(m):
    cur.execute("SELECT uname FROM inventory WHERE tg_id=?", (m.from_user.id,))
    items = [r[0] for r in cur.fetchall()]
    bot.reply_to(m, "🎒 " + ("\n".join(items) if items else "пусто"))

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("барыга продать"))
def sell(m):
    p = m.text.split()
    if len(p) < 3: return bot.reply_to(m, "барыга продать @user")
    u = norm(p[2])
    if owner(u) != m.from_user.id: return bot.reply_to(m, "Нет такого")
    cur.execute("DELETE FROM inventory WHERE uname=?", (u,))
    conn.commit()
    bot.reply_to(m, f"💰 Продал {u} за {SELL_PRICE}")

if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()