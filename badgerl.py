import sqlite3, re, random, telebot

# ==================== ТОКЕН ====================
TOKEN_PART1 = "8650713388:"
TOKEN_PART2 = "AAFbY_4Drg29xAJSYwi1qu7C3x_0q7C3tEY"
bot = telebot.TeleBot(TOKEN_PART1 + TOKEN_PART2)

# ==================== БАЗА ====================
conn = sqlite3.connect("usernames.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(tg_id INTEGER PRIMARY KEY, username TEXT)")
cur.execute("""CREATE TABLE IF NOT EXISTS inventory(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER,
    uname TEXT UNIQUE,
    rarity TEXT DEFAULT 'обычный',
    price INTEGER DEFAULT 100
)""")
cur.execute("CREATE TABLE IF NOT EXISTS balances(tg_id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS equipped(tg_id INTEGER PRIMARY KEY, uname TEXT)")
conn.commit()

# ==================== РЕДКОСТИ ====================
RARITIES = {
    "обычный":  {"emoji": "⚪", "price": 100,   "chance": 0.70},
    "редкий":   {"emoji": "🔵", "price": 500,   "chance": 0.20},
    "эпический":{"emoji": "🟣", "price": 2000,  "chance": 0.07},
    "легендарный":{"emoji": "🟡", "price": 10000,"chance": 0.025},
    "мифический":{"emoji": "🔴", "price": 50000, "chance": 0.005},
}

def roll_rarity():
    r = random.random()
    acc = 0
    for name, data in RARITIES.items():
        acc += data["chance"]
        if r <= acc:
            return name
    return "обычный"

# ==================== УТИЛИТЫ ====================
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

def get_coins(tg_id):
    cur.execute("SELECT coins FROM balances WHERE tg_id=?", (tg_id,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO balances(tg_id, coins) VALUES(?,0)", (tg_id,))
        conn.commit()
        return 0
    return r[0]

def add_coins(tg_id, amount):
    cur.execute("INSERT OR IGNORE INTO balances(tg_id, coins) VALUES(?,0)", (tg_id,))
    cur.execute("UPDATE balances SET coins = coins + ? WHERE tg_id=?", (amount, tg_id))
    conn.commit()

def get_inv(tg_id):
    cur.execute("SELECT uname, rarity, price FROM inventory WHERE tg_id=?", (tg_id,))
    return cur.fetchall()

def get_equipped(tg_id):
    cur.execute("SELECT uname FROM equipped WHERE tg_id=?", (tg_id,))
    r = cur.fetchone()
    return r[0] if r else None

def set_equipped(tg_id, u):
    cur.execute("INSERT OR REPLACE INTO equipped(tg_id, uname) VALUES(?,?)", (tg_id, u))
    conn.commit()

def username_of(tg_id):
    cur.execute("SELECT username FROM users WHERE tg_id=?", (tg_id,))
    r = cur.fetchone()
    return r[0] if r else None

# ==================== ХЕНДЛЕРЫ ====================

@bot.message_handler(commands=["start"])
def start(m):
    bot.reply_to(m, "Привет! Напиши `команды`, чтобы увидеть всё меню.", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "команды")
def commands(m):
    text = (
        "📋 **Меню команд**\n\n"
        "🎒 **Инвентарь**\n"
        "• `взять @user` — забрать ник\n"
        "• `инвентарь` — твои ники\n"
        "• `поставить @user` — поставить лучший ник в профиль\n"
        "• `дать @user` — передать (ответом на сообщение)\n"
        "• `барыга продать @user` — продать ник\n\n"
        "💰 **Экономика**\n"
        "• `баланс` — твои монеты\n"
        "• `топ` — топ богачей\n\n"
        "👤 **Профиль**\n"
        "• `профиль` — твой профиль\n"
        "• `профиль @user` — профиль другого\n\n"
        "ℹ️ **Редкости:**\n"
        + "\n".join(f"{d['emoji']} **{n}** — {d['price']} 🪙" for n, d in RARITIES.items())
    )
    bot.reply_to(m, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("взять"))
def take(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "взять @user")
    u = norm(p[1])
    if not re.fullmatch(r"@[a-z0-9_]{3,32}", u): return bot.reply_to(m, "Плохой юз")
    if owner(u): return bot.reply_to(m, "Занят")
    rar = roll_rarity()
    price = RARITIES[rar]["price"]
    cur.execute("INSERT INTO inventory(tg_id,uname,rarity,price) VALUES(?,?,?,?)", (m.from_user.id, u, rar, price))
    conn.commit()
    bot.reply_to(m, f"✅ {u} твой!\n{RARITIES[rar]['emoji']} Редкость: **{rar}**\n💰 Цена: {price} 🪙", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("дать"))
def give(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "дать @user (ответом на сообщение)")
    u = norm(p[1])
    if owner(u) != m.from_user.id: return bot.reply_to(m, "Нет такого")
    t = m.reply_to_message.from_user.id if m.reply_to_message else by_uname(p[1])
    if not t: return bot.reply_to(m, "Ответь на сообщение получателя")
    cur.execute("UPDATE inventory SET tg_id=? WHERE uname=?", (t, u))
    conn.commit()
    bot.reply_to(m, f"➡️ {u} передан")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "инвентарь")
def inv(m):
    items = get_inv(m.from_user.id)
    if not items:
        return bot.reply_to(m, "🎒 Инвентарь пуст")
    text = "🎒 **Твой инвентарь:**\n\n"
    for u, rar, price in items:
        text += f"{RARITIES[rar]['emoji']} {u} — **{rar}** ({price} 🪙)\n"
    bot.reply_to(m, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("поставить"))
def equip(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "поставить @user")
    u = norm(p[1])
    if owner(u) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого ника")
    set_equipped(m.from_user.id, u)
    bot.reply_to(m, f"⭐ Лучший ник установлен: {u}")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("барыга продать"))
