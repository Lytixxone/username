import sqlite3, re, random, time, telebot
from collections import Counter
from telebot import types

# ==================== ТОКЕН ====================
TOKEN_PART1 = "8650713388:"
TOKEN_PART2 = "AAFbY_4Drg29xAJSYwi1qu7C3x_0q7C3tEY"
bot = telebot.TeleBot(TOKEN_PART1 + TOKEN_PART2)

ADMIN_IDS = {5458427637}  # ← вставь свой Telegram ID (узнать: @userinfobot)

# ==================== БАЗА ====================
conn = sqlite3.connect("usernames.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(tg_id INTEGER PRIMARY KEY, username TEXT)")
cur.execute("""CREATE TABLE IF NOT EXISTS inventory(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER, item TEXT UNIQUE, type TEXT, rarity TEXT, price INTEGER)""")
cur.execute("CREATE TABLE IF NOT EXISTS balances(tg_id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS equipped(tg_id INTEGER PRIMARY KEY, best_user TEXT, best_number TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS slots(tg_id INTEGER PRIMARY KEY, ub INTEGER DEFAULT 0, nb INTEGER DEFAULT 0)")
cur.execute("""CREATE TABLE IF NOT EXISTS listings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER, item TEXT, type TEXT, rarity TEXT, price INTEGER)""")
cur.execute("CREATE TABLE IF NOT EXISTS daily(tg_id INTEGER PRIMARY KEY, last_claim INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS achievements(tg_id INTEGER, code TEXT, PRIMARY KEY(tg_id, code))")
conn.commit()

# ==================== РЕДКОСТИ ====================
RARITIES = {
    "обычный":     {"emoji": "⚪", "price": 100},
    "редкий":      {"emoji": "🔵", "price": 500},
    "эпический":   {"emoji": "🟣", "price": 2000},
    "легендарный": {"emoji": "🟡", "price": 10000},
    "мифический":  {"emoji": "🔴", "price": 50000},
    "мега":        {"emoji": "💎", "price": 1_000_000_000},
}

TAKE_COST = {
    "обычный":     0,
    "редкий":      100,
    "эпический":   500,
    "легендарный": 2500,
    "мифический":  10000,
    "мега":        50000,
}

KNOWN_NICKS = {"durov", "lytixx", "developer"}

ACHIEVEMENTS = {
    "first":   {"emoji": "🥉", "name": "Первый ник"},
    "ten":     {"emoji": "🥈", "name": "10 ников продано"},
    "rich":    {"emoji": "💰", "name": "Богач (10 000 🪙)"},
    "mega":    {"emoji": "💎", "name": "Обладатель мега-ника"},
    "number":  {"emoji": "📱", "name": "Первый номер"},
    "trader":  {"emoji": "🤝", "name": "Первая сделка на бирже"},
}

# ==================== УТИЛИТЫ ====================
def norm(u):
    u = u.strip().lower()
    return u if u.startswith("@") else "@" + u

def norm_num(s):
    s = re.sub(r"[\s\-\(\)]", "", s.strip())
    if not s.startswith("+"): s = "+" + s
    return s

def rarity_user(u):
    name = u[1:].lower()
    if name in KNOWN_NICKS: return "мега"
    if not re.fullmatch(r"[a-z]+", name):
        return "редкий" if len(name) <= 3 else "обычный"
    L = len(name)
    if L <= 3: return "мифический"
    if L <= 4: return "легендарный"
    if L <= 5: return "эпический"
    if L <= 7: return "редкий"
    return "обычный"

def rarity_number(num):
    digits = re.sub(r"\D", "", num)
    if not digits: return "обычный"
    c = Counter(digits).most_common(1)[0][1]
    if c >= 6: return "мифический"
    if c >= 5: return "легендарный"
    if c >= 4: return "эпический"
    if c >= 3: return "редкий"
    return "обычный"

def owner(item):
    cur.execute("SELECT tg_id FROM inventory WHERE item=?", (item,))
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
        cur.execute("INSERT INTO balances(tg_id,coins) VALUES(?,0)", (tg_id,)); conn.commit(); return 0
    return r[0]

def add_coins(tg_id, amount):
    cur.execute("INSERT OR IGNORE INTO balances(tg_id,coins) VALUES(?,0)", (tg_id,))
    cur.execute("UPDATE balances SET coins = coins + ? WHERE tg_id=?", (amount, tg_id))
    conn.commit()

