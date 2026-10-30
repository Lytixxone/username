import sqlite3, re, random, time, telebot
from collections import Counter
from telebot import types

# ==================== ТОКЕН ====================
TOKEN_PART1 = "8650713388:"
TOKEN_PART2 = "AAFbY_4Drg29xAJSYwi1qu7C3x_0q7C3tEY"
bot = telebot.TeleBot(TOKEN_PART1 + TOKEN_PART2)

ADMIN_USERNAMES = {"lytixx"}
ADMIN_IDS = set()

# ==================== БАЗА ====================
conn = sqlite3.connect("usernames.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(tg_id INTEGER PRIMARY KEY, username TEXT)")
cur.execute("""CREATE TABLE IF NOT EXISTS inventory(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER, item TEXT UNIQUE, type TEXT, rarity TEXT, price INTEGER)""")
cur.execute("CREATE TABLE IF NOT EXISTS balances(tg_id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS equipped(tg_id INTEGER PRIMARY KEY, best_user TEXT, best_number TEXT, best_nft TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS slots(tg_id INTEGER PRIMARY KEY, ub INTEGER DEFAULT 0, nb INTEGER DEFAULT 0, nbft INTEGER DEFAULT 0)")
cur.execute("""CREATE TABLE IF NOT EXISTS listings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER, item TEXT, type TEXT, rarity TEXT, price INTEGER, currency TEXT DEFAULT 'coins')""")
cur.execute("CREATE TABLE IF NOT EXISTS daily(tg_id INTEGER PRIMARY KEY, last_claim INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS achievements(tg_id INTEGER, code TEXT, PRIMARY KEY(tg_id, code))")
cur.execute("CREATE TABLE IF NOT EXISTS stars(tg_id INTEGER PRIMARY KEY, amount INTEGER DEFAULT 0)")
conn.commit()

# Миграция: добавляем best_nft и nbft если нет
try: cur.execute("ALTER TABLE equipped ADD COLUMN best_nft TEXT")
except: pass
try: cur.execute("ALTER TABLE slots ADD COLUMN nbft INTEGER DEFAULT 0")
except: pass
try: cur.execute("ALTER TABLE listings ADD COLUMN currency TEXT DEFAULT 'coins'")
except: pass
conn.commit()

# ==================== РЕДКОСТИ ====================
RARITIES = {
    "обычный":     {"emoji": "⚪", "price": 100,      "stars": 0},
    "редкий":      {"emoji": "🔵", "price": 500,      "stars": 0},
    "эпический":   {"emoji": "🟣", "price": 2000,     "stars": 1},
    "легендарный": {"emoji": "🟡", "price": 10000,    "stars": 3},
    "мифический":  {"emoji": "🔴", "price": 50000,    "stars": 5},
    "мега":        {"emoji": "💎", "price": 99000000, "stars": 10},
}

SPECIAL_RARITIES = {
    "@durov": "мега", "@lytixx": "мега",
    "@developer": "мифический", "@telegram": "мифический",
    "@botfather": "мифический", "@tgpremium": "мифический",
    "@melstroy": "мифический", "@musk": "мифический",
    "@trump": "мифический", "@putin": "мифический",
    "@tmex": "эпический", "@tgsx": "эпический",
    "@tgl": "эпический", "@botx": "эпический", "@webx": "эпический",
    "@mebx": "редкий", "@setx": "редкий", "@father": "редкий", "@premium": "редкий",
}

SPECIAL_PRICES = {
    "@durov":99000000,"@lytixx":99000000,"@developer":50000000,
    "@melstroy":40000000,"@putin":30000000,"@musk":25000000,"@telegram":25000000,
    "@trump":20000000,"@botfather":20000000,"@tgpremium":15000000,
    "@tmex":10000000,"@tgsx":5000000,"@tgl":2000000,"@botx":2000000,"@webx":2000000,
    "@mebx":500000,"@setx":500000,"@father":500000,"@premium":500000,
}

CRAFT_TARGETS = ["@durov","@lytixx","@developer","@telegram","@botfather","@tgpremium",
                 "@tmex","@tgsx","@melstroy","@musk","@trump","@putin"]

RECIPES = {
    "@tmex":      {"rarity":"эпический",  "fixed":["@mebx","@setx"],    "rand":2, "min":"обычный",    "chance":0.9},
    "@tgsx":      {"rarity":"эпический",  "fixed":["@tgl","@father"],   "rand":2, "min":"обычный",    "chance":0.9},
    "@telegram":  {"rarity":"мифический", "fixed":["@tmex","@webx"],    "rand":3, "min":"эпический",  "chance":0.6},
    "@botfather": {"rarity":"мифический", "fixed":["@botx","@father"],  "rand":3, "min":"редкий",     "chance":0.7},
    "@developer": {"rarity":"мифический", "fixed":["@tgl","@botx"],     "rand":5, "min":"легендарный","chance":0.5},
    "@tgpremium": {"rarity":"мифический", "fixed":["@tgsx","@premium"], "rand":5, "min":"эпический",  "chance":0.55},
    "@melstroy":  {"rarity":"мифический", "fixed":["@crow","@free"],    "rand":5, "min":"эпический",  "chance":0.55},
    "@musk":      {"rarity":"мифический", "fixed":["@tgl","@webx"],     "rand":5, "min":"эпический",  "chance":0.55},
    "@trump":     {"rarity":"мифический", "fixed":["@botx","@father"],  "rand":6, "min":"легендарный","chance":0.5},
    "@putin":     {"rarity":"мифический", "fixed":["@melstroy","@trump"],"rand":8,"min":"легендарный","chance":0.45},
    "@durov":     {"rarity":"мега",       "fixed":["@crow","@free"],    "rand":7, "min":"эпический",  "chance":0.5},
    "@lytixx":    {"rarity":"мега",       "fixed":[],                   "rand":10,"min":"эпический",  "chance":0.5},
}

