import sqlite3, re, random, time, telebot
from collections import Counter
from telebot import types

# ==================== ТОКЕН ====================
TOKEN_PART1 = "8650713388:"
TOKEN_PART2 = "AAFbY_4Drg29xAJSYwi1qu7C3x_0q7C3tEY"
bot = telebot.TeleBot(TOKEN_PART1 + TOKEN_PART2)

ADMIN_USERNAMES = {"lytixx"}   # Telegram-ники админов (без @, в нижнем регистре)
ADMIN_IDS = set()              # опционально: сюда можно вписать Telegram ID

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
    "мега":        {"emoji": "💎", "price": 99_000_000},
}

SPECIAL_RARITIES = {
    "@durov": "мега", "@lytixx": "мега",
    "@developer": "мифический", "@telegram": "мифический",
    "@botfather": "мифический", "@tgpremium": "мифический",
    "@tme": "эпический", "@tgs": "эпический",
    "@crow": "эпический", "@free": "эпический",
    "@tg": "редкий", "@me": "редкий", "@s": "редкий",
    "@bot": "редкий", "@web": "редкий",
    "@father": "редкий", "@premium": "редкий",
}

SPECIAL_PRICES = {
    "@durov": 99_000_000, "@lytixx": 99_000_000,
    "@developer": 50_000_000, "@telegram": 25_000_000,
    "@botfather": 20_000_000, "@tgpremium": 15_000_000,
    "@tme": 10_000_000, "@tgs": 5_000_000,
    "@crow": 3_000_000, "@free": 3_000_000,
    "@tg": 500_000, "@me": 500_000, "@s": 500_000,
    "@bot": 500_000, "@web": 500_000,
    "@father": 500_000, "@premium": 500_000,
}

CRAFT_TARGETS = {"@durov", "@lytixx", "@developer", "@telegram",
                 "@botfather", "@tgpremium", "@tme", "@tgs"}

RECIPES = {
    "@durov":     {"target_rarity": "мега",       "fixed": ["@crow", "@free"],   "random_count": 7, "min_rarity": "эпический",   "success": 0.50},
    "@lytixx":    {"target_rarity": "мега",       "fixed": [],                   "random_count": 10,"min_rarity": "эпический",   "success": 0.50},
    "@developer": {"target_rarity": "мифический", "fixed": ["@tg", "@bot"],      "random_count": 5, "min_rarity": "легендарный", "success": 0.50},
    "@telegram":  {"target_rarity": "мифический", "fixed": ["@tme", "@web"],     "random_count": 3, "min_rarity": "эпический",   "success": 0.60},
    "@botfather": {"target_rarity": "мифический", "fixed": ["@bot", "@father"],  "random_count": 3, "min_rarity": "редкий",      "success": 0.70},
    "@tgpremium": {"target_rarity": "мифический", "fixed": ["@tgs", "@premium"], "random_count": 5, "min_rarity": "эпический",   "success": 0.55},
    "@tme":       {"target_rarity": "эпический",  "fixed": ["@tg", "@me"],       "random_count": 2, "min_rarity": "обычный",     "success": 0.85},
    "@tgs":       {"target_rarity": "эпический",  "fixed": ["@tg", "@s"],        "random_count": 2, "min_rarity": "обычный",     "success": 0.90},
}

ACHIEVEMENTS = {
    "first":   {"emoji": "🥉", "name": "Первый ник"},
    "ten":     {"emoji": "🥈", "name": "10 ников продано"},
    "rich":    {"emoji": "💰", "name": "Богач (10 000 🪙)"},
    "mega":    {"emoji": "💎", "name": "Обладатель мега-ника"},
    "number":  {"emoji": "📱", "name": "Первый номер"},
    "trader":  {"emoji": "🤝", "name": "Первая сделка на бирже"},
    "crafter": {"emoji": "🛠", "name": "Первый крафт"},
}

# ==================== АДМИНКА ====================
def is_admin(tg_id=None, username=None):
    if username:
        uname = username.lower().lstrip("@")
        if uname in ADMIN_USERNAMES:
            return True
    if tg_id and tg_id in ADMIN_IDS:
        return True
    return False