def get_inv(tg_id, typ=None):
    if typ:
        cur.execute("SELECT item, rarity, price FROM inventory WHERE tg_id=? AND type=?", (tg_id, typ))
    else:
        cur.execute("SELECT item, rarity, price, type FROM inventory WHERE tg_id=?", (tg_id,))
    return cur.fetchall()

def count_items(tg_id, typ):
    cur.execute("SELECT COUNT(*) FROM inventory WHERE tg_id=? AND type=?", (tg_id, typ))
    return cur.fetchone()[0]

def get_bought(tg_id):
    cur.execute("SELECT ub, nb FROM slots WHERE tg_id=?", (tg_id,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO slots(tg_id,ub,nb) VALUES(?,0,0)", (tg_id,)); conn.commit(); return 0, 0
    return r

def slots_limit(tg_id, typ):
    ub, nb = get_bought(tg_id)
    return 5 + 5 * (ub if typ == "user" else nb)

def slot_cost(tg_id, typ):
    ub, nb = get_bought(tg_id)
    return 100 * ((ub if typ == "user" else nb) + 1)

def get_equipped(tg_id):
    cur.execute("SELECT best_user, best_number FROM equipped WHERE tg_id=?", (tg_id,))
    return cur.fetchone() or (None, None)

def set_eq(tg_id, user=None, number=None):
    bu, bn = get_equipped(tg_id)
    cur.execute("INSERT OR REPLACE INTO equipped(tg_id,best_user,best_number) VALUES(?,?,?)",
                (tg_id, user if user is not None else bu, number if number is not None else bn))
    conn.commit()

def clear_eq(tg_id, item):
    cur.execute("UPDATE equipped SET best_user=CASE WHEN best_user=? THEN NULL ELSE best_user END WHERE tg_id=?", (item, tg_id))
    cur.execute("UPDATE equipped SET best_number=CASE WHEN best_number=? THEN NULL ELSE best_number END WHERE tg_id=?", (item, tg_id))
    conn.commit()

def username_of(tg_id):
    cur.execute("SELECT username FROM users WHERE tg_id=?", (tg_id,))
    r = cur.fetchone()
    return r[0] if r else None

def display_name(tg_id):
    u = username_of(tg_id)
    if not u: return f"ID {tg_id}"
    return "✅ @lytixx" if u == "@lytixx" else u

def parse_item(arg):
    if arg.startswith("+"): return norm_num(arg), "number"
    if re.fullmatch(r"\d{5,15}", arg): return norm_num(arg), "number"
    return norm(arg), "user"

def register(tg_id, username):
    if username:
        cur.execute("INSERT OR REPLACE INTO users VALUES(?,?)", (tg_id, norm(username))); conn.commit()

def grant(tg_id, code):
    cur.execute("INSERT OR IGNORE INTO achievements(tg_id, code) VALUES(?,?)", (tg_id, code))
    conn.commit()

def has(tg_id, code):
    cur.execute("SELECT 1 FROM achievements WHERE tg_id=? AND code=?", (tg_id, code))
    return cur.fetchone() is not None

def check_rich(tg_id):
    if get_coins(tg_id) >= 10000 and not has(tg_id, "rich"):
        grant(tg_id, "rich")

# ==================== МЕНЮ ====================
def commands_text():
    return (
        "📋 **Меню команд**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎒 **КОЛЛЕКЦИЯ**\n"
        "• `взять @user` — забрать ник (платно для редких)\n"
        "• `номер +77777777777` — забрать номер\n"
        "• `инвентарь` — твоя коллекция\n"
        "• `поставить @user` — лучший ник в профиль\n"
        "• `поставить +7777` — лучший номер\n"
        "• `дать @user` — передать (ответом на сообщение)\n"
        "• `дать +7777` — передать номер (ответом)\n\n"
        "💰 **ПРОДАЖА**\n"
        "• `продать @user` — продать барыге\n"
        "• `продать +7777` — продать номер\n"
        "• `продать несколько @a +7... @b` — пачкой\n"
        "• `продать всё` — весь инвентарь\n\n"
        "🏦 **БИРЖА**\n"
        "• `биржа` — последние лоты\n"
        "• `выставить @user 500` — выставить лот\n"
        "• `снять <id>` — забрать свой лот\n"
        "• `купить <id>` — купить лот\n\n"
        "📦 **СЛОТЫ**\n"
        "• `слот` — инфо о слотах\n"
        "• `слот купить юзы` — +5 слотов ников\n"
        "• `слот купить номера` — +5 слотов номеров\n\n"
        "🎁 **БОНУСЫ**\n"
        "• `бонус` — ежедневный бонус (50–200 🪙)\n\n"
        "👤 **ПРОФИЛЬ И СТАТА**\n"
        "• `профиль` — твой профиль\n"
        "• `профиль @user` — чужой профиль\n"
        "• `профиль` ответом — профиль автора\n"
        "• `баланс` — твои монеты\n"
        "• `топ` — топ-10 богачей\n"
        "• `ачивки` — твои достижения\n\n"
        "ℹ️ **ИНФО**\n"
        "• `цены` — цена взятия/продажи\n"
        "• `команды` — это меню\n\n"
        "👑 **АДМИН**\n"
        "• `админ выдать @user 1000` — выдать монеты\n"
        "• `админ топ` — статистика бота\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💎 **РЕДКОСТИ (взять / продать):**\n"
        "⚪ обычный — `0` / `100` 🪙\n"
        "🔵 редкий — `100` / `500` 🪙\n"
        "🟣 эпический — `500` / `2 000` 🪙\n"
        "🟡 легендарный — `2 500` / `10 000` 🪙\n"
        "🔴 мифический — `10 000` / `50 000` 🪙\n"
        "💎 мега — `50 000` / `1 000 000 000` 🪙\n\n"
        "💡 Короткие ники без цифр и красивые номера — самые дорогие."
    )

# ==================== ХЕНДЛЕРЫ ====================

@bot.message_handler(commands=["start"])
def start(m):
    register(m.from_user.id, m.from_user.username)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📋 Команды", callback_data="show_commands"))
    bot.reply_to(m, "👋 Привет!\nНажми «Команды» или напиши `команды`.", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "show_commands")
def cb_commands(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, commands_text(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "команды")
def commands(m):
    bot.reply_to(m, commands_text(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "цены")
def prices(m):
    txt = "💸 **Цены взятия и продажи**\n\n"
    for n, d in RARITIES.items():
        txt += f"{d['emoji']} **{n}**\n   взять: `{TAKE_COST[n]} 🪙` | продать: `{d['price']} 🪙`\n"
    txt += "\n💡 Короткие ники и красивые номера — дорогие, но и продать их можно дороже."
    bot.reply_to(m, txt, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower() in ("бонус", "ежедневно", "daily"))
def daily(m):
    register(m.from_user.id, m.from_user.username)
    cur.execute("SELECT last_claim FROM daily WHERE tg_id=?", (m.from_user.id,))
    r = cur.fetchone()
    now = int(time.time())
    if r and now - r[0] < 86400:
        left = 86400 - (now - r[0])
        h, rem = divmod(left, 3600)
        return bot.reply_to(m, f"⏳ Следующий бонус через **{h}ч {rem//60}м**", parse_mode="Markdown")
    reward = random.randint(50, 200)
    add_coins(m.from_user.id, reward)
    cur.execute("INSERT OR REPLACE INTO daily(tg_id,last_claim) VALUES(?,?)", (m.from_user.id, now))
    conn.commit()
    bot.reply_to(m, f"🎁 Ты получил **{reward}** 🪙!\n💰 Баланс: {get_coins(m.from_user.id)}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("взять"))
def take(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "взять @user")
    u = norm(p[1])
    if not re.fullmatch(r"@[a-z0-9_]{3,32}", u): return bot.reply_to(m, "Плохой юз")
    if owner(u): return bot.reply_to(m, "Занят")
    lim = slots_limit(m.from_user.id, "user")
    if count_items(m.from_user.id, "user") >= lim:
        return bot.reply_to(m, f"❌ Лимит: {lim}. Расширь: `слот купить юзы`", parse_mode="Markdown")
    rar = rarity_user(u)
    cost = TAKE_COST[rar]
    if cost > 0:
        if get_coins(m.from_user.id) < cost:
            return bot.reply_to(m,
                f"❌ Чтобы взять {u} ({RARITIES[rar]['emoji']} **{rar}**), нужно **{cost}** 🪙\n"
                f"💰 У тебя: {get_coins(m.from_user.id)} 🪙\n"
                f"🎁 Напиши `бонус` или продай что-нибудь.", parse_mode="Markdown")
        add_coins(m.from_user.id, -cost)
    price = RARITIES[rar]["price"]
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, u, "user", rar, price)); conn.commit()
    if not has(m.from_user.id, "first"): grant(m.from_user.id, "first")
    if rar == "мега" and not has(m.from_user.id, "mega"):
        grant(m.from_user.id, "mega")
        bot.reply_to(m, f"🏆 Ачивка: {ACHIEVEMENTS['mega']['emoji']} {ACHIEVEMENTS['mega']['name']}!")
    msg = f"✅ {u} твой!\n{RARITIES[rar]['emoji']} **{rar}** — продать: {price} 🪙"
    if cost > 0: msg += f"\n💸 Заплачено: {cost} 🪙\n💰 Баланс: {get_coins(m.from_user.id)}"
    bot.reply_to(m, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("номер"))
def take_number(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "номер +77777777777")
    num = norm_num(p[1])
    if not re.fullmatch(r"\+[0-9]{5,15}", num):
        return bot.reply_to(m, "Формат: `номер +77777777777`", parse_mode="Markdown")
    if owner(num): return bot.reply_to(m, "Занят")
    lim = slots_limit(m.from_user.id, "number")
    if count_items(m.from_user.id, "number") >= lim:
        return bot.reply_to(m, f"❌ Лимит: {lim}. Расширь: `слот купить номера`", parse_mode="Markdown")
    rar = rarity_number(num)
    cost = TAKE_COST[rar]
    if cost > 0:
        if get_coins(m.from_user.id) < cost:
            return bot.reply_to(m,
                f"❌ Чтобы взять {num} ({RARITIES[rar]['emoji']} **{rar}**), нужно **{cost}** 🪙\n"
                f"💰 У тебя: {get_coins(m.from_user.id)} 🪙", parse_mode="Markdown")
        add_coins(m.from_user.id, -cost)
    price = RARITIES[rar]["price"]
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, num, "number", rar, price)); conn.commit()
    if not has(m.from_user.id, "number"): grant(m.from_user.id, "number")
    msg = f"✅ {num} твой!\n{RARITIES[rar]['emoji']} **{rar}** — продать: {price} 🪙"
    if cost > 0: msg += f"\n💸 Заплачено: {cost} 🪙\n💰 Баланс: {get_coins(m.from_user.id)}"
    bot.reply_to(m, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("дать"))
def give(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "дать @user / дать +7777 (ответом)")
    item, typ = parse_item(p[1])
    if owner(item) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого")
    if m.reply_to_message:
        target = m.reply_to_message.from_user.id
    elif typ == "user":
        target = by_uname(p[1])
    else:
        return bot.reply_to(m, "Номер передаётся только ответом")
    if not target: return bot.reply_to(m, "Ответь на сообщение получателя")
    if count_items(target, typ) >= slots_limit(target, typ):
        return bot.reply_to(m, "У получателя нет места")
    cur.execute("UPDATE inventory SET tg_id=? WHERE item=?", (target, item)); conn.commit()
    bot.reply_to(m, f"➡️ {item} передан")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "инвентарь")