# ==================== NFT ====================
# Формат: t.me/nft/IceCream-123
NFT_TYPES = {
    "IceCream": {
        "emoji": "🍦", "name": "IceCream",
        "prices": {1:10000, 2:5000, 3:2000, 4:1000},  # по числу цифр
        "max": 999999,
        "default": 500,
    },
    "MirageLamp": {
        "emoji": "🪔", "name": "MirageLamp",
        "prices": {1:20000, 2:10000, 3:4000, 4:2000},
        "max": 999999,
        "default": 800,
    },
    "SnoopDogg": {
        "emoji": "🐶", "name": "SnoopDogg",
        "prices": {1:100000, 2:50000, 3:20000, 4:10000, 5:5000, 6:2000},
        "max": 9999999,
        "default": 1000,
    },
    "PlushPepe": {
        "emoji": "🐸", "name": "PlushPepe",
        "prices": {1:10000000, 2:5000000, 3:2000000, 4:1000000},
        "max": 3000,
        "default": 1000000,
    },
}

def nft_rarity(price):
    if price >= 1000000: return "мега"
    if price >= 100000: return "мифический"
    if price >= 20000: return "легендарный"
    if price >= 5000: return "эпический"
    if price >= 1000: return "редкий"
    return "обычный"

def nft_price(nft_type, num):
    t = NFT_TYPES[nft_type]
    digits = len(str(num))
    return t["prices"].get(digits, t["default"])

def parse_nft(text):
    """Парсит 'IceCream-123', 't.me/nft/IceCream-123', 'https://t.me/nft/IceCream-123'"""
    text = text.strip()
    m = re.search(r"(?:t\.me/nft/)?(IceCream|MirageLamp|SnoopDogg|PlushPepe)-(\d+)", text, re.IGNORECASE)
    if not m: return None
    # Нормализуем регистр типа
    typ_map = {"icecream":"IceCream","miragelamp":"MirageLamp","snoopdogg":"SnoopDogg","plushpepe":"PlushPepe"}
    nft_type = typ_map[m.group(1).lower()]
    num = int(m.group(2))
    if num <= 0 or num > NFT_TYPES[nft_type]["max"]:
        return {"error": f"Число должно быть от 1 до {NFT_TYPES[nft_type]['max']}"}
    item = f"t.me/nft/{nft_type}-{num}"
    return {"type": nft_type, "num": num, "item": item, "price": nft_price(nft_type, num)}

ACHIEVEMENTS = {
    "first":   {"emoji": "🥉", "name": "Первый ник"},
    "ten":     {"emoji": "🎯", "name": "10 ников"},
    "fifty":   {"emoji": "💯", "name": "50 ников"},
    "seller":  {"emoji": "💰", "name": "Продавец"},
    "crafter": {"emoji": "🛠", "name": "Крафтер"},
    "rich":    {"emoji": "💵", "name": "Богач"},
    "million": {"emoji": "🏆", "name": "Миллионер"},
    "mega":    {"emoji": "💎", "name": "Мега-ник"},
    "myph":    {"emoji": "🔴", "name": "Мифический"},
    "nft1":    {"emoji": "🖼", "name": "Первый NFT"},
    "nft10":   {"emoji": "🎨", "name": "10 NFT"},
    "nft_mega":{"emoji": "🐸", "name": "PlushPepe"},
}

# ==================== АДМИНКА ====================
def is_admin(tg_id=None, username=None):
    if username and username.lower().lstrip("@") in ADMIN_USERNAMES: return True
    if tg_id and tg_id in ADMIN_IDS: return True
    return False

# ==================== УТИЛИТЫ ====================
def norm(u):
    u = u.strip().lower()
    return u if u.startswith("@") else "@" + u

def norm_num(s):
    s = re.sub(r"[\s\-()]", "", s.strip())
    if not s.startswith("+"): s = "+" + s
    return s

def rarity_user(u):
    if u in SPECIAL_RARITIES: return SPECIAL_RARITIES[u]
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

def price_of(item, rar): return SPECIAL_PRICES.get(item, RARITIES[rar]["price"])

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