# ==================== УТИЛИТЫ ====================
def norm(u):
    u = u.strip().lower()
    return u if u.startswith("@") else "@" + u

def norm_num(s):
    s = re.sub(r"[\s\-\(\)]", "", s.strip())
    if not s.startswith("+"): s = "+" + s
    return s

def rarity_user(u):
    if u in SPECIAL_RARITIES:
        return SPECIAL_RARITIES[u]
    name = u[1:].lower()
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

def price_of(item, rar):
    return SPECIAL_PRICES.get(item, RARITIES[rar]["price"])

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
    uname = u.lower().lstrip("@")
    if uname in ADMIN_USERNAMES:
        return f"✅ {u}"
    return u

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

# ==================== АНИМАЦИЯ ====================
def drop_animation(chat_id, reply_to_id, final_text, rarity):
    if rarity in ("мега", "мифический"):
        frames = [("🎰 |", 0.22), ("🎰 /", 0.22), ("🎰 —", 0.22), ("🎰 \\", 0.22), ("✨✨✨", 0.35)]
    elif rarity in ("легендарный", "эпический"):
        frames = [("🎰 ...", 0.28), ("✨", 0.32)]
    elif rarity == "редкий":
        frames = [("🎰 ...", 0.3)]
    else:
        bot.send_message(chat_id, final_text, parse_mode="HTML", reply_to_message_id=reply_to_id)
        return

    msg = bot.send_message(chat_id, frames[0][0])
    for text, delay in frames[1:]:
        time.sleep(delay)
        try:
            bot.edit_message_text(text, chat_id, msg.message_id)
        except:
            pass
    time.sleep(0.3)
    try:
        bot.edit_message_text(final_text, chat_id, msg.message_id, parse_mode="HTML")
    except:
        bot.send_message(chat_id, final_text, parse_mode="HTML")

# ==================== ИНВЕНТАРЬ ====================
INV_PAGE_SIZE = 8