def sell(m):
    p = m.text.split()
    if len(p) < 3: return bot.reply_to(m, "барыга продать @user")
    u = norm(p[2])
    if owner(u) != m.from_user.id: return bot.reply_to(m, "Нет такого")
    cur.execute("SELECT rarity, price FROM inventory WHERE uname=?", (u,))
    rar, price = cur.fetchone()
    cur.execute("DELETE FROM inventory WHERE uname=?", (u,))
    cur.execute("DELETE FROM equipped WHERE tg_id=? AND uname=?", (m.from_user.id, u))
    add_coins(m.from_user.id, price)
    conn.commit()
    bot.reply_to(m, f"💰 Продал {u} ({rar}) за **{price}** 🪙\n💰 Баланс: {get_coins(m.from_user.id)}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "баланс")
def balance(m):
    bot.reply_to(m, f"💰 У тебя **{get_coins(m.from_user.id)}** монет", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "топ")
def top(m):
    cur.execute("SELECT tg_id, coins FROM balances ORDER BY coins DESC LIMIT 10")
    rows = cur.fetchall()
    if not rows: return bot.reply_to(m, "Пока никого нет")
    text = "🏆 **Топ богачей:**\n\n"
    for i, (tid, coins) in enumerate(rows, 1):
        uname = username_of(tid) or f"ID {tid}"
        text += f"{i}. {uname} — {coins} 🪙\n"
    bot.reply_to(m, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("профиль"))
def profile(m):
    p = m.text.split()
    target_id = m.from_user.id
    if len(p) >= 2:
        tid = by_uname(p[1])
        if tid: target_id = tid
    elif m.reply_to_message:
        target_id = m.reply_to_message.from_user.id

    uname = username_of(target_id) or f"ID {target_id}"
    coins = get_coins(target_id)
    best = get_equipped(target_id) or "не установлен"
    items = get_inv(target_id)

    text = (
        f"👤 **Профиль**\n\n"
        f"🔗 Твой Telegram: {uname}\n"
        f"⭐ Лучший ник: {best}\n"
        f"💰 Монет: {coins}\n"
        f"🎒 Ников в инвентаре: {len(items)}\n"
    )
    if items:
        text += "\n**Ники:**\n"
        for u, rar, price in items:
            text += f"{RARITIES[rar]['emoji']} {u} — {rar} ({price} 🪙)\n"
    bot.reply_to(m, text, parse_mode="Markdown")

# ВАЖНО: последним, иначе перехватит команды
@bot.message_handler(func=lambda m: m.text and m.from_user.username)
def track(m):
    cur.execute("INSERT OR REPLACE INTO users VALUES(?,?)", (m.from_user.id, norm(m.from_user.username)))
    conn.commit()

bot.infinity_polling()