def get_stars(tg_id):
    cur.execute("SELECT amount FROM stars WHERE tg_id=?", (tg_id,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO stars(tg_id,amount) VALUES(?,0)", (tg_id,)); conn.commit(); return 0
    return r[0]

def add_stars(tg_id, n):
    cur.execute("INSERT OR IGNORE INTO stars(tg_id,amount) VALUES(?,0)", (tg_id,))
    cur.execute("UPDATE stars SET amount = amount + ? WHERE tg_id=?", (n, tg_id))
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
    cur.execute("SELECT ub, nb, nbft FROM slots WHERE tg_id=?", (tg_id,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO slots(tg_id,ub,nb,nbft) VALUES(?,0,0,0)", (tg_id,)); conn.commit(); return 0,0,0
    return r

def slots_limit(tg_id, typ):
    ub, nb, nbft = get_bought(tg_id)
    if typ == "user": return 5 + 5*ub
    if typ == "number": return 5 + 5*nb
    return 3 + 3*nbft

def slot_cost(tg_id, typ):
    ub, nb, nbft = get_bought(tg_id)
    if typ == "user": return 100*(ub+1)
    if typ == "number": return 100*(nb+1)
    return 500*(nbft+1)

def get_equipped(tg_id):
    cur.execute("SELECT best_user, best_number, best_nft FROM equipped WHERE tg_id=?", (tg_id,))
    r = cur.fetchone()
    return r if r else (None, None, None)

def set_eq(tg_id, user=None, number=None, nft=None):
    bu, bn, bf = get_equipped(tg_id)
    cur.execute("INSERT OR REPLACE INTO equipped(tg_id,best_user,best_number,best_nft) VALUES(?,?,?,?)",
                (tg_id, user if user is not None else bu, number if number is not None else bn, nft if nft is not None else bf))
    conn.commit()

def clear_eq(tg_id, item):
    cur.execute("UPDATE equipped SET best_user=CASE WHEN best_user=? THEN NULL ELSE best_user END WHERE tg_id=?", (item, tg_id))
    cur.execute("UPDATE equipped SET best_number=CASE WHEN best_number=? THEN NULL ELSE best_number END WHERE tg_id=?", (item, tg_id))
    cur.execute("UPDATE equipped SET best_nft=CASE WHEN best_nft=? THEN NULL ELSE best_nft END WHERE tg_id=?", (item, tg_id))
    conn.commit()

def username_of(tg_id):
    cur.execute("SELECT username FROM users WHERE tg_id=?", (tg_id,))
    r = cur.fetchone()
    return r[0] if r else None

def display_name(tg_id):
    u = username_of(tg_id)
    if not u: return f"ID {tg_id}"
    if u.lower().lstrip("@") in ADMIN_USERNAMES: return f"✅ {u}"
    return u

def parse_item(arg):
    if arg.startswith("+"): return norm_num(arg), "number"
    if re.fullmatch(r"\d{5,15}", arg): return norm_num(arg), "number"
    if "nft" in arg.lower() or any(t in arg for t in ["IceCream","MirageLamp","SnoopDogg","PlushPepe"]):
        nft = parse_nft(arg)
        if nft and "error" not in nft:
            return nft["item"], "nft"
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
    if get_coins(tg_id) >= 10000 and not has(tg_id, "rich"): grant(tg_id, "rich")
    if get_coins(tg_id) >= 1000000 and not has(tg_id, "million"): grant(tg_id, "million")

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
        try: bot.edit_message_text(text, chat_id, msg.message_id)
        except: pass
    time.sleep(0.3)
    try: bot.edit_message_text(final_text, chat_id, msg.message_id, parse_mode="HTML")
    except: bot.send_message(chat_id, final_text, parse_mode="HTML")

# ==================== ИНВЕНТАРЬ (просмотр с пагинацией) ====================
INV_PAGE_SIZE = 8

def build_inv_page(tg_id, typ, page):
    items = get_inv(tg_id, typ)
    total = len(items)
    pages = max(1, (total + INV_PAGE_SIZE - 1) // INV_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    start = page * INV_PAGE_SIZE
    chunk = items[start:start + INV_PAGE_SIZE]

    titles = {"user": "👤 Ники", "number": "📱 Номера", "nft": "🖼 NFT"}
    title = titles.get(typ, "Инвентарь")
    limit = slots_limit(tg_id, typ)
    txt = f"<b>{title}</b> ({total}/{limit}) — стр. {page+1}/{pages}\n\n"
    if not chunk:
        txt += "пусто"
    else:
        for it, rar, price in chunk:
            if typ == "nft":
                txt += f"{RARITIES[rar]['emoji']} {it} — {rar} ({price:,} ⭐)\n"
            else:
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
    other = {"user":"number", "number":"nft", "nft":"user"}[typ]
    other_name = {"user":"👤 Ники", "number":"📱 Номера", "nft":"🖼 NFT"}[other]
    kb.row(types.InlineKeyboardButton(other_name, callback_data=f"inv:{owner_id}:{other}:0"))
    return kb

# ==================== МЕНЮ (7 страниц) ====================
MENU_PAGES = [
    {"title": "🎒 КОЛЛЕКЦИЯ", "lines": [
        "• <code>взять @user</code> — забрать ник",
        "• <code>номер +7777...</code> — забрать номер",
        "• <code>инвентарь</code> — листать коллекцию",
        "• <code>поставить @user</code> — лучший ник",
        "• <code>поставить +7777</code> — лучший номер",
        "• <code>дать @user</code> — передать (ответом)",
        "",
        "<b>Звёзды за продажу:</b>",
        "🔴 мифический → +5 ⭐",
        "🟡 легендарный → +3 ⭐",
        "🟣 эпический → +1 ⭐",
    ]},
    {"title": "🖼 NFT", "lines": [
        "• <code>нфт IceCream-123</code> — взять NFT",
        "• <code>нфт t.me/nft/SnoopDogg-99</code> — тоже",
        "• <code>инвентарь</code> → вкладка NFT",
        "",
        "<b>Каталог NFT (цена в ⭐):</b>",
        "🍦 IceCream-N — 500–10 000 ⭐",
        "🪔 MirageLamp-N — 800–20 000 ⭐",
        "🐶 SnoopDogg-N — 1 000–100 000 ⭐",
        "🐸 PlushPepe-N (до 3000) — 1 млн–10 млн ⭐",
        "",
        "💡 Чем короче число — тем дороже",
    ]},
    {"title": "⭐ ЗВЁЗДЫ", "lines": [
        "• <code>мои звёзды</code> — баланс",
        "• <code>купить звёзды 10</code> — 100k 🪙 за 1 ⭐",
        "• <code>обменять звёзды 10</code> — 80k 🪙 за 1 ⭐",
        "• Звёзды даются за продажу редких",
        "• За NFT платишь звёздами",
    ]},
    {"title": "🛠 КРАФТ", "lines": [
        "• <code>крафт</code> — рецепты",
        "• <code>крафт @durov</code> — крафтить",
        "• Шанс 45–90%, при провале сгорает",
        "",
        "<b>Топ-ники:</b>",
        "💎 @durov / @lytixx — 99 млн",
        "🔴 @developer — 50 млн",
        "🔴 @melstroy — 40 млн",
        "🔴 @putin — 30 млн",
        "🔴 @musk / @telegram — 25 млн",
    ]},
    {"title": "💰 ПРОДАЖА", "lines": [
        "• <code>продать @user</code> / <code>продать +7777</code>",
        "• <code>продать несколько @a +7...</code>",
        "• <code>продать всё</code>",
        "",
        "🏦 <b>БИРЖА:</b>",
        "• <code>биржа</code> — лоты",
        "• <code>выставить @user 500</code>",
        "• <code>снять <id></code> / <code>купить <id></code>",
    ]},
    {"title": "📦 ЭКОНОМИКА", "lines": [
        "• <code>бонус</code> — ежедневно 50–200 🪙",
        "• <code>баланс</code> — монеты и звёзды",
        "• <code>топ</code> — топ богачей",
        "• <code>слот</code> — инфо слотов",
        "• <code>слот купить юзы</code> — +5 ников",
        "• <code>слот купить номера</code> — +5 номеров",
        "• <code>слот купить нфт</code> — +3 NFT",
    ]},
    {"title": "👑 АДМИНКА (@lytixx)", "lines": [
        "• <code>админ выдать @user 1000</code> — монеты",
        "• <code>админ звезда @user 10</code> — звёзды",
        "• <code>админ слот @user 5</code> — слоты",
        "• <code>админ топ</code> — статистика",
    ]},
]

def build_menu(page=0):
    page = max(0, min(page, len(MENU_PAGES) - 1))
    p = MENU_PAGES[page]
    text = f"📋 <b>Меню</b> — {page+1}/{len(MENU_PAGES)}\n\n<b>{p['title']}</b>\n" + "\n".join(p["lines"])
    kb = types.InlineKeyboardMarkup()
    row = []
    if page > 0:
        row.append(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"menu:{page-1}"))
    row.append(types.InlineKeyboardButton(f"{page+1}/{len(MENU_PAGES)}", callback_data="menu:noop"))
    if page < len(MENU_PAGES) - 1:
        row.append(types.InlineKeyboardButton("Далее ➡️", callback_data=f"menu:{page+1}"))
    kb.row(*row)
    return text, kb

# ==================== КРАФТ-ХЕЛПЕР ====================
def get_random_rich(tg_id, min_rarity, exclude, count):
    order = ["обычный","редкий","эпический","легендарный","мифический","мега"]
    min_idx = order.index(min_rarity)
    allowed = set(order[min_idx:])
    cur.execute("SELECT item, rarity FROM inventory WHERE tg_id=? AND type='user'", (tg_id,))
    candidates = [item for item, rar in cur.fetchall()
                  if rar in allowed and item not in exclude and item not in CRAFT_TARGETS]
    if len(candidates) < count: return None
    return random.sample(candidates, count)

# ==================== ХЕНДЛЕРЫ ====================
@bot.message_handler(commands=["start"])
def start(m):
    register(m.from_user.id, m.from_user.username)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📋 Меню команд", callback_data="menu:0"))
    bot.reply_to(m, "👋 Привет!\nНажми кнопку ниже или напиши <code>команды</code>.", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("menu:"))
def cb_menu(call):
    parts = call.data.split(":")
    if parts[1] == "noop": return bot.answer_callback_query(call.id)
    text, kb = build_menu(int(parts[1]))
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("inv:"))
def cb_inv(call):
    parts = call.data.split(":")
    if parts[1] == "noop": return bot.answer_callback_query(call.id)
    owner_id = int(parts[1]); typ = parts[2]; page = int(parts[3])
    if call.from_user.id != owner_id:
        return bot.answer_callback_query(call.id, "❌ Это не твой инвентарь", show_alert=True)
    txt, page, pages = build_inv_page(owner_id, typ, page)
    kb = inv_keyboard(owner_id, typ, page, pages)
    try: bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: m.text and m.text.lower() in ("команды", "меню"))
def commands(m):
    text, kb = build_menu(0)
    bot.reply_to(m, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "цены")
def prices(m):
    txt = ("💸 <b>Цены продажи</b>\n\n"
           "⚪ обычный — 100 🪙\n🔵 редкий — 500 🪙\n"
           "🟣 эпический — 2 000 🪙 (+1 ⭐)\n🟡 легендарный — 10 000 🪙 (+3 ⭐)\n"
           "🔴 мифический — 50 000 🪙 (+5 ⭐)\n💎 мега — 99 000 000 🪙 (+10 ⭐)\n\n"
           "🖼 <b>NFT (за ⭐):</b>\n"
           "🍦 IceCream-N — 500–10 000\n🪔 MirageLamp-N — 800–20 000\n"
           "🐶 SnoopDogg-N — 1 000–100 000\n🐸 PlushPepe-N — 1 млн–10 млн")
    bot.reply_to(m, txt, parse_mode="HTML")

# ==================== ЗВЁЗДЫ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower() in ("мои звёзды","звёзды","баланс звёзд","⭐"))
def my_stars(m):
    bot.reply_to(m, f"⭐ <b>Звёзды:</b> {get_stars(m.from_user.id)}\n💰 Монеты: {get_coins(m.from_user.id):,}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("купить звёзды"))
def buy_stars(m):
    p = m.text.split()
    if len(p) < 3: return bot.reply_to(m, "<code>купить звёзды 10</code> — 1 ⭐ = 100 000 🪙", parse_mode="HTML")
    try: n = int(p[2])
    except: return bot.reply_to(m, "Число")
    if n <= 0: return bot.reply_to(m, "> 0")
    cost = n * 100000
    if get_coins(m.from_user.id) < cost:
        return bot.reply_to(m, f"❌ Нужно {cost:,} 🪙 (у тебя {get_coins(m.from_user.id):,})", parse_mode="HTML")
    add_coins(m.from_user.id, -cost)
    add_stars(m.from_user.id, n)
    bot.reply_to(m, f"✅ Куплено {n} ⭐ за {cost:,} 🪙\n⭐ Баланс: {get_stars(m.from_user.id)}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("обменять звёзды"))
def exchange_stars(m):
    p = m.text.split()
    if len(p) < 3: return bot.reply_to(m, "<code>обменять звёзды 10</code> — 1 ⭐ = 80 000 🪙", parse_mode="HTML")
    try: n = int(p[2])
    except: return bot.reply_to(m, "Число")
    if n <= 0: return bot.reply_to(m, "> 0")
    if get_stars(m.from_user.id) < n:
        return bot.reply_to(m, f"❌ Мало звёзд (у тебя {get_stars(m.from_user.id)})", parse_mode="HTML")
    gain = n * 80000
    add_stars(m.from_user.id, -n)
    add_coins(m.from_user.id, gain)
    bot.reply_to(m, f"✅ {n} ⭐ → {gain:,} 🪙\n⭐ Осталось: {get_stars(m.from_user.id)}", parse_mode="HTML")

# ==================== NFT ====================
@bot.message_handler(func=lambda m: m.text and (m.text.lower().startswith("нфт ") or m.text.lower().startswith("nft ")))
def take_nft(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split(maxsplit=1)
    if len(p) < 2:
        return bot.reply_to(m, "<code>нфт IceCream-123</code>\n<code>нфт t.me/nft/SnoopDogg-99</code>", parse_mode="HTML")
    nft = parse_nft(p[1])
    if not nft:
        return bot.reply_to(m, "❌ Формат: <code>нфт IceCream-123</code>", parse_mode="HTML")
    if "error" in nft:
        return bot.reply_to(m, f"❌ {nft['error']}", parse_mode="HTML")
    item = nft["item"]
    if owner(item):
        return bot.reply_to(m, f"❌ <b>{item}</b> уже занят", parse_mode="HTML")
    lim = slots_limit(m.from_user.id, "nft")
    if count_items(m.from_user.id, "nft") >= lim:
        return bot.reply_to(m, f"❌ Лимит NFT: {lim}. <code>слот купить нфт</code>", parse_mode="HTML")
    price = nft["price"]
    if get_stars(m.from_user.id) < price:
        return bot.reply_to(m, f"❌ Нужно <b>{price:,} ⭐</b> (у тебя {get_stars(m.from_user.id)})", parse_mode="HTML")
    add_stars(m.from_user.id, -price)
    rar = nft_rarity(price)
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, item, "nft", rar, price)); conn.commit()
    if not has(m.from_user.id, "nft1"): grant(m.from_user.id, "nft1")
    if count_items(m.from_user.id, "nft") >= 10 and not has(m.from_user.id, "nft10"): grant(m.from_user.id, "nft10")
    if nft["type"] == "PlushPepe" and not has(m.from_user.id, "nft_mega"): grant(m.from_user.id, "nft_mega")
    drop_animation(m.chat.id, m.message_id,
        f"🖼 <b>NFT получен!</b>\n\n{RARITIES[rar]['emoji']} <b>{rar}</b>\n<b>{item}</b>\n💸 Заплачено: {price:,} ⭐\n⭐ Осталось: {get_stars(m.from_user.id)}",
        rar)

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "каталог нфт")
def nft_catalog(m):
    txt = "🖼 <b>Каталог NFT</b>\n\n"
    for name, t in NFT_TYPES.items():
        txt += f"{t['emoji']} <b>{name}</b> — до {t['max']:,}\n"
        for digits, price in t["prices"].items():
            txt += f"   {digits} цифр — {price:,} ⭐\n"
    txt += "\nПример: <code>нфт IceCream-7</code>"
    bot.reply_to(m, txt, parse_mode="HTML")

# ==================== ВЗЯТЬ / ДАТЬ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("взять"))
def take(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "взять @user")
    u = norm(p[1])
    if not re.fullmatch(r"@[a-z0-9_]{3,32}", u): return bot.reply_to(m, "Плохой юз (мин 3)")
    if u in CRAFT_TARGETS: return bot.reply_to(m, f"❌ <b>{u}</b> только через <code>крафт</code>", parse_mode="HTML")
    if owner(u): return bot.reply_to(m, "Занят")
    if count_items(m.from_user.id, "user") >= slots_limit(m.from_user.id, "user"):
        return bot.reply_to(m, "❌ Лимит. <code>слот купить юзы</code>", parse_mode="HTML")
    rar = rarity_user(u); price = price_of(u, rar)
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, u, "user", rar, price)); conn.commit()
    if not has(m.from_user.id, "first"): grant(m.from_user.id, "first")
    if rar == "мега" and not has(m.from_user.id, "mega"): grant(m.from_user.id, "mega")
    drop_animation(m.chat.id, m.message_id,
                   f"✅ <b>{u}</b> твой!\n{RARITIES[rar]['emoji']} <b>{rar}</b> — продать {price:,} 🪙", rar)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("номер"))