def build_inv_page(tg_id, typ, page):
    items = get_inv(tg_id, typ)
    total = len(items)
    pages = max(1, (total + INV_PAGE_SIZE - 1) // INV_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    start = page * INV_PAGE_SIZE
    chunk = items[start:start + INV_PAGE_SIZE]

    title = "👤 Ники" if typ == "user" else "📱 Номера"
    limit = slots_limit(tg_id, typ)
    txt = f"<b>{title}</b> ({total}/{limit}) — стр. {page+1}/{pages}\n\n"
    if not chunk:
        txt += "пусто"
    else:
        for it, rar, price in chunk:
            txt += f"{RARITIES[rar]['emoji']} {it} — {rar} ({price:,} 🪙)\n"
    return txt, page, pages

def inv_keyboard(owner_id, typ, page, pages):
    kb = types.InlineKeyboardMarkup()
    row = []
    if page > 0:
        row.append(types.InlineKeyboardButton("⬅️", callback_data=f"inv:{owner_id}:{typ}:{page-1}"))
    row.append(types.InlineKeyboardButton(f"{page+1}/{pages}", callback_data="inv:noop:0:0"))
    if page < pages - 1:
        row.append(types.InlineKeyboardButton("➡️", callback_data=f"inv:{owner_id}:{typ}:{page+1}"))
    kb.row(*row)
    other = "number" if typ == "user" else "user"
    other_name = "📱 Номера" if other == "number" else "👤 Ники"
    kb.row(types.InlineKeyboardButton(other_name, callback_data=f"inv:{owner_id}:{other}:0"))
    return kb

# ==================== КРАФТ ====================
def get_random_rich(tg_id, min_rarity, exclude, count):
    order = ["обычный", "редкий", "эпический", "легендарный", "мифический", "мега"]
    min_idx = order.index(min_rarity)
    allowed = set(order[min_idx:])
    cur.execute("SELECT item, rarity FROM inventory WHERE tg_id=?", (tg_id,))
    candidates = [
        item for item, rar in cur.fetchall()
        if rar in allowed and item not in exclude and item not in CRAFT_TARGETS
    ]
    if len(candidates) < count:
        return None
    return random.sample(candidates, count)

# ==================== МЕНЮ ====================
def commands_text():
    return (
        "📋 <b>Меню команд</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "🎒 <b>КОЛЛЕКЦИЯ</b>\n"
        "• <code>взять @user</code> — забрать ник (бесплатно)\n"
        "• <code>номер +77777777777</code> — забрать номер\n"
        "• <code>инвентарь</code> — коллекция с листанием\n"
        "• <code>поставить @user</code> — лучший ник\n"
        "• <code>поставить +7777</code> — лучший номер\n"
        "• <code>дать @user</code> / <code>дать +7777</code> — передать (ответом)\n\n"

        "🛠 <b>КРАФТ</b>\n"
        "• <code>крафт</code> — список рецептов\n"
        "• <code>крафт @durov</code> — скрафтить\n"
        "• Шанс успеха 50–90%, при провале компоненты сгорают\n\n"

        "💰 <b>ПРОДАЖА</b>\n"
        "• <code>продать @user</code> / <code>продать +7777</code>\n"
        "• <code>продать несколько @a +7... @b</code>\n"
        "• <code>продать всё</code>\n\n"

        "🏦 <b>БИРЖА</b>\n"
        "• <code>биржа</code> — лоты\n"
        "• <code>выставить @user 500</code>\n"
        "• <code>снять &lt;id&gt;</code> / <code>купить &lt;id&gt;</code>\n\n"

        "📦 <b>СЛОТЫ</b>\n"
        "• <code>слот</code> — инфо\n"
        "• <code>слот купить юзы</code> — +5 слотов ников\n"
        "• <code>слот купить номера</code> — +5 слотов номеров\n\n"

        "🎁 <b>БОНУСЫ</b>\n"
        "• <code>бонус</code> — ежедневно 50–200 🪙\n\n"

        "👤 <b>ПРОФИЛЬ И СТАТА</b>\n"
        "• <code>профиль</code> / <code>профиль @user</code>\n"
        "• <code>баланс</code> / <code>топ</code> / <code>ачивки</code>\n\n"

        "ℹ️ <b>ИНФО</b>\n"
        "• <code>цены</code> — цены продажи\n"
        "• <code>команды</code> — это меню\n\n"

        "👑 <b>АДМИНКА (для @lytixx)</b>\n"
        "• <code>админ выдать @user 1000</code> — выдать монеты\n"
        "• <code>админ топ</code> — статистика бота\n"
        "• <code>админ слот @user 5</code> — выдать слоты\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "💎 <b>ТОПОВЫЕ НИКИ (только крафт):</b>\n"
        "💎 @durov / @lytixx — 99 000 000 🪙\n"
        "🔴 @developer — 50 000 000 🪙\n"
        "🔴 @telegram — 25 000 000 🪙\n"
        "🔴 @botfather — 20 000 000 🪙\n"
        "🔴 @tgpremium — 15 000 000 🪙\n"
        "🟣 @tme — 10 000 000 🪙\n"
        "🟣 @tgs — 5 000 000 🪙"
    )

# ==================== ХЕНДЛЕРЫ ====================
@bot.message_handler(commands=["start"])
def start(m):
    register(m.from_user.id, m.from_user.username)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📋 Команды", callback_data="show_commands"))
    bot.reply_to(m, "👋 Привет!\nНажми «Команды» или напиши <code>команды</code>.", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "show_commands")
def cb_commands(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, commands_text(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("inv:"))
def cb_inv(call):
    parts = call.data.split(":")
    if parts[1] == "noop":
        return bot.answer_callback_query(call.id)
    owner_id = int(parts[1]); typ = parts[2]; page = int(parts[3])
    if call.from_user.id != owner_id:
        return bot.answer_callback_query(call.id, "❌ Это не твой инвентарь", show_alert=True)
    txt, page, pages = build_inv_page(owner_id, typ, page)
    kb = inv_keyboard(owner_id, typ, page, pages)
    try:
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "команды")
def commands(m):
    bot.reply_to(m, commands_text(), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "цены")
def prices(m):
    txt = ("💸 <b>Цены</b>\n\n"
           "Взятие: <b>бесплатно</b>\n\n"
           "Продажа барыге:\n"
           "⚪ обычный — 100 🪙\n"
           "🔵 редкий — 500 🪙\n"
           "🟣 эпический — 2 000 🪙\n"
           "🟡 легендарный — 10 000 🪙\n"
           "🔴 мифический — 50 000 🪙\n\n"
           "💎 <b>Топовые (только крафт):</b>\n"
           "@tgs — 5 млн\n@tme — 10 млн\n@tgpremium — 15 млн\n"
           "@botfather — 20 млн\n@telegram — 25 млн\n@developer — 50 млн\n"
           "@durov / @lytixx — 99 млн")
    bot.reply_to(m, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower() in ("бонус", "ежедневно", "daily"))
def daily(m):
    register(m.from_user.id, m.from_user.username)
    cur.execute("SELECT last_claim FROM daily WHERE tg_id=?", (m.from_user.id,))
    r = cur.fetchone()
    now = int(time.time())
    if r and now - r[0] < 86400:
        left = 86400 - (now - r[0]); h, rem = divmod(left, 3600)
        return bot.reply_to(m, f"⏳ Следующий бонус через <b>{h}ч {rem//60}м</b>", parse_mode="HTML")
    reward = random.randint(50, 200)
    add_coins(m.from_user.id, reward)
    cur.execute("INSERT OR REPLACE INTO daily(tg_id,last_claim) VALUES(?,?)", (m.from_user.id, now))
    conn.commit()
    bot.reply_to(m, f"🎁 Ты получил <b>{reward}</b> 🪙!\n💰 Баланс: {get_coins(m.from_user.id):,}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("взять"))
def take(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "взять @user")
    u = norm(p[1])
    if not re.fullmatch(r"@[a-z0-9_]{3,32}", u): return bot.reply_to(m, "Плохой юз")
    if u in CRAFT_TARGETS:
        return bot.reply_to(m, f"❌ <b>{u}</b> нельзя взять напрямую. Только через <code>крафт</code>.", parse_mode="HTML")
    if owner(u): return bot.reply_to(m, "Занят")
    lim = slots_limit(m.from_user.id, "user")
    if count_items(m.from_user.id, "user") >= lim:
        return bot.reply_to(m, f"❌ Лимит: {lim}. Расширь: <code>слот купить юзы</code>", parse_mode="HTML")
    rar = rarity_user(u); price = price_of(u, rar)
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, u, "user", rar, price)); conn.commit()
    if not has(m.from_user.id, "first"): grant(m.from_user.id, "first")
    if rar == "мега" and not has(m.from_user.id, "mega"): grant(m.from_user.id, "mega")
    final = f"✅ <b>{u}</b> твой!\n{RARITIES[rar]['emoji']} <b>{rar}</b> — продать: {price:,} 🪙"
    drop_animation(m.chat.id, m.message_id, final, rar)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("номер"))