def inv(m):
    items = get_inv(m.from_user.id)
    if not items: return bot.reply_to(m, "🎒 Пусто. Загляни в `команды`.", parse_mode="Markdown")
    users = [i for i in items if i[3] == "user"]
    numbers = [i for i in items if i[3] == "number"]
    txt = "🎒 **Твой инвентарь**\n\n"
    if users:
        txt += f"👤 **Ники** ({len(users)}/{slots_limit(m.from_user.id,'user')}):\n"
        for it, rar, price, _ in users:
            txt += f"{RARITIES[rar]['emoji']} {it} — {rar} ({price} 🪙)\n"
    if numbers:
        txt += f"\n📱 **Номера** ({len(numbers)}/{slots_limit(m.from_user.id,'number')}):\n"
        for it, rar, price, _ in numbers:
            txt += f"{RARITIES[rar]['emoji']} {it} — {rar} ({price} 🪙)\n"
    bot.reply_to(m, txt, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("поставить"))
def equip(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "поставить @user / поставить +7777")
    item, typ = parse_item(p[1])
    if owner(item) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого")
    if typ == "user":
        set_eq(m.from_user.id, user=item)
        bot.reply_to(m, f"⭐ Лучший ник: {item}")
    else:
        set_eq(m.from_user.id, number=item)
        bot.reply_to(m, f"⭐ Лучший номер: {item}")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("продать"))