def take_number(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "номер +77777777777")
    num = norm_num(p[1])
    if not re.fullmatch(r"\+[0-9]{5,15}", num):
        return bot.reply_to(m, "Формат: <code>номер +77777777777</code>", parse_mode="HTML")
    if owner(num): return bot.reply_to(m, "Занят")
    if count_items(m.from_user.id, "number") >= slots_limit(m.from_user.id, "number"):
        return bot.reply_to(m, "❌ Лимит. <code>слот купить номера</code>", parse_mode="HTML")
    rar = rarity_number(num); price = RARITIES[rar]["price"]
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, num, "number", rar, price)); conn.commit()
    drop_animation(m.chat.id, m.message_id,
                   f"✅ <b>{num}</b> твой!\n{RARITIES[rar]['emoji']} <b>{rar}</b> — продать {price:,} 🪙", rar)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("дать"))
def give(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "дать @user / +7777 / NFT (ответом)")
    item, typ = parse_item(p[1])
    if owner(item) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого")
    if m.reply_to_message:
        target = m.reply_to_message.from_user.id
    elif typ == "user":
        target = by_uname(p[1])
    else:
        return bot.reply_to(m, "Только ответом на сообщение")
    if not target: return bot.reply_to(m, "Ответь на сообщение получателя")
    if count_items(target, typ) >= slots_limit(target, typ):
        return bot.reply_to(m, "У получателя нет места")
    cur.execute("UPDATE inventory SET tg_id=? WHERE item=?", (target, item)); conn.commit()
    bot.reply_to(m, f"➡️ {item} передан")