def take_number(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "номер +77777777777")
    num = norm_num(p[1])
    if not re.fullmatch(r"\+[0-9]{5,15}", num):
        return bot.reply_to(m, "Формат: <code>номер +77777777777</code>", parse_mode="HTML")
    if owner(num): return bot.reply_to(m, "Занят")
    lim = slots_limit(m.from_user.id, "number")
    if count_items(m.from_user.id, "number") >= lim:
        return bot.reply_to(m, f"❌ Лимит: {lim}. Расширь: <code>слот купить номера</code>", parse_mode="HTML")
    rar = rarity_number(num); price = RARITIES[rar]["price"]
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, num, "number", rar, price)); conn.commit()
    if not has(m.from_user.id, "number"): grant(m.from_user.id, "number")
    final = f"✅ <b>{num}</b> твой!\n{RARITIES[rar]['emoji']} <b>{rar}</b> — продать: {price:,} 🪙"
    drop_animation(m.chat.id, m.message_id, final, rar)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("крафт"))
def craft(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2:
        txt = "🛠 <b>Рецепты крафта</b>\n\n"
        for target, r in RECIPES.items():
            txt += f"<b>{target}</b> ({RARITIES[r['target_rarity']]['emoji']} {r['target_rarity']}, шанс {int(r['success']*100)}%)\n"
            if r["fixed"]:
                txt += f"  • обязательно: {', '.join(r['fixed'])}\n"
            txt += f"  • +{r['random_count']} любых ({r['min_rarity']}+)\n\n"
        txt += "Пиши: <code>крафт @durov</code>"
        return bot.reply_to(m, txt, parse_mode="HTML")

    target = norm(p[1])
    recipe = RECIPES.get(target)
    if not recipe:
        return bot.reply_to(m, "❌ Такого рецепта нет. <code>крафт</code> — список.", parse_mode="HTML")
    if owner(target) == m.from_user.id:
        return bot.reply_to(m, "У тебя уже есть этот ник")
    if owner(target):
        return bot.reply_to(m, "❌ Этот ник уже занят")

    for f in recipe["fixed"]:
        cur.execute("SELECT 1 FROM inventory WHERE tg_id=? AND item=?", (m.from_user.id, f))
        if not cur.fetchone():
            return bot.reply_to(m, f"❌ Нет компонента: <b>{f}</b>", parse_mode="HTML")

    excludes = set(recipe["fixed"]) | CRAFT_TARGETS
    rand = get_random_rich(m.from_user.id, recipe["min_rarity"], excludes, recipe["random_count"])
    if rand is None:
        return bot.reply_to(m, f"❌ Нужно {recipe['random_count']} доп. юзов редкости <b>{recipe['min_rarity']}+</b>", parse_mode="HTML")

    all_components = recipe["fixed"] + rand
    for c in all_components:
        cur.execute("DELETE FROM inventory WHERE item=?", (c,))
        clear_eq(m.from_user.id, c)
    conn.commit()

    if not has(m.from_user.id, "crafter"): grant(m.from_user.id, "crafter")
    success = random.random() < recipe["success"]
    chance_pct = int(recipe["success"] * 100)

    if success:
        rar = recipe["target_rarity"]
        price = price_of(target, rar)
        cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                    (m.from_user.id, target, "user", rar, price))
        conn.commit()
        if rar == "мега" and not has(m.from_user.id, "mega"): grant(m.from_user.id, "mega")
        final = (f"✨ <b>УСПЕХ!</b> ✨\n\n"
                 f"{RARITIES[rar]['emoji']} <b>{rar}</b>\n"
                 f"<b>{target}</b>\n"
                 f"💰 Цена: {price:,} 🪙\n"
                 f"🎲 Шанс был: {chance_pct}%")
        drop_animation(m.chat.id, m.message_id, final, rar)
    else:
        bot.reply_to(m,
            f"💀 <b>ПРОВАЛ</b> 💀\n\n"
            f"Крафт <b>{target}</b> провалился (шанс был {chance_pct}%)\n"
            f"🔥 Сгорело: {', '.join(all_components)}",
            parse_mode="HTML")

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
    register(m.from_user.id, m.from_user.username)
    txt, page, pages = build_inv_page(m.from_user.id, "user", 0)
    kb = inv_keyboard(m.from_user.id, "user", page, pages)
    bot.reply_to(m, txt, parse_mode="HTML", reply_markup=kb)

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
        return bot.reply_to(m, f"💰 Продано {len(items)} шт. за <b>{total:,}</b> 🪙\n💰 Баланс: {get_coins(m.from_user.id):,}", parse_mode="HTML")

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
        msg = f"💰 Продано {sold} за <b>{total:,}</b> 🪙"
        if skip: msg += f"\n❌ Не найдено: {', '.join(skip)}"
        return bot.reply_to(m, msg, parse_mode="HTML")

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
    bot.reply_to(m, f"💰 Продал {item} ({rar}) за <b>{price:,}</b> 🪙\n💰 Баланс: {get_coins(m.from_user.id):,}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "баланс")
def balance(m):
    bot.reply_to(m, f"💰 <b>{get_coins(m.from_user.id):,}</b> 🪙", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "топ")
def top(m):
    cur.execute("SELECT tg_id, coins FROM balances ORDER BY coins DESC LIMIT 10")
    rows = cur.fetchall()
    if not rows: return bot.reply_to(m, "Пусто")
    txt = "🏆 <b>Топ богачей</b>\n\n"
    for i, (tid, coins) in enumerate(rows, 1):
        txt += f"{i}. {display_name(tid)} — {coins:,} 🪙\n"
    bot.reply_to(m, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "ачивки")
def ach(m):
    cur.execute("SELECT code FROM achievements WHERE tg_id=?", (m.from_user.id,))
    codes = [r[0] for r in cur.fetchall()]
    if not codes: return bot.reply_to(m, "Пока пусто. Собери первый ник: <code>взять @user</code>", parse_mode="HTML")
    txt = "🏅 <b>Твои ачивки</b>\n\n"
    for c in codes:
        a = ACHIEVEMENTS.get(c)
        if a: txt += f"{a['emoji']} {a['name']}\n"
    bot.reply_to(m, txt, parse_mode="HTML")

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
    admin_mark = " 👑" if is_admin(target_id, username_of(target_id)) else ""

    txt = (
        "╔════════════════════╗\n"
        "║    👤 <b>Профиль</b>\n"
        "╚════════════════════╝\n"
        f"🔗 <b>Telegram:</b> {display_name(target_id)}{admin_mark}\n"
        f"💰 <b>Монеты:</b> {coins:,} 🪙\n"
        f"⭐ <b>Лучший ник:</b> {bu or '—'}\n"
        f"📱 <b>Лучший номер:</b> {bn or '—'}\n"
        f"🏅 <b>Ачивок:</b> {len(ach_codes)}/{len(ACHIEVEMENTS)}\n\n"
        f"👤 <b>Ники</b> ({len(users)}/{slots_limit(target_id,'user')}):\n"
    )
    for i, r, pr in users[:10]:
        txt += f"{RARITIES[r]['emoji']} {i} — {r} ({pr:,} 🪙){' ⭐' if i==bu else ''}\n"
    if len(users) > 10: txt += f"… и ещё {len(users)-10}\n"
    txt += f"\n📱 <b>Номера</b> ({len(numbers)}/{slots_limit(target_id,'number')}):\n"
    for i, r, pr in numbers[:10]:
        txt += f"{RARITIES[r]['emoji']} {i} — {r} ({pr:,} 🪙){' ⭐' if i==bn else ''}\n"
    if len(numbers) > 10: txt += f"… и ещё {len(numbers)-10}\n"
    if ach_codes:
        txt += "\n🏅 <b>Ачивки:</b> "
        txt += " ".join(ACHIEVEMENTS[c]["emoji"] for c in ach_codes if c in ACHIEVEMENTS)
    bot.reply_to(m, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("слот"))
def slot_cmd(m):
    text = m.text.lower().strip()
    if text in ("слот", "слоты"):
        uc = slot_cost(m.from_user.id, "user"); nc = slot_cost(m.from_user.id, "number")
        return bot.reply_to(m,
            f"📦 <b>Слоты</b>\n\n"
            f"👤 Ники: {count_items(m.from_user.id,'user')}/{slots_limit(m.from_user.id,'user')}\n"
            f"• <code>слот купить юзы</code> — {uc:,} 🪙\n\n"
            f"📱 Номера: {count_items(m.from_user.id,'number')}/{slots_limit(m.from_user.id,'number')}\n"
            f"• <code>слот купить номера</code> — {nc:,} 🪙", parse_mode="HTML")
    if text == "слот купить юзы":
        cost = slot_cost(m.from_user.id, "user")
        if get_coins(m.from_user.id) < cost: return bot.reply_to(m, f"❌ Нужно {cost:,} 🪙")
        add_coins(m.from_user.id, -cost)
        ub, nb = get_bought(m.from_user.id)
        cur.execute("UPDATE slots SET ub=? WHERE tg_id=?", (ub+1, m.from_user.id)); conn.commit()
        return bot.reply_to(m, f"✅ +5 слотов. Лимит: {slots_limit(m.from_user.id,'user')}")
    if text == "слот купить номера":
        cost = slot_cost(m.from_user.id, "number")
        if get_coins(m.from_user.id) < cost: return bot.reply_to(m, f"❌ Нужно {cost:,} 🪙")
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
    txt = "🏦 <b>Биржа</b>\n\n"
    for lid, seller, item, rar, price in rows:
        txt += f"<code>#{lid}</code> {RARITIES[rar]['emoji']} {item} — <b>{price:,}</b> 🪙 (от {display_name(seller)})\n"
    txt += "\nКупить: <code>купить &lt;id&gt;</code>\nСнять: <code>снять &lt;id&gt;</code>"
    bot.reply_to(m, txt, parse_mode="HTML")

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
    bot.reply_to(m, f"✅ {item} выставлен за {price:,} 🪙")

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
    if get_coins(m.from_user.id) < price: return bot.reply_to(m, f"❌ Нужно {price:,} 🪙")
    if count_items(m.from_user.id, typ) >= slots_limit(m.from_user.id, typ):
        return bot.reply_to(m, "❌ Нет места. Расширь: <code>слот</code>", parse_mode="HTML")
    add_coins(m.from_user.id, -price); add_coins(seller, price)
    cur.execute("DELETE FROM listings WHERE id=?", (lid,))
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, item, typ, rar, price)); conn.commit()
    if not has(m.from_user.id, "trader"): grant(m.from_user.id, "trader")
    check_rich(seller)
    bot.reply_to(m, f"✅ Купил {item} за {price:,} 🪙")