def sell(m):
    text = m.text.lower()
    if text in ("продать всё", "продать все"):
        items = get_inv(m.from_user.id)
        if not items: return bot.reply_to(m, "Нечего продавать")
        total = sum(i[2] for i in items)
        for it, _, _, _ in items:
            cur.execute("DELETE FROM inventory WHERE item=?", (it,))
        cur.execute("DELETE FROM equipped WHERE tg_id=?", (m.from_user.id,))
        add_coins(m.from_user.id, total); conn.commit()
        if not has(m.from_user.id, "ten") and len(items) >= 10: grant(m.from_user.id, "ten")
        check_rich(m.from_user.id)
        return bot.reply_to(m, f"💰 Продано {len(items)} шт. за **{total}** 🪙\n💰 Баланс: {get_coins(m.from_user.id)}", parse_mode="Markdown")

    if text.startswith("продать несколько"):
        args = m.text.split()[2:]
        if not args: return bot.reply_to(m, "продать несколько @a @b +7...")
        total = 0; sold = 0; skip = []
        for a in args:
            item, _ = parse_item(a)
            if owner(item) != m.from_user.id: skip.append(item); continue
            cur.execute("SELECT price FROM inventory WHERE item=?", (item,))
            pr = cur.fetchone()[0]
            cur.execute("DELETE FROM inventory WHERE item=?", (item,))
            clear_eq(m.from_user.id, item)
            total += pr; sold += 1
        add_coins(m.from_user.id, total); conn.commit()
        check_rich(m.from_user.id)
        msg = f"💰 Продано {sold} за **{total}** 🪙"
        if skip: msg += f"\n❌ Не найдено: {', '.join(skip)}"
        return bot.reply_to(m, msg, parse_mode="Markdown")

    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "продать @user / продать +7777")
    item, typ = parse_item(p[1])
    if owner(item) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого")
    cur.execute("SELECT price, rarity FROM inventory WHERE item=?", (item,))
    price, rar = cur.fetchone()
    cur.execute("DELETE FROM inventory WHERE item=?", (item,))
    clear_eq(m.from_user.id, item)
    add_coins(m.from_user.id, price); conn.commit()
    check_rich(m.from_user.id)
    bot.reply_to(m, f"💰 Продал {item} ({rar}) за **{price}** 🪙\n💰 Баланс: {get_coins(m.from_user.id)}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "баланс")
def balance(m):
    bot.reply_to(m, f"💰 **{get_coins(m.from_user.id)}** 🪙", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "топ")
def top(m):
    cur.execute("SELECT tg_id, coins FROM balances ORDER BY coins DESC LIMIT 10")
    rows = cur.fetchall()
    if not rows: return bot.reply_to(m, "Пусто")
    txt = "🏆 **Топ богачей**\n\n"
    for i, (tid, coins) in enumerate(rows, 1):
        txt += f"{i}. {display_name(tid)} — {coins} 🪙\n"
    bot.reply_to(m, txt, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "ачивки")
def ach(m):
    cur.execute("SELECT code FROM achievements WHERE tg_id=?", (m.from_user.id,))
    codes = [r[0] for r in cur.fetchall()]
    if not codes: return bot.reply_to(m, "Пока пусто. Собери первый ник: `взять @user`", parse_mode="Markdown")
    txt = "🏅 **Твои ачивки**\n\n"
    for c in codes:
        a = ACHIEVEMENTS.get(c)
        if a: txt += f"{a['emoji']} {a['name']}\n"
    bot.reply_to(m, txt, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("профиль"))
def profile(m):
    p = m.text.split()
    target_id = m.from_user.id
    if len(p) >= 2:
        t = by_uname(p[1])
        if not t: return bot.reply_to(m, "Пользователь не найден")
        target_id = t
    elif m.reply_to_message:
        target_id = m.reply_to_message.from_user.id
    coins = get_coins(target_id)
    bu, bn = get_equipped(target_id)
    users = get_inv(target_id, "user")
    numbers = get_inv(target_id, "number")
    cur.execute("SELECT code FROM achievements WHERE tg_id=?", (target_id,))
    ach_codes = [r[0] for r in cur.fetchall()]
    txt = (
        "╔════════════════════╗\n"
        "║    👤 **Профиль**\n"
        "╚════════════════════╝\n"
        f"🔗 **Telegram:** {display_name(target_id)}\n"
        f"💰 **Монеты:** {coins} 🪙\n"
        f"⭐ **Лучший ник:** {bu or '—'}\n"
        f"📱 **Лучший номер:** {bn or '—'}\n"
        f"🏅 **Ачивок:** {len(ach_codes)}/{len(ACHIEVEMENTS)}\n\n"
        f"👤 **Ники** ({len(users)}/{slots_limit(target_id,'user')}):\n"
    )
    txt += "".join(f"{RARITIES[r]['emoji']} {i} — {r} ({p} 🪙){' ⭐' if i==bu else ''}\n" for i, r, p in users) or "—\n"
    txt += f"\n📱 **Номера** ({len(numbers)}/{slots_limit(target_id,'number')}):\n"
    txt += "".join(f"{RARITIES[r]['emoji']} {i} — {r} ({p} 🪙){' ⭐' if i==bn else ''}\n" for i, r, p in numbers) or "—\n"
    if ach_codes:
        txt += "\n🏅 **Ачивки:**\n"
        txt += " ".join(ACHIEVEMENTS[c]["emoji"] for c in ach_codes if c in ACHIEVEMENTS)
    bot.reply_to(m, txt, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("слот"))
def slot_cmd(m):
    text = m.text.lower().strip()
    if text in ("слот", "слоты"):
        uc = slot_cost(m.from_user.id, "user"); nc = slot_cost(m.from_user.id, "number")
        return bot.reply_to(m,
            f"📦 **Слоты**\n\n"
            f"👤 Ники: {count_items(m.from_user.id,'user')}/{slots_limit(m.from_user.id,'user')}\n"
            f"• `слот купить юзы` — {uc} 🪙\n\n"
            f"📱 Номера: {count_items(m.from_user.id,'number')}/{slots_limit(m.from_user.id,'number')}\n"
            f"• `слот купить номера` — {nc} 🪙", parse_mode="Markdown")
    if text == "слот купить юзы":
        cost = slot_cost(m.from_user.id, "user")
        if get_coins(m.from_user.id) < cost: return bot.reply_to(m, f"❌ Нужно {cost} 🪙")
        add_coins(m.from_user.id, -cost)
        ub, nb = get_bought(m.from_user.id)
        cur.execute("UPDATE slots SET ub=? WHERE tg_id=?", (ub+1, m.from_user.id)); conn.commit()
        return bot.reply_to(m, f"✅ +5 слотов. Лимит: {slots_limit(m.from_user.id,'user')}")
    if text == "слот купить номера":
        cost = slot_cost(m.from_user.id, "number")
        if get_coins(m.from_user.id) < cost: return bot.reply_to(m, f"❌ Нужно {cost} 🪙")
        add_coins(m.from_user.id, -cost)
        ub, nb = get_bought(m.from_user.id)
        cur.execute("UPDATE slots SET nb=? WHERE tg_id=?", (nb+1, m.from_user.id)); conn.commit()
        return bot.reply_to(m, f"✅ +5 слотов. Лимит: {slots_limit(m.from_user.id,'number')}")
    bot.reply_to(m, "слот | слот купить юзы | слот купить номера")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "биржа")