# ==================== КРАФТ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("крафт"))
def craft(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2:
        txt = "🛠 <b>Рецепты крафта</b>\n\n"
        for target, r in RECIPES.items():
            txt += f"<b>{target}</b> ({RARITIES[r['rarity']]['emoji']} {r['rarity']}, {int(r['chance']*100)}%)\n"
            if r["fixed"]: txt += f"  • нужно: {', '.join(r['fixed'])}\n"
            txt += f"  • +{r['rand']} любых ({r['min']}+)\n\n"
        txt += "Пиши: <code>крафт @durov</code>"
        return bot.reply_to(m, txt, parse_mode="HTML")
    target = norm(p[1])
    recipe = RECIPES.get(target)
    if not recipe: return bot.reply_to(m, "❌ Нет такого рецепта")
    if owner(target) == m.from_user.id: return bot.reply_to(m, "Уже есть")
    if owner(target): return bot.reply_to(m, "❌ Занят")
    for f in recipe["fixed"]:
        cur.execute("SELECT 1 FROM inventory WHERE tg_id=? AND item=?", (m.from_user.id, f))
        if not cur.fetchone(): return bot.reply_to(m, f"❌ Нет компонента: <b>{f}</b>", parse_mode="HTML")
    excludes = set(recipe["fixed"]) | set(CRAFT_TARGETS)
    rand = get_random_rich(m.from_user.id, recipe["min"], excludes, recipe["rand"])
    if rand is None:
        return bot.reply_to(m, f"❌ Нужно {recipe['rand']} юзов <b>{recipe['min']}+</b>", parse_mode="HTML")
    all_comp = recipe["fixed"] + rand
    for c in all_comp:
        cur.execute("DELETE FROM inventory WHERE item=?", (c,))
        clear_eq(m.from_user.id, c)
    conn.commit()
    if not has(m.from_user.id, "crafter"): grant(m.from_user.id, "crafter")
    success = random.random() < recipe["chance"]
    if success:
        rar = recipe["rarity"]; price = price_of(target, rar)
        cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                    (m.from_user.id, target, "user", rar, price)); conn.commit()
        if rar == "мега" and not has(m.from_user.id, "mega"): grant(m.from_user.id, "mega")
        if rar == "мифический" and not has(m.from_user.id, "myph"): grant(m.from_user.id, "myph")
        drop_animation(m.chat.id, m.message_id,
            f"✨ <b>УСПЕХ!</b>\n\n{RARITIES[rar]['emoji']} <b>{rar}</b>\n<b>{target}</b>\n💰 {price:,} 🪙", rar)
    else:
        bot.reply_to(m, f"💀 <b>ПРОВАЛ</b>\n🔥 Сгорело: {', '.join(all_comp)}", parse_mode="HTML")