# ==================== АДМИНКА (по Telegram-нику) ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("админ выдать"))
def admin_give(m):
    if not is_admin(m.from_user.id, m.from_user.username):
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
    bot.reply_to(m, f"✅ Выдано {amount:,} 🪙 → {display_name(tid)}")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "админ топ")
def admin_top(m):
    if not is_admin(m.from_user.id, m.from_user.username): return
    cur.execute("SELECT COUNT(*) FROM users"); u = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM inventory"); i = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM listings"); l = cur.fetchone()[0]
    cur.execute("SELECT SUM(coins) FROM balances"); c = cur.fetchone()[0] or 0
    bot.reply_to(m, f"📊 <b>Стата</b>\n👥 Игроков: {u}\n🎒 Предметов: {i}\n🏦 Лотов: {l}\n💰 Монет в системе: {c:,}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("админ слот"))
def admin_slot(m):
    if not is_admin(m.from_user.id, m.from_user.username):
        return bot.reply_to(m, "❌ Нет прав")
    p = m.text.split()
    if len(p) < 4: return bot.reply_to(m, "админ слот @user 5")
    target_str, count_s = p[2], p[3]
    try: count = int(count_s)
    except: return bot.reply_to(m, "Число")
    if target_str.startswith("@"):
        tid = by_uname(target_str)
    else:
        try: tid = int(target_str)
        except: return bot.reply_to(m, "Плохой ID")
    if not tid: return bot.reply_to(m, "Не найден")
    ub, nb = get_bought(tid)
    cur.execute("INSERT OR REPLACE INTO slots(tg_id,ub,nb) VALUES(?,?,?)", (tid, ub+count, nb+count))
    conn.commit()
    bot.reply_to(m, f"✅ Выдано +{count} к каждому лимиту → {display_name(tid)}")

# ВАЖНО: последним
@bot.message_handler(func=lambda m: m.text and m.from_user.username)
def track(m):
    register(m.from_user.id, m.from_user.username)
print("Бот запущен...")
bot.infinity_polling(timeout=60, long_polling_timeout=60)