def exchange(m):
    cur.execute("SELECT id, seller_id, item, rarity, price FROM listings ORDER BY id DESC LIMIT 30")
    rows = cur.fetchall()
    if not rows: return bot.reply_to(m, "🏦 Биржа пуста")
    txt = "🏦 **Биржа**\n\n"
    for lid, seller, item, rar, price in rows:
        txt += f"`#{lid}` {RARITIES[rar]['emoji']} {item} — **{price}** 🪙 (от {display_name(seller)})\n"
    txt += "\nКупить: `купить <id>`\nСнять: `снять <id>`"
    bot.reply_to(m, txt, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("выставить"))
def list_item(m):
    p = m.text.split()
    if len(p) < 3: return bot.reply_to(m, "выставить @user 500")
    item, typ = parse_item(p[1])
    try: price = int(p[2])
    except: return bot.reply_to(m, "Цена — число")
    if price <= 0: return bot.reply_to(m, "Цена > 0")
    if owner(item) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого")
    cur.execute("SELECT rarity FROM inventory WHERE item=?", (item,))
    rar = cur.fetchone()[0]
    cur.execute("DELETE FROM inventory WHERE item=?", (item,))
    clear_eq(m.from_user.id, item)
    cur.execute("INSERT INTO listings(seller_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, item, typ, rar, price)); conn.commit()
    bot.reply_to(m, f"✅ {item} выставлен за {price} 🪙")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("снять"))