# ==================== ПРОДАЖА ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("продать"))
def sell(m):
    text = m.text.lower()
    if text in ("продать всё", "продать все"):
        items = get_inv(m.from_user.id)
        if not items: return bot.reply_to(m, "Нечего продавать")
        coins_total = 0; stars_total = 0
        for it, rar, pr, typ in items:
            if typ == "nft":
                stars_total += int(pr * 0.8)
            else:
                coins_total += pr
                stars_total += RARITIES[rar]["stars"]
        cur.execute("DELETE FROM inventory WHERE tg_id=?", (m.from_user.id,))
        cur.execute("DELETE FROM equipped WHERE tg_id=?", (m.from_user.id,))
        add_coins(m.from_user.id, coins_total)
        add_stars(m.from_user.id, stars_total)
        conn.commit()
        if not has(m.from_user.id, "ten") and len(items) >= 10: grant(m.from_user.id, "ten")
        check_rich(m.from_user.id)
        return bot.reply_to(m, f"💰 +{coins_total:,} 🪙, ⭐ +{stars_total} за {len(items)} шт.", parse_mode="HTML")

    if text.startswith("продать несколько"):
        args = m.text.split()[2:]
        if not args: return bot.reply_to(m, "продать несколько @a @b +7...")
        coins_total = 0; stars_total = 0; sold = 0; skip = []
        for a in args:
            item, typ = parse_item(a)
            if owner(item) != m.from_user.id: skip.append(item); continue
            cur.execute("SELECT price, rarity FROM inventory WHERE item=?", (item,))
            pr, rar = cur.fetchone()
            cur.execute("DELETE FROM inventory WHERE item=?", (item,))
            clear_eq(m.from_user.id, item)
            if typ == "nft":
                stars_total += int(pr * 0.8)
            else:
                coins_total += pr
                stars_total += RARITIES[rar]["stars"]
            sold += 1
        add_coins(m.from_user.id, coins_total)
        add_stars(m.from_user.id, stars_total)
        conn.commit()
        check_rich(m.from_user.id)
        msg = f"💰 +{coins_total:,} 🪙, ⭐ +{stars_total} ({sold} шт.)"
        if skip: msg += f"\n❌ Не найдено: {', '.join(skip)}"
        return bot.reply_to(m, msg, parse_mode="HTML")

    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "продать @user / +7777 / NFT")
    item, typ = parse_item(p[1])
    if owner(item) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого")
    cur.execute("SELECT price, rarity FROM inventory WHERE item=?", (item,))
    price, rar = cur.fetchone()
    cur.execute("DELETE FROM inventory WHERE item=?", (item,))
    clear_eq(m.from_user.id, item)
    if typ == "nft":
        stars_gain = int(price * 0.8)
        add_stars(m.from_user.id, stars_gain)
        result = f"⭐ +{stars_gain} звёзд"
    else:
        add_coins(m.from_user.id, price)
        stars_gain = RARITIES[rar]["stars"]
        if stars_gain > 0: add_stars(m.from_user.id, stars_gain)
        result = f"💰 +{price:,} 🪙" + (f", ⭐ +{stars_gain}" if stars_gain > 0 else "")
    conn.commit()
    check_rich(m.from_user.id)
    bot.reply_to(m, f"✅ Продал {item} ({rar})\n{result}", parse_mode="HTML")

# ==================== БАЛАНС / ТОП / АЧИВКИ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "баланс")
def balance(m):
    bot.reply_to(m, f"💰 <b>{get_coins(m.from_user.id):,}</b> 🪙\n⭐ <b>{get_stars(m.from_user.id)}</b> звёзд", parse_mode="HTML")

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
    if not codes: return bot.reply_to(m, "Пока пусто")
    txt = "🏅 <b>Ачивки</b>\n\n"
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
        if not t: return bot.reply_to(m, "Не найден")
        target_id = t
    elif m.reply_to_message:
        target_id = m.reply_to_message.from_user.id
    coins = get_coins(target_id); stars = get_stars(target_id)
    bu, bn, bf = get_equipped(target_id)
    users = get_inv(target_id, "user"); numbers = get_inv(target_id, "number"); nfts = get_inv(target_id, "nft")
    admin_mark = " 👑" if is_admin(target_id, username_of(target_id)) else ""

    txt = (f"╔════════════════════╗\n║    👤 <b>Профиль</b>\n╚════════════════════╝\n"
           f"🔗 <b>Telegram:</b> {display_name(target_id)}{admin_mark}\n"
           f"💰 <b>Монеты:</b> {coins:,} 🪙\n⭐ <b>Звёзды:</b> {stars}\n"
           f"⭐ <b>Лучший ник:</b> {bu or '—'}\n📱 <b>Лучший номер:</b> {bn or '—'}\n"
           f"🖼 <b>Лучший NFT:</b> {bf or '—'}\n\n"
           f"👤 <b>Ники</b> ({len(users)}/{slots_limit(target_id,'user')}):\n")
    for i, r, pr in users[:5]:
        txt += f"{RARITIES[r]['emoji']} {i} — {r} ({pr:,} 🪙){' ⭐' if i==bu else ''}\n"
    if len(users) > 5: txt += f"… и ещё {len(users)-5}\n"
    txt += f"\n📱 <b>Номера</b> ({len(numbers)}/{slots_limit(target_id,'number')}):\n"
    for i, r, pr in numbers[:5]:
        txt += f"{RARITIES[r]['emoji']} {i} — {r} ({pr:,} 🪙){' ⭐' if i==bn else ''}\n"
    if len(numbers) > 5: txt += f"… и ещё {len(numbers)-5}\n"
    txt += f"\n🖼 <b>NFT</b> ({len(nfts)}/{slots_limit(target_id,'nft')}):\n"
    for i, r, pr in nfts[:5]:
        txt += f"{RARITIES[r]['emoji']} {i} — {r} ({pr:,} ⭐){' ⭐' if i==bf else ''}\n"
    if len(nfts) > 5: txt += f"… и ещё {len(nfts)-5}\n"
    bot.reply_to(m, txt, parse_mode="HTML")

# ==================== СЛОТЫ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("слот"))
def slot_cmd(m):
    text = m.text.lower().strip()
    if text in ("слот", "слоты"):
        uc = slot_cost(m.from_user.id, "user"); nc = slot_cost(m.from_user.id, "number"); fc = slot_cost(m.from_user.id, "nft")
        return bot.reply_to(m,
            f"📦 <b>Слоты</b>\n\n"
            f"👤 Ники: {count_items(m.from_user.id,'user')}/{slots_limit(m.from_user.id,'user')}\n"
            f"• <code>слот купить юзы</code> — {uc:,} 🪙\n\n"
            f"📱 Номера: {count_items(m.from_user.id,'number')}/{slots_limit(m.from_user.id,'number')}\n"
            f"• <code>слот купить номера</code> — {nc:,} 🪙\n\n"
            f"🖼 NFT: {count_items(m.from_user.id,'nft')}/{slots_limit(m.from_user.id,'nft')}\n"
            f"• <code>слот купить нфт</code> — {fc:,} 🪙", parse_mode="HTML")
    for t, cost_fn, ub_field in [("слот купить юзы", "user", "ub"), ("слот купить номера", "number", "nb"), ("слот купить нфт", "nft", "nbft")]:
        if text == t:
            cost = slot_cost(m.from_user.id, cost_fn)
            if get_coins(m.from_user.id) < cost: return bot.reply_to(m, f"❌ Нужно {cost:,} 🪙")
            add_coins(m.from_user.id, -cost)
            ub, nb, nbft = get_bought(m.from_user.id)
            if cost_fn == "user": cur.execute("UPDATE slots SET ub=? WHERE tg_id=?", (ub+1, m.from_user.id))
            elif cost_fn == "number": cur.execute("UPDATE slots SET nb=? WHERE tg_id=?", (nb+1, m.from_user.id))
            else: cur.execute("UPDATE slots SET nbft=? WHERE tg_id=?", (nbft+1, m.from_user.id))
            conn.commit()
            return bot.reply_to(m, f"✅ Расширено. Лимит: {slots_limit(m.from_user.id, cost_fn)}")
    bot.reply_to(m, "слот | слот купить юзы | слот купить номера | слот купить нфт")

# ==================== ИНВЕНТАРЬ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "инвентарь")
def inv(m):
    register(m.from_user.id, m.from_user.username)
    txt, page, pages = build_inv_page(m.from_user.id, "user", 0)
    kb = inv_keyboard(m.from_user.id, "user", page, pages)
    bot.reply_to(m, txt, parse_mode="HTML", reply_markup=kb)

# ==================== ПОСТАВИТЬ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("поставить"))
def equip(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "поставить @user / +7777 / NFT")
    item, typ = parse_item(p[1])
    if owner(item) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого")
    if typ == "user": set_eq(m.from_user.id, user=item)
    elif typ == "number": set_eq(m.from_user.id, number=item)
    else: set_eq(m.from_user.id, nft=item)
    bot.reply_to(m, f"⭐ Лучший: {item}")

# ==================== БИРЖА ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "биржа")
def exchange(m):
    cur.execute("SELECT id, seller_id, item, type, rarity, price FROM listings ORDER BY id DESC LIMIT 30")
    rows = cur.fetchall()
    if not rows: return bot.reply_to(m, "🏦 Биржа пуста")
    txt = "🏦 <b>Биржа</b>\n\n"
    for lid, seller, item, typ, rar, price in rows:
        if typ == "nft":
            txt += f"<code>#{lid}</code> {RARITIES[rar]['emoji']} {item} — <b>{price:,}</b> ⭐ (от {display_name(seller)})\n"
        else:
            txt += f"<code>#{lid}</code> {RARITIES[rar]['emoji']} {item} — <b>{price:,}</b> 🪙 (от {display_name(seller)})\n"
    txt += "\n<code>купить &lt;id&gt;</code> / <code>снять &lt;id&gt;</code>"
    bot.reply_to(m, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("выставить"))
def list_item(m):
    p = m.text.split()
    if len(p) < 3: return bot.reply_to(m, "выставить @user 500")
    item, typ = parse_item(p[1])
    try: price = int(p[2])
    except: return bot.reply_to(m, "Число")
    if price <= 0: return bot.reply_to(m, "> 0")
    if owner(item) != m.from_user.id: return bot.reply_to(m, "Нет такого")
    cur.execute("SELECT rarity FROM inventory WHERE item=?", (item,))
    rar = cur.fetchone()[0]
    cur.execute("DELETE FROM inventory WHERE item=?", (item,))
    clear_eq(m.from_user.id, item)
    cur.execute("INSERT INTO listings(seller_id,item,type,rarity,price,currency) VALUES(?,?,?,?,?,?)",
                (m.from_user.id, item, typ, rar, price, "stars" if typ=="nft" else "coins")); conn.commit()
    bot.reply_to(m, f"✅ {item} выставлен за {price:,} {'⭐' if typ=='nft' else '🪙'}")

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
    if seller != m.from_user.id: return bot.reply_to(m, "Не твой лот")
    if count_items(seller, typ) >= slots_limit(seller, typ): return bot.reply_to(m, "❌ Нет места")
    cur.execute("DELETE FROM listings WHERE id=?", (lid,))
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (seller, item, typ, rar, price)); conn.commit()
    bot.reply_to(m, f"✅ {item} возвращён")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("купить"))