def unlist(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "снять <id>")
    try: lid = int(p[1])
    except: return bot.reply_to(m, "ID — число")
    cur.execute("SELECT seller_id, item, type, rarity, price FROM listings WHERE id=?", (lid,))
    r = cur.fetchone()
    if not r: return bot.reply_to(m, "Лот не найден")
    seller, item, typ, rar, price = r
    if seller != m.from_user.id: return bot.reply_to(m, "Это не твой лот")
    if count_items(seller, typ) >= slots_limit(seller, typ):
        return bot.reply_to(m, "❌ Нет места")
    cur.execute("DELETE FROM listings WHERE id=?", (lid,))
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (seller, item, typ, rar, price)); conn.commit()
    bot.reply_to(m, f"✅ {item} возвращён")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("купить"))
def buy(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "купить <id>")
    try: lid = int(p[1])
    except: return bot.reply_to(m, "ID — число")
    cur.execute("SELECT seller_id, item, type, rarity, price FROM listings WHERE id=?", (lid,))
    r = cur.fetchone()
    if not r: return bot.reply_to(m, "Лот не найден")
    seller, item, typ, rar, price = r
    if seller == m.from_user.id: return bot.reply_to(m, "Это твой лот")
    if get_coins(m.from_user.id) < price: return bot.reply_to(m, f"❌ Нужно {price} 🪙")
    if count_items(m.from_user.id, typ) >= slots_limit(m.from_user.id, typ):
        return bot.reply_to(m, "❌ Нет места. Расширь: `слот`", parse_mode="Markdown")
    add_coins(m.from_user.id, -price); add_coins(seller, price)
    cur.execute("DELETE FROM listings WHERE id=?", (lid,))
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, item, typ, rar, price)); conn.commit()
    if not has(m.from_user.id, "trader"): grant(m.from_user.id, "trader")
    check_rich(seller)
    bot.reply_to(m, f"✅ Купил {item} за {price} 🪙")