def buy_lot(m):
    text = m.text.lower()
    # Не перехватывать "купить звёзды"
    if text.startswith("купить звёзды"): return
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "купить <id>")
    try: lid = int(p[1])
    except: return bot.reply_to(m, "ID — число")
    cur.execute("SELECT seller_id, item, type, rarity, price, currency FROM listings WHERE id=?", (lid,))
    r = cur.fetchone()
    if not r: return bot.reply_to(m, "Лот не найден")
    seller, item, typ, rar, price, currency = r
    if seller == m.from_user.id: return bot.reply_to(m, "Твой лот")
    if currency == "stars":
        if get_stars(m.from_user.id) < price: return bot.reply_to(m, f"❌ Нужно {price:,} ⭐")
        if count_items(m.from_user.id, typ) >= slots_limit(m.from_user.id, typ): return bot.reply_to(m, "❌ Нет места")
        add_stars(m.from_user.id, -price); add_stars(seller, price)
    else:
        if get_coins(m.from_user.id) < price: return bot.reply_to(m, f"❌ Нужно {price:,} 🪙")
        if count_items(m.from_user.id, typ) >= slots_limit(m.from_user.id, typ): return bot.reply_to(m, "❌ Нет места")
        add_coins(m.from_user.id, -price); add_coins(seller, price)
    cur.execute("DELETE FROM listings WHERE id=?", (lid,))
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, item, typ, rar, price)); conn.commit()
    bot.reply_to(m, f"✅ Купил {item} за {price:,} {'⭐' if currency=='stars' else '🪙'}")

# ==================== БОНУС ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower() in ("бонус", "ежедневно"))
def daily(m):
    register(m.from_user.id, m.from_user.username)
    cur.execute("SELECT last_claim FROM daily WHERE tg_id=?", (m.from_user.id,))
    r = cur.fetchone()
    now = int(time.time())
    if r and now - r[0] < 86400:
        left = 86400 - (now - r[0]); h, rem = divmod(left, 3600)
        return bot.reply_to(m, f"⏳ Через <b>{h}ч {rem//60}м</b>", parse_mode="HTML")
    reward = random.randint(50, 200)
    add_coins(m.from_user.id, reward)
    cur.execute("INSERT OR REPLACE INTO daily(tg_id,last_claim) VALUES(?,?)", (m.from_user.id, now)); conn.commit()
    bot.reply_to(m, f"🎁 +<b>{reward:,}</b> 🪙\n💰 Баланс: {get_coins(m.from_user.id):,}", parse_mode="HTML")

# ==================== АДМИНКА ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("админ выдать"))
def admin_give(m):
    if not is_admin(m.from_user.id, m.from_user.username): return bot.reply_to(m, "❌ Нет прав")
    p = m.text.split()
    if len(p) < 4: return bot.reply_to(m, "админ выдать @user 1000")
    try: amount = int(p[3])
    except: return bot.reply_to(m, "Сумма — число")
    tid = by_uname(p[2]) if p[2].startswith("@") else (int(p[2]) if p[2].lstrip("-").isdigit() else None)
    if not tid: return bot.reply_to(m, "Не найден")
    add_coins(tid, amount)
    bot.reply_to(m, f"✅ Выдано {amount:,} 🪙 → {display_name(tid)}")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("админ звезда"))
def admin_star(m):
    if not is_admin(m.from_user.id, m.from_user.username): return bot.reply_to(m, "❌ Нет прав")
    p = m.text.split()
    if len(p) < 4: return bot.reply_to(m, "админ звезда @user 10")
    try: amount = int(p[3])
    except: return bot.reply_to(m, "Число")
    tid = by_uname(p[2]) if p[2].startswith("@") else (int(p[2]) if p[2].lstrip("-").isdigit() else None)
    if not tid: return bot.reply_to(m, "Не найден")
    add_stars(tid, amount)
    bot.reply_to(m, f"✅ Выдано {amount} ⭐ → {display_name(tid)}")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("админ слот"))
def admin_slot(m):
    if not is_admin(m.from_user.id, m.from_user.username): return bot.reply_to(m, "❌ Нет прав")
    p = m.text.split()
    if len(p) < 4: return bot.reply_to(m, "админ слот @user 5")
    try: count = int(p[3])
    except: return bot.reply_to(m, "Число")
    tid = by_uname(p[2]) if p[2].startswith("@") else (int(p[2]) if p[2].lstrip("-").isdigit() else None)
    if not tid: return bot.reply_to(m, "Не найден")
    ub, nb, nbft = get_bought(tid)
    cur.execute("INSERT OR REPLACE INTO slots(tg_id,ub,nb,nbft) VALUES(?,?,?,?)", (tid, ub+count, nb+count, nbft+count)); conn.commit()
    bot.reply_to(m, f"✅ +{count} слотов каждого типа → {display_name(tid)}")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "админ топ")
def admin_top(m):
    if not is_admin(m.from_user.id, m.from_user.username): return
    cur.execute("SELECT COUNT(*) FROM users"); u = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM inventory"); i = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM inventory WHERE type='nft'"); n = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM listings"); l = cur.fetchone()[0]
    cur.execute("SELECT SUM(coins) FROM balances"); c = cur.fetchone()[0] or 0
    cur.execute("SELECT SUM(amount) FROM stars"); s = cur.fetchone()[0] or 0
    bot.reply_to(m, f"📊 <b>Статистика</b>\n👥 Игроков: {u}\n🎒 Предметов: {i}\n🖼 NFT: {n}\n🏦 Лотов: {l}\n💰 Монет: {c:,}\n⭐ Звёзд: {s:,}", parse_mode="HTML")

# ВАЖНО: последним
@bot.message_handler(func=lambda m: m.text and m.from_user.username)
def track(m):
    register(m.from_user.id, m.from_user.username)

print("Бот запущен...")
bot.infinity_polling(timeout=60, long_polling_timeout=60)