# ==================== АДМИН ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("админ выдать"))
def admin_give(m):
    if m.from_user.id not in ADMIN_IDS:
        return bot.reply_to(m, "❌ Нет прав")
    p = m.text.split()
    if len(p) < 4: return bot.reply_to(m, "админ выдать @user 1000")
    target_str, amount_s = p[2], p[3]
    try: amount = int(amount_s)
    except: return bot.reply_to(m, "Сумма — число")
    if target_str.startswith("@"):
        tid = by_uname(target_str)
    else:
        try: tid = int(target_str)
        except: return bot.reply_to(m, "Плохой ID")
    if not tid: return bot.reply_to(m, "Не найден")
    add_coins(tid, amount)
    bot.reply_to(m, f"✅ Выдано {amount} 🪙 → {display_name(tid)}")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "админ топ")
def admin_top(m):
    if m.from_user.id not in ADMIN_IDS: return
    cur.execute("SELECT COUNT(*) FROM users"); u = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM inventory"); i = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM listings"); l = cur.fetchone()[0]
    cur.execute("SELECT SUM(coins) FROM balances"); c = cur.fetchone()[0] or 0
    bot.reply_to(m, f"📊 **Стата бота**\n👥 Игроков: {u}\n🎒 Предметов: {i}\n🏦 Лотов: {l}\n💰 Монет в системе: {c}", parse_mode="Markdown")

# ВАЖНО: последним
@bot.message_handler(func=lambda m: m.text and m.from_user.username)
def track(m):
    register(m.from_user.id, m.from_user.username)

print("Бот запущен...")
bot.infinity_polling(timeout=60, long_polling_timeout=60)