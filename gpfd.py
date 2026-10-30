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
    tg_id INTEGER, item TEXT UNIQUE, type TEXT, rarity TEXT, price INTEGER, bg TEXT)""")
cur.execute("CREATE TABLE IF NOT EXISTS balances(tg_id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS equipped(tg_id INTEGER PRIMARY KEY, best_user TEXT, best_number TEXT, best_nft TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS slots(tg_id INTEGER PRIMARY KEY, ub INTEGER DEFAULT 0, nb INTEGER DEFAULT 0, nbft INTEGER DEFAULT 0)")
cur.execute("""CREATE TABLE IF NOT EXISTS listings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER, item TEXT, type TEXT, rarity TEXT, price INTEGER, currency TEXT DEFAULT 'coins')""")
cur.execute("CREATE TABLE IF NOT EXISTS daily(tg_id INTEGER PRIMARY KEY, last_claim INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS stars(tg_id INTEGER PRIMARY KEY, amount INTEGER DEFAULT 0)")
conn.commit()

try: cur.execute("ALTER TABLE equipped ADD COLUMN best_nft TEXT")
except: pass
try: cur.execute("ALTER TABLE slots ADD COLUMN nbft INTEGER DEFAULT 0")
except: pass
try: cur.execute("ALTER TABLE listings ADD COLUMN currency TEXT DEFAULT 'coins'")
except: pass
try: cur.execute("ALTER TABLE inventory ADD COLUMN bg TEXT")
except: pass
conn.commit()

# ==================== РЕДКОСТИ ====================
RARITIES = {
    "обычный":     {"emoji": "⚪", "price": 100,      "stars": 0},
    "редкий":      {"emoji": "🔵", "price": 500,      "stars": 0},
    "эпический":   {"emoji": "🟣", "price": 2000,     "stars": 50},
    "легендарный": {"emoji": "🟡", "price": 10000,    "stars": 100},
    "мифический":  {"emoji": "🔴", "price": 50000,    "stars": 300},
    "мега":        {"emoji": "💎", "price": 99000000, "stars": 1000},
}

SPECIAL_RARITIES = {
    "@durov":"мега","@lytixx":"мега","@developer":"мифический","@telegram":"мифический",
    "@botfather":"мифический","@tgpremium":"мифический","@melstroy":"мифический",
    "@musk":"мифический","@trump":"мифический","@putin":"мифический",
    "@tmex":"эпический","@tgsx":"эпический","@tgl":"эпический","@botx":"эпический","@webx":"эпический",
    "@mebx":"редкий","@setx":"редкий","@father":"редкий","@premium":"редкий",
}
SPECIAL_PRICES = {
    "@durov":99000000,"@lytixx":99000000,"@developer":50000000,"@melstroy":40000000,
    "@putin":30000000,"@musk":25000000,"@telegram":25000000,"@trump":20000000,
    "@botfather":20000000,"@tgpremium":15000000,"@tmex":10000000,"@tgsx":5000000,
    "@tgl":2000000,"@botx":2000000,"@webx":2000000,
    "@mebx":500000,"@setx":500000,"@father":500000,"@premium":500000,
}

CRAFT_TARGETS = ["@durov","@lytixx","@developer","@telegram","@botfather","@tgpremium",
                 "@tmex","@tgsx","@melstroy","@musk","@trump","@putin"]

RECIPES = {
    "@tmex":      {"rarity":"эпический","fixed":["@mebx","@setx"],   "rand":2,"min":"обычный","chance":0.9},
    "@tgsx":      {"rarity":"эпический","fixed":["@tgl","@father"],  "rand":2,"min":"обычный","chance":0.9},
    "@telegram":  {"rarity":"мифический","fixed":["@tmex","@webx"],   "rand":3,"min":"эпический","chance":0.6},
    "@botfather": {"rarity":"мифический","fixed":["@botx","@father"], "rand":3,"min":"редкий","chance":0.7},
    "@developer": {"rarity":"мифический","fixed":["@tgl","@botx"],    "rand":5,"min":"легендарный","chance":0.5},
    "@tgpremium": {"rarity":"мифический","fixed":["@tgsx","@premium"],"rand":5,"min":"эпический","chance":0.55},
    "@melstroy":  {"rarity":"мифический","fixed":["@crow","@free"],   "rand":5,"min":"эпический","chance":0.55},
    "@musk":      {"rarity":"мифический","fixed":["@tgl","@webx"],    "rand":5,"min":"эпический","chance":0.55},
    "@trump":     {"rarity":"мифический","fixed":["@botx","@father"], "rand":6,"min":"легендарный","chance":0.5},
    "@putin":     {"rarity":"мифический","fixed":["@melstroy","@trump"],"rand":8,"min":"легендарный","chance":0.45},
    "@durov":     {"rarity":"мега","fixed":["@crow","@free"],         "rand":7,"min":"эпический","chance":0.5},
    "@lytixx":    {"rarity":"мега","fixed":[],                        "rand":10,"min":"эпический","chance":0.5},
}

# ==================== NFT ====================
NFT_TYPES = {
    "IceCream": {
        "emoji":"🍦","name":"Мороженое",
        "aliases":["icecream","ice","мороженое","мороженка","айс"],
        "min_price":500,"max_price":10000,"max_num":999999,
    },
    "MirageLamp": {
        "emoji":"🪔","name":"Мираж-лампа",
        "aliases":["miragelamp","mirage","лампа","мираж","миражлампа"],
        "min_price":800,"max_price":20000,"max_num":999999,
    },
    "ToyBear": {
        "emoji":"🧸","name":"Мишка",
        "aliases":["toybear","bear","мишка","медведь","игрушка"],
        "min_price":3000,"max_price":500000,"max_num":9999999,
    },
    "SnoopDogg": {
        "emoji":"🐶","name":"Снуп Догг",
        "aliases":["snoopdogg","snoop","снуп","снупдогг","собака"],
        "min_price":1000,"max_price":100000,"max_num":9999999,
    },
    "ScaredCat": {
        "emoji":"🐈","name":"Испуганный кот",
        "aliases":["scaredcat","cat","кошка","кот","скаредкат","испуганный"],
        "min_price":30000,"max_price":1000000,"max_num":19000,
    },
    "ResistanceDog": {
        "emoji":"🐕","name":"Собака сопротивления",
        "aliases":["resistancedog","resistance","сопротивление","резистдог"],
        "min_price":50000,"max_price":1500000,"max_num":15000,
    },
    "PlushPepe": {
        "emoji":"🐸","name":"Плюш Пепе",
        "aliases":["plushpepe","pepe","пепе","плюшпепе","плюш","жаба","лягушка"],
        "min_price":1000000,"max_price":10000000,"max_num":3000,
    },
    "DurovCap": {
        "emoji":"🧢","name":"Кепка Дурова",
        "aliases":["durovcap","cap","кепка","дуров","кепкадурова"],
        "min_price":200000,"max_price":5000000,"max_num":99999,
    },
    "Heart": {
        "emoji":"💝","name":"Сердце",
        "aliases":["heart","сердце","сердечко"],
        "min_price":2000,"max_price":200000,"max_num":9999999,
    },
    "DiamondRing": {
        "emoji":"💍","name":"Кольцо с алмазом",
        "aliases":["diamondring","ring","кольцо","алмаз","кольцоалмаз"],
        "min_price":5000,"max_price":300000,"max_num":999999,
    },
    "InstantRamen": {
        "emoji":"🍜","name":"Рамен",
        "aliases":["instantramen","ramen","рамен","лапша","суп"],
        "min_price":300,"max_price":50000,"max_num":9999999,
    },
    "EasterEgg": {
        "emoji":"🥚","name":"Пасхальное яйцо",
        "aliases":["easteregg","egg","яйцо","яйко","пасха"],
        "min_price":400,"max_price":80000,"max_num":999999,
    },
    "SkullFlower": {
        "emoji":"🌺","name":"Цветок-череп",
        "aliases":["skullflower","flower","череп","цветок"],
        "min_price":1500,"max_price":150000,"max_num":999999,
    },
}

BG_NAMES = {
    "обычный":     {"emoji":"⬜","mult":1.0},
    "редкий":      {"emoji":"🟦","mult":1.5},
    "эпический":   {"emoji":"🟪","mult":2.5},
    "легендарный": {"emoji":"🟨","mult":5.0},
    "мифический":  {"emoji":"🟥","mult":12.0},
    "монохром":    {"emoji":"⬛","mult":8.0},
}

def nft_bg(num):
    idx = (num * 31 + num // 7 + 17) % 100
    if idx in (1, 2, 3, 97, 98, 99): return "монохром"
    if idx < 50: return "обычный"
    if idx < 80: return "редкий"
    if idx < 95: return "эпический"
    if idx < 99: return "легендарный"
    return "мифический"

def nft_price(nft_type, num):
    t = NFT_TYPES[nft_type]
    base = t["min_price"]; cap = t["max_price"]
    s = str(num); L = len(s)
    if L >= 6: len_f = 0.05
    elif L == 5: len_f = 0.15
    elif L == 4: len_f = 0.35
    elif L == 3: len_f = 0.55
    elif L == 2: len_f = 0.80
    else: len_f = 1.0
    cnt = Counter(s).most_common(1)[0][1]
    if cnt == L and L > 1: rep_f = 1.0
    elif cnt >= 3: rep_f = 0.7
    elif cnt >= 2: rep_f = 0.4
    else: rep_f = 0.0
    bg = nft_bg(num)
    bg_f = min(1.0, (BG_NAMES[bg]["mult"] - 1) / 11)
    main_f = min(1.0, len_f * 0.65 + rep_f * 0.35)
    total_f = min(1.0, main_f * 0.65 + bg_f * 0.35)
    price = int(base + (cap - base) * total_f)
    return price, bg

def nft_rarity(price):
    if price >= 1000000: return "мега"
    if price >= 100000: return "мифический"
    if price >= 20000: return "легендарный"
    if price >= 5000: return "эпический"
    if price >= 1000: return "редкий"
    return "обычный"

def parse_nft(text):
    text = text.strip()
    m = re.search(r"([a-zа-яё]+)[\-_\s]?(\d+)", text, re.IGNORECASE)
    if not m: return None
    type_in = m.group(1).lower()
    num = int(m.group(2))
    nft_type = None
    for name, t in NFT_TYPES.items():
        if type_in in t["aliases"] or type_in == name.lower():
            nft_type = name; break
    if not nft_type: return None
    if num <= 0 or num > NFT_TYPES[nft_type]["max_num"]:
        return {"error": f"Число должно быть 1–{NFT_TYPES[nft_type]['max_num']:,}"}
    price, bg = nft_price(nft_type, num)
    item = f"t.me/nft/{nft_type}-{num}"
    return {"type": nft_type, "num": num, "item": item, "price": price, "bg": bg}

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
    s = re.sub(r"[\s\-()]","",s.strip())
    if not s.startswith("+"): s = "+" + s
    return s
def rarity_user(u):
    if u in SPECIAL_RARITIES: return SPECIAL_RARITIES[u]
    name = u[1:].lower()
    if not re.fullmatch(r"[a-z]+",name): return "редкий" if len(name)<=3 else "обычный"
    L = len(name)
    if L<=3: return "мифический"
    if L<=4: return "легендарный"
    if L<=5: return "эпический"
    if L<=7: return "редкий"
    return "обычный"
def rarity_number(num):
    digits = re.sub(r"\D","",num)
    if not digits: return "обычный"
    c = Counter(digits).most_common(1)[0][1]
    if c>=6: return "мифический"
    if c>=5: return "легендарный"
    if c>=4: return "эпический"
    if c>=3: return "редкий"
    return "обычный"
def price_of(item, rar): return SPECIAL_PRICES.get(item, RARITIES[rar]["price"])
def owner(item):
    cur.execute("SELECT tg_id FROM inventory WHERE item=?",(item,))
    r = cur.fetchone()
    return r[0] if r else None
def by_uname(u):
    cur.execute("SELECT tg_id FROM users WHERE username=?",(norm(u),))
    r = cur.fetchone()
    return r[0] if r else None
def get_coins(tg_id):
    cur.execute("SELECT coins FROM balances WHERE tg_id=?",(tg_id,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO balances(tg_id,coins) VALUES(?,0)",(tg_id,)); conn.commit(); return 0
    return r[0]
def add_coins(tg_id, amount):
    cur.execute("INSERT OR IGNORE INTO balances(tg_id,coins) VALUES(?,0)",(tg_id,))
    cur.execute("UPDATE balances SET coins=coins+? WHERE tg_id=?",(amount,tg_id)); conn.commit()
def get_stars(tg_id):
    cur.execute("SELECT amount FROM stars WHERE tg_id=?",(tg_id,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO stars(tg_id,amount) VALUES(?,0)",(tg_id,)); conn.commit(); return 0
    return r[0]
def add_stars(tg_id, n):
    cur.execute("INSERT OR IGNORE INTO stars(tg_id,amount) VALUES(?,0)",(tg_id,))
    cur.execute("UPDATE stars SET amount=amount+? WHERE tg_id=?",(n,tg_id)); conn.commit()
def get_inv(tg_id, typ=None):
    if typ:
        cur.execute("SELECT item, rarity, price, bg FROM inventory WHERE tg_id=? AND type=?",(tg_id,typ))
    else:
        cur.execute("SELECT item, rarity, price, type, bg FROM inventory WHERE tg_id=?",(tg_id,))
    return cur.fetchall()
def count_items(tg_id, typ):
    cur.execute("SELECT COUNT(*) FROM inventory WHERE tg_id=? AND type=?",(tg_id,typ))
    return cur.fetchone()[0]
def get_bought(tg_id):
    cur.execute("SELECT ub, nb, nbft FROM slots WHERE tg_id=?",(tg_id,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO slots(tg_id,ub,nb,nbft) VALUES(?,0,0,0)",(tg_id,)); conn.commit(); return 0,0,0
    return r
def slots_limit(tg_id, typ):
    ub, nb, nbft = get_bought(tg_id)
    if typ=="user": return 5+5*ub
    if typ=="number": return 5+5*nb
    return 3+3*nbft
def slot_cost(tg_id, typ):
    ub, nb, nbft = get_bought(tg_id)
    if typ=="user": return 100*(ub+1)
    if typ=="number": return 100*(nb+1)
    return 500*(nbft+1)
def get_equipped(tg_id):
    cur.execute("SELECT best_user, best_number, best_nft FROM equipped WHERE tg_id=?",(tg_id,))
    r = cur.fetchone()
    return r if r else (None,None,None)
def set_eq(tg_id, user=None, number=None, nft=None):
    bu, bn, bf = get_equipped(tg_id)
    cur.execute("INSERT OR REPLACE INTO equipped(tg_id,best_user,best_number,best_nft) VALUES(?,?,?,?)",
                (tg_id, user if user is not None else bu, number if number is not None else bn, nft if nft is not None else bf))
    conn.commit()
def clear_eq(tg_id, item):
    for col in ("best_user","best_number","best_nft"):
        cur.execute(f"UPDATE equipped SET {col}=CASE WHEN {col}=? THEN NULL ELSE {col} END WHERE tg_id=?",(item,tg_id))
    conn.commit()
def username_of(tg_id):
    cur.execute("SELECT username FROM users WHERE tg_id=?",(tg_id,))
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
    nft = parse_nft(arg)
    if nft and "error" not in nft: return nft["item"], "nft"
    return norm(arg), "user"
def register(tg_id, username):
    if username:
        cur.execute("INSERT OR REPLACE INTO users VALUES(?,?)",(tg_id,norm(username))); conn.commit()

# ==================== АНИМАЦИЯ ====================
def drop_animation(chat_id, reply_to_id, final_text, rarity):
    if rarity in ("мега","мифический"):
        frames = [("🎰 |",0.2),("🎰 /",0.2),("🎰 —",0.2),("🎰 \\",0.2),("✨✨✨",0.3)]
    elif rarity in ("легендарный","эпический"):
        frames = [("🎰 ...",0.25),("✨",0.3)]
    else:
        bot.send_message(chat_id, final_text, parse_mode="HTML", reply_to_message_id=reply_to_id); return
    msg = bot.send_message(chat_id, frames[0][0])
    for text, delay in frames[1:]:
        time.sleep(delay)
        try: bot.edit_message_text(text, chat_id, msg.message_id)
        except: pass
    time.sleep(0.3)
    try: bot.edit_message_text(final_text, chat_id, msg.message_id, parse_mode="HTML")
    except: bot.send_message(chat_id, final_text, parse_mode="HTML")

# ==================== ИНВЕНТАРЬ ====================
def build_inv_page(tg_id, typ, page):
    items = get_inv(tg_id, typ)
    total = len(items)
    page_size = 1 if typ == "nft" else 8
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    start = page * page_size
    chunk = items[start:start + page_size]
    titles = {"user":"👤 Ники","number":"📱 Номера","nft":"🖼 NFT"}
    title = titles.get(typ,"")
    limit = slots_limit(tg_id, typ)
    txt = f"<b>{title}</b> ({total}/{limit}) — стр. {page+1}/{pages}\n\n"
    if not chunk:
        txt += "пусто"
    else:
        for row in chunk:
            it, rar, price, bg = row
            if typ == "nft":
                bg_info = BG_NAMES.get(bg, {"emoji":"⬜"})
                txt += f"{RARITIES[rar]['emoji']} <b>{it}</b>\n"
                txt += f"   Фон: {bg_info['emoji']} {bg}\n"
                txt += f"   Цена: {price:,} ⭐ | {rar}\n"
            else:
                txt += f"{RARITIES[rar]['emoji']} {it} — {rar} ({price:,} 🪙)\n"
    return txt, page, pages

def inv_keyboard(owner_id, typ, page, pages):
    kb = types.InlineKeyboardMarkup()
    row = []
    if page > 0:
        row.append(types.InlineKeyboardButton("◀", callback_data=f"inv:{owner_id}:{typ}:{page-1}"))
    row.append(types.InlineKeyboardButton(f"{page+1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        row.append(types.InlineKeyboardButton("▶", callback_data=f"inv:{owner_id}:{typ}:{page+1}"))
    kb.row(*row)
    other = {"user":"number","number":"nft","nft":"user"}[typ]
    names = {"user":"👤 Ники","number":"📱 Номера","nft":"🖼 NFT"}
    kb.row(types.InlineKeyboardButton(names[other], callback_data=f"inv:{owner_id}:{other}:0"))
    return kb

# ==================== МЕНЮ ====================
MENU_PAGES = [
    {"title":"🎒 КОЛЛЕКЦИЯ","lines":[
        "• <code>взять @user</code> — забрать ник",
        "• <code>номер +7777...</code> — забрать номер",
        "• <code>инвентарь</code> — листать",
        "• <code>поставить @user</code> — лучший ник",
        "• <code>дать @user</code> — передать (ответом)",
    ]},
    {"title":"🖼 NFT","lines":[
        "• <code>нфт icecream-7</code> — взять NFT",
        "• <code>нфт пепе-100</code> — русские названия",
        "• <code>нфт кепка-500</code> — тоже",
        "• <code>каталог нфт</code> — все типы",
        "• <code>улучшить icecream-7</code> — рулетка",
        "",
        "<b>Типы NFT:</b>",
        "🍦 мороженое, 🪔 миражлампа, 🧸 мишка",
        "🐶 снуп, 🐈 кошка, 🐕 собака, 🐸 пепе",
        "🧢 кепка, 💝 сердце, 💍 кольцо, 🍜 рамен",
        "",
        "💡 Цена зависит от: длины числа,",
        "повторов (777), фона, монохрома",
    ]},
    {"title":"⭐ ЗВЁЗДЫ","lines":[
        "• <code>мои звёзды</code> — баланс",
        "• Звёзды только с продажи ников и NFT",
        "",
        "<b>За продажу ников (⭐):</b>",
        "🟣 эпический → 50 ⭐",
        "🟡 легендарный → 100 ⭐",
        "🔴 мифический → 300 ⭐",
        "💎 мега → 1000 ⭐",
        "",
        "• Продажа NFT — 80% от цены",
    ]},
    {"title":"🛠 КРАФТ","lines":[
        "• <code>крафт</code> — рецепты",
        "• <code>крафт @durov</code> — крафтить",
        "• Шанс 45–90%",
    ]},
    {"title":"💰 ПРОДАЖА","lines":[
        "• <code>продать @user</code> — выбор валюты",
        "• <code>продать +7777</code>",
        "• <code>продать icecream-7</code>",
        "• <code>продать всё</code>",
        "",
        "🏦 <b>БИРЖА:</b>",
        "• <code>биржа</code> — лоты",
        "• <code>выставить @user 500</code>",
        "• <code>купить <id></code> / <code>снять <id></code>",
    ]},
    {"title":"📦 ЭКОНОМИКА","lines":[
        "• <code>бонус</code> — 50–200 🪙 (5% шанс +1⭐)",
        "• <code>баланс</code> — всё",
        "• <code>топ</code> — рейтинг игроков",
        "• <code>слот</code> — инфо",
        "• <code>слот купить юзы</code> — +5",
        "• <code>слот купить номера</code> — +5",
        "• <code>слот купить нфт</code> — +3",
    ]},
    {"title":"👑 АДМИНКА","lines":[
        "• <code>админ выдать @user 1000</code>",
        "• <code>админ звезда @user 10</code>",
        "• <code>админ слот @user 5</code>",
        "• <code>админ топ</code>",
    ]},
]

def build_menu(page=0):
    page = max(0, min(page, len(MENU_PAGES)-1))
    p = MENU_PAGES[page]
    text = f"📋 <b>Меню</b> — {page+1}/{len(MENU_PAGES)}\n\n<b>{p['title']}</b>\n" + "\n".join(p["lines"])
    kb = types.InlineKeyboardMarkup()
    row = []
    if page > 0:
        row.append(types.InlineKeyboardButton("◀ Назад", callback_data=f"menu:{page-1}"))
    row.append(types.InlineKeyboardButton(f"{page+1}/{len(MENU_PAGES)}", callback_data="noop"))
    if page < len(MENU_PAGES)-1:
        row.append(types.InlineKeyboardButton("Далее ▶", callback_data=f"menu:{page+1}"))
    kb.row(*row)
    return text, kb

# ==================== КРАФТ-ХЕЛПЕР ====================
def get_random_rich(tg_id, min_rarity, exclude, count):
    order = ["обычный","редкий","эпический","легендарный","мифический","мега"]
    min_idx = order.index(min_rarity)
    allowed = set(order[min_idx:])
    cur.execute("SELECT item, rarity FROM inventory WHERE tg_id=? AND type='user'",(tg_id,))
    cand = [item for item,rar in cur.fetchall() if rar in allowed and item not in exclude and item not in CRAFT_TARGETS]
    if len(cand) < count: return None
    return random.sample(cand, count)

# ==================== ХЕНДЛЕРЫ ====================
@bot.message_handler(commands=["start"])
def start(m):
    register(m.from_user.id, m.from_user.username)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📋 Меню", callback_data="menu:0"))
    bot.reply_to(m, "👋 Привет!\nНажми кнопку или пиши <code>команды</code>.", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "noop")
def cb_noop(call):
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("menu:"))
def cb_menu(call):
    try:
        page = int(call.data.split(":")[1])
        text, kb = build_menu(page)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("inv:"))
def cb_inv(call):
    parts = call.data.split(":")
    owner_id = int(parts[1]); typ = parts[2]; page = int(parts[3])
    if call.from_user.id != owner_id:
        return bot.answer_callback_query(call.id, "Не твой инвентарь", show_alert=True)
    txt, page, pages = build_inv_page(owner_id, typ, page)
    kb = inv_keyboard(owner_id, typ, page, pages)
    try: bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except: pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("sellcur:"))
def cb_sell(call):
    parts = call.data.split(":")
    item = parts[1]; typ = parts[2]; currency = parts[3]
    if owner(item) != call.from_user.id:
        return bot.answer_callback_query(call.id, "Не твоё", show_alert=True)
    cur.execute("SELECT price, rarity FROM inventory WHERE item=?",(item,))
    price, rar = cur.fetchone()
    cur.execute("DELETE FROM inventory WHERE item=?",(item,))
    clear_eq(call.from_user.id, item)
    if currency == "coins":
        gain = price
        add_coins(call.from_user.id, gain)
        result = f"💰 +{gain:,} 🪙"
    else:
        if typ == "nft":
            gain = int(price * 0.8)
            add_stars(call.from_user.id, gain)
            result = f"⭐ +{gain:,}"
        else:
            gain = RARITIES[rar]["stars"]
            if gain == 0:
                return bot.answer_callback_query(call.id, "Этот ник нельзя продать за ⭐", show_alert=True)
            add_stars(call.from_user.id, gain)
            result = f"⭐ +{gain}"
    conn.commit()
    bot.edit_message_text(f"✅ Продал <b>{item}</b> ({rar})\n{result}", call.message.chat.id, call.message.message_id, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: m.text and m.text.lower() in ("команды","меню"))
def commands(m):
    text, kb = build_menu(0)
    bot.reply_to(m, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "цены")
def prices(m):
    txt = ("💸 <b>Продажа ников</b>\n\n"
           "⚪ обычный — 100 🪙\n🔵 редкий — 500 🪙\n"
           "🟣 эпический — 2 000 🪙 / 50 ⭐\n"
           "🟡 легендарный — 10 000 🪙 / 100 ⭐\n"
           "🔴 мифический — 50 000 🪙 / 300 ⭐\n"
           "💎 мега — 99 000 000 🪙 / 1000 ⭐\n\n"
           "<b>NFT (за ⭐):</b>\n"
           "🍦 мороженое — 500–10k\n🪔 миражлампа — 800–20k\n"
           "🧸 мишка — 3k–500k\n🐶 снуп — 1k–100k\n"
           "🐈 кошка — 30k–1M\n🐕 собака — 50k–1.5M\n"
           "🧢 кепка — 200k–5M\n🐸 пепе — 1M–10M")
    bot.reply_to(m, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "каталог нфт")
def nft_catalog(m):
    txt = "🖼 <b>Каталог NFT</b>\n\n"
    for name, t in NFT_TYPES.items():
        txt += f"{t['emoji']} <b>{name}</b> ({t['name']})\n"
        txt += f"   {t['min_price']:,}–{t['max_price']:,} ⭐ | макс: {t['max_num']:,}\n"
        txt += f"   писать: <code>{t['aliases'][-1]}</code> или <code>{name.lower()}</code>\n\n"
    txt += "Пример: <code>нфт пепе-100</code>"
    bot.reply_to(m, txt, parse_mode="HTML")

# ==================== ЗВЁЗДЫ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower() in ("мои звёзды","звёзды","⭐"))
def my_stars(m):
    bot.reply_to(m, f"⭐ <b>Звёзды:</b> {get_stars(m.from_user.id)}\n💰 Монеты: {get_coins(m.from_user.id):,}", parse_mode="HTML")

# ==================== NFT ====================
@bot.message_handler(func=lambda m: m.text and (m.text.lower().startswith("нфт ") or m.text.lower().startswith("nft ")))
def take_nft(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split(maxsplit=1)
    if len(p) < 2:
        return bot.reply_to(m, "<code>нфт пепе-100</code>\n<code>нфт icecream-7</code>", parse_mode="HTML")
    nft = parse_nft(p[1])
    if not nft: return bot.reply_to(m, "❌ Формат: <code>нфт пепе-100</code>", parse_mode="HTML")
    if "error" in nft: return bot.reply_to(m, f"❌ {nft['error']}", parse_mode="HTML")
    item = nft["item"]
    if owner(item): return bot.reply_to(m, f"❌ <b>{item}</b> занят", parse_mode="HTML")
    lim = slots_limit(m.from_user.id, "nft")
    if count_items(m.from_user.id, "nft") >= lim:
        return bot.reply_to(m, f"❌ Лимит NFT: {lim}. <code>слот купить нфт</code>", parse_mode="HTML")
    price = nft["price"]
    if get_stars(m.from_user.id) < price:
        return bot.reply_to(m, f"❌ Нужно <b>{price:,} ⭐</b> (у тебя {get_stars(m.from_user.id)})", parse_mode="HTML")
    add_stars(m.from_user.id, -price)
    rar = nft_rarity(price)
    bg_info = BG_NAMES[nft["bg"]]
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price,bg) VALUES(?,?,?,?,?,?)",
                (m.from_user.id, item, "nft", rar, price, nft["bg"])); conn.commit()
    drop_animation(m.chat.id, m.message_id,
        f"🖼 <b>NFT получен!</b>\n\n{RARITIES[rar]['emoji']} <b>{rar}</b>\n<b>{item}</b>\n"
        f"Фон: {bg_info['emoji']} {nft['bg']}\n💸 Заплачено: {price:,} ⭐\n⭐ Осталось: {get_stars(m.from_user.id)}",
        rar)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("улучшить"))
def upgrade_nft(m):
    p = m.text.split(maxsplit=1)
    if len(p) < 2: return bot.reply_to(m, "<code>улучшить пепе-100</code>", parse_mode="HTML")
    nft = parse_nft(p[1])
    if not nft or "error" in nft: return bot.reply_to(m, "❌ Формат: <code>улучшить пепе-100</code>", parse_mode="HTML")
    old_item = nft["item"]
    if owner(old_item) != m.from_user.id: return bot.reply_to(m, "❌ У тебя нет такого NFT")
    if not confirm_upgrade(m, old_item, nft["type"]):
        return
    _do_upgrade(m, old_item, nft["type"])

def confirm_upgrade(m, old_item, nft_type):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🎲 Улучшить", callback_data=f"upg:{old_item}"))
    kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="noop"))
    bot.reply_to(m,
        f"🎲 <b>Улучшение NFT</b>\n\n"
        f"Старый: {old_item}\n"
        f"Тип: {NFT_TYPES[nft_type]['emoji']} {NFT_TYPES[nft_type]['name']}\n\n"
        f"⚠️ Старый NFT сгорит безвозвратно\n"
        f"🎁 Получишь рандомный номер этого типа\n\n"
        f"<b>Шансы:</b>\n"
        f"Обычный (5-6 цифр) — 55%\n"
        f"4 цифры — 25%\n"
        f"3 цифры — 12%\n"
        f"2 цифры — 5%\n"
        f"1 цифра — 2%\n"
        f"Красивый (777, 5555) — бонус 15%",
        reply_markup=kb, parse_mode="HTML")
    return False

@bot.callback_query_handler(func=lambda c: c.data.startswith("upg:"))
def cb_upgrade(call):
    old_item = call.data.split(":",1)[1]
    if owner(old_item) != call.from_user.id:
        return bot.answer_callback_query(call.id, "Не твоё", show_alert=True)
    # Извлекаем тип
    m2 = re.search(r"nft/(\w+)-", old_item)
    if not m2: return bot.answer_callback_query(call.id, "Ошибка", show_alert=True)
    nft_type = m2.group(1)
    if nft_type not in NFT_TYPES: return bot.answer_callback_query(call.id, "Ошибка типа", show_alert=True)
    bot.answer_callback_query(call.id, "🎲 Улучшаем...")
    # Удаляем старый
    cur.execute("DELETE FROM inventory WHERE item=?",(old_item,))
    clear_eq(call.from_user.id, old_item)
    conn.commit()
    # Ролл
    new_num = upgrade_roll(NFT_TYPES[nft_type]["max_num"])
    new_price, new_bg = nft_price(nft_type, new_num)
    new_item = f"t.me/nft/{nft_type}-{new_num}"
    # Проверка что не занят (редко)
    if owner(new_item):
        new_num = random.randint(1, min(9999, NFT_TYPES[nft_type]["max_num"]))
        new_price, new_bg = nft_price(nft_type, new_num)
        new_item = f"t.me/nft/{nft_type}-{new_num}"
    rar = nft_rarity(new_price)
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price,bg) VALUES(?,?,?,?,?,?)",
                (call.from_user.id, new_item, "nft", rar, new_price, new_bg)); conn.commit()
    bg_info = BG_NAMES[new_bg]
    try:
        bot.edit_message_text(
            f"🎲 <b>Результат улучшения</b>\n\n"
            f"Было: {old_item}\n"
            f"Стало: <b>{new_item}</b>\n"
            f"{RARITIES[rar]['emoji']} {rar}\n"
            f"Фон: {bg_info['emoji']} {new_bg}\n"
            f"💰 Стоимость: {new_price:,} ⭐",
            call.message.chat.id, call.message.message_id, parse_mode="HTML")
    except: pass

def upgrade_roll(max_num):
    r = random.random()
    if r < 0.55: length = random.randint(5, 6)
    elif r < 0.80: length = 4
    elif r < 0.92: length = 3
    elif r < 0.97: length = 2
    else: length = 1
    length = min(length, len(str(max_num)))
    if length == 1:
        return random.randint(1, min(9, max_num))
    if random.random() < 0.15:
        digit = random.randint(1, 9)
        num = int(str(digit) * length)
        if num > max_num: num = random.randint(10**(length-1), max_num)
        return num
    lo = 10**(length-1)
    hi = min(10**length - 1, max_num)
    return random.randint(lo, hi)

# ==================== ВЗЯТЬ / ДАТЬ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("взять"))
def take(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "взять @user")
    u = norm(p[1])
    if not re.fullmatch(r"@[a-z0-9_]{3,32}", u): return bot.reply_to(m, "Плохой юз")
    if u in CRAFT_TARGETS: return bot.reply_to(m, f"❌ <b>{u}</b> только крафт", parse_mode="HTML")
    if owner(u): return bot.reply_to(m, "Занят")
    if count_items(m.from_user.id, "user") >= slots_limit(m.from_user.id, "user"):
        return bot.reply_to(m, "❌ Лимит. <code>слот купить юзы</code>", parse_mode="HTML")
    rar = rarity_user(u); price = price_of(u, rar)
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, u, "user", rar, price)); conn.commit()
    drop_animation(m.chat.id, m.message_id,
                   f"✅ <b>{u}</b> твой!\n{RARITIES[rar]['emoji']} <b>{rar}</b> — {price:,} 🪙", rar)

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
                   f"✅ <b>{num}</b> твой!\n{RARITIES[rar]['emoji']} <b>{rar}</b> — {price:,} 🪙", rar)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("дать"))
def give(m):
    p = m.text.split(maxsplit=1)
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
    cur.execute("UPDATE inventory SET tg_id=? WHERE item=?",(target,item)); conn.commit()
    bot.reply_to(m, f"➡️ {item} передан")

# ==================== КРАФТ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("крафт"))
def craft(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2:
        txt = "🛠 <b>Рецепты</b>\n\n"
        for target, r in RECIPES.items():
            txt += f"<b>{target}</b> ({RARITIES[r['rarity']]['emoji']} {r['rarity']}, {int(r['chance']*100)}%)\n"
            if r["fixed"]: txt += f"  • {', '.join(r['fixed'])}\n"
            txt += f"  • +{r['rand']} любых ({r['min']}+)\n\n"
        return bot.reply_to(m, txt, parse_mode="HTML")
    target = norm(p[1])
    recipe = RECIPES.get(target)
    if not recipe: return bot.reply_to(m, "❌ Нет рецепта")
    if owner(target) == m.from_user.id: return bot.reply_to(m, "Уже есть")
    if owner(target): return bot.reply_to(m, "❌ Занят")
    for f in recipe["fixed"]:
        cur.execute("SELECT 1 FROM inventory WHERE tg_id=? AND item=?",(m.from_user.id,f))
        if not cur.fetchone(): return bot.reply_to(m, f"❌ Нет: <b>{f}</b>", parse_mode="HTML")
    excludes = set(recipe["fixed"]) | set(CRAFT_TARGETS)
    rand = get_random_rich(m.from_user.id, recipe["min"], excludes, recipe["rand"])
    if rand is None: return bot.reply_to(m, f"❌ Нужно {recipe['rand']} юзов {recipe['min']}+", parse_mode="HTML")
    all_comp = recipe["fixed"] + rand
    for c in all_comp:
        cur.execute("DELETE FROM inventory WHERE item=?",(c,))
        clear_eq(m.from_user.id, c)
    conn.commit()
    if random.random() < recipe["chance"]:
        rar = recipe["rarity"]; price = price_of(target, rar)
        cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                    (m.from_user.id, target, "user", rar, price)); conn.commit()
        drop_animation(m.chat.id, m.message_id,
            f"✨ <b>УСПЕХ!</b>\n\n{RARITIES[rar]['emoji']} <b>{rar}</b>\n<b>{target}</b>\n💰 {price:,} 🪙", rar)
    else:
        bot.reply_to(m, f"💀 <b>ПРОВАЛ</b>\n🔥 Сгорело: {', '.join(all_comp)}", parse_mode="HTML")

# ==================== ПРОДАЖА (выбор валюты через кнопки) ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("продать"))
def sell(m):
    text = m.text.lower()
    if text in ("продать всё","продать все"):
        items = get_inv(m.from_user.id)
        if not items: return bot.reply_to(m, "Нечего продавать")
        coins_total = 0; stars_total = 0
        for row in items:
            it, rar, pr, typ, bg = row
            if typ == "nft": stars_total += int(pr * 0.8)
            else:
                coins_total += pr
                stars_total += RARITIES[rar]["stars"]
        cur.execute("DELETE FROM inventory WHERE tg_id=?",(m.from_user.id,))
        cur.execute("DELETE FROM equipped WHERE tg_id=?",(m.from_user.id,))
        add_coins(m.from_user.id, coins_total)
        add_stars(m.from_user.id, stars_total)
        conn.commit()
        return bot.reply_to(m, f"💰 +{coins_total:,} 🪙, ⭐ +{stars_total} за {len(items)} шт.", parse_mode="HTML")

    p = m.text.split(maxsplit=1)
    if len(p) < 2: return bot.reply_to(m, "продать @user")
    item, typ = parse_item(p[1])
    if owner(item) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого")
    cur.execute("SELECT price, rarity FROM inventory WHERE item=?",(item,))
    price, rar = cur.fetchone()
    kb = types.InlineKeyboardMarkup()
    if typ == "nft":
        stars_gain = int(price * 0.8)
        kb.add(types.InlineKeyboardButton(f"⭐ Продать за {stars_gain:,}", callback_data=f"sellcur:{item}:nft:stars"))
    else:
        kb.add(types.InlineKeyboardButton(f"💰 Продать за {price:,}", callback_data=f"sellcur:{item}:{typ}:coins"))
        star_gain = RARITIES[rar]["stars"]
        if star_gain > 0:
            kb.add(types.InlineKeyboardButton(f"⭐ Продать за {star_gain}", callback_data=f"sellcur:{item}:{typ}:stars"))
    kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="noop"))
    bot.reply_to(m, f"💰 <b>{item}</b> ({rar})\nВыбери валюту:", reply_markup=kb, parse_mode="HTML")

# ==================== БАЛАНС / ТОП / ПРОФИЛЬ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "баланс")
def balance(m):
    bot.reply_to(m, f"💰 <b>{get_coins(m.from_user.id):,}</b> 🪙\n⭐ <b>{get_stars(m.from_user.id)}</b> звёзд", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "топ")
def top(m):
    cur.execute("""SELECT b.tg_id, b.coins, COALESCE(s.amount,0) as stars,
                   (SELECT COUNT(*) FROM inventory WHERE tg_id=b.tg_id AND type='nft') as nfts
                   FROM balances b LEFT JOIN stars s ON s.tg_id=b.tg_id
                   ORDER BY b.coins DESC LIMIT 10""")
    rows = cur.fetchall()
    if not rows: return bot.reply_to(m, "Пусто")
    txt = "🏆 <b>Топ игроков</b>\n\n"
    for i, row in enumerate(rows, 1):
        tid, coins, stars, nfts = row
        name = display_name(tid)
        txt += f"{i}. <b>{name}</b>\n"
        txt += f"   💰 {coins:,} | ⭐ {stars} | 🖼 {nfts}\n"
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
    admin = " 👑" if is_admin(target_id, username_of(target_id)) else ""
    txt = (f"╔════════════════════╗\n║    👤 <b>Профиль</b>\n╚════════════════════╝\n"
           f"🔗 <b>Telegram:</b> {display_name(target_id)}{admin}\n"
           f"💰 <b>Монеты:</b> {coins:,} 🪙\n⭐ <b>Звёзды:</b> {stars}\n"
           f"⭐ Лучший ник: {bu or '—'}\n📱 Лучший номер: {bn or '—'}\n"
           f"🖼 Лучший NFT: {bf or '—'}\n\n"
           f"👤 Ники ({len(users)}/{slots_limit(target_id,'user')}):\n")
    for it, rar, pr, bg in users[:5]:
        txt += f"{RARITIES[rar]['emoji']} {it} — {pr:,} 🪙{' ⭐' if it==bu else ''}\n"
    if len(users) > 5: txt += f"… +{len(users)-5}\n"
    txt += f"\n📱 Номера ({len(numbers)}/{slots_limit(target_id,'number')}):\n"
    for it, rar, pr, bg in numbers[:5]:
        txt += f"{RARITIES[rar]['emoji']} {it} — {pr:,} 🪙{' ⭐' if it==bn else ''}\n"
    if len(numbers) > 5: txt += f"… +{len(numbers)-5}\n"
    txt += f"\n🖼 NFT ({len(nfts)}/{slots_limit(target_id,'nft')}):\n"
    for it, rar, pr, bg in nfts[:3]:
        bg_info = BG_NAMES.get(bg, {"emoji":"⬜"})
        txt += f"{RARITIES[rar]['emoji']} {it}\n   {bg_info['emoji']} {bg} | {pr:,} ⭐{' ⭐ЛУЧШИЙ' if it==bf else ''}\n"
    if len(nfts) > 3: txt += f"… +{len(nfts)-3}\n"
    bot.reply_to(m, txt, parse_mode="HTML")

# ==================== СЛОТЫ ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("слот"))
def slot_cmd(m):
    text = m.text.lower().strip()
    if text in ("слот","слоты"):
        uc = slot_cost(m.from_user.id,"user"); nc = slot_cost(m.from_user.id,"number"); fc = slot_cost(m.from_user.id,"nft")
        return bot.reply_to(m,
            f"📦 <b>Слоты</b>\n\n"
            f"👤 {count_items(m.from_user.id,'user')}/{slots_limit(m.from_user.id,'user')} — <code>слот купить юзы</code> ({uc:,} 🪙)\n"
            f"📱 {count_items(m.from_user.id,'number')}/{slots_limit(m.from_user.id,'number')} — <code>слот купить номера</code> ({nc:,} 🪙)\n"
            f"🖼 {count_items(m.from_user.id,'nft')}/{slots_limit(m.from_user.id,'nft')} — <code>слот купить нфт</code> ({fc:,} 🪙)",
            parse_mode="HTML")
    if text == "слот купить юзы":
        cost = slot_cost(m.from_user.id,"user")
        if get_coins(m.from_user.id) < cost: return bot.reply_to(m, f"❌ {cost:,} 🪙")
        add_coins(m.from_user.id, -cost)
        ub, nb, nbft = get_bought(m.from_user.id)
        cur.execute("UPDATE slots SET ub=? WHERE tg_id=?",(ub+1,m.from_user.id)); conn.commit()
        return bot.reply_to(m, f"✅ Лимит: {slots_limit(m.from_user.id,'user')}")
    if text == "слот купить номера":
        cost = slot_cost(m.from_user.id,"number")
        if get_coins(m.from_user.id) < cost: return bot.reply_to(m, f"❌ {cost:,} 🪙")
        add_coins(m.from_user.id, -cost)
        ub, nb, nbft = get_bought(m.from_user.id)
        cur.execute("UPDATE slots SET nb=? WHERE tg_id=?",(nb+1,m.from_user.id)); conn.commit()
        return bot.reply_to(m, f"✅ Лимит: {slots_limit(m.from_user.id,'number')}")
    if text == "слот купить нфт":
        cost = slot_cost(m.from_user.id,"nft")
        if get_coins(m.from_user.id) < cost: return bot.reply_to(m, f"❌ {cost:,} 🪙")
        add_coins(m.from_user.id, -cost)
        ub, nb, nbft = get_bought(m.from_user.id)
        cur.execute("UPDATE slots SET nbft=? WHERE tg_id=?",(nbft+1,m.from_user.id)); conn.commit()
        return bot.reply_to(m, f"✅ Лимит: {slots_limit(m.from_user.id,'nft')}")
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
    p = m.text.split(maxsplit=1)
    if len(p) < 2: return bot.reply_to(m, "поставить @user / +7777 / NFT")
    item, typ = parse_item(p[1])
    if owner(item) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого")
    if typ=="user": set_eq(m.from_user.id, user=item)
    elif typ=="number": set_eq(m.from_user.id, number=item)
    else: set_eq(m.from_user.id, nft=item)
    bot.reply_to(m, f"⭐ Лучший: {item}")

# ==================== БИРЖА ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "биржа")
def exchange(m):
    cur.execute("SELECT id, seller_id, item, type, rarity, price, currency FROM listings ORDER BY id DESC LIMIT 30")
    rows = cur.fetchall()
    if not rows: return bot.reply_to(m, "🏦 Пусто")
    txt = "🏦 <b>Биржа</b>\n\n"
    for lid, seller, item, typ, rar, price, curr in rows:
        cur_sym = "⭐" if curr=="stars" else "🪙"
        txt += f"<code>#{lid}</code> {RARITIES[rar]['emoji']} {item} — <b>{price:,}</b> {cur_sym} (от {display_name(seller)})\n"
    txt += "\n<code>купить <id></code> / <code>снять <id></code>"
    bot.reply_to(m, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("выставить"))
def list_item(m):
    p = m.text.split(maxsplit=2)
    if len(p) < 3: return bot.reply_to(m, "выставить @user 500")
    item, typ = parse_item(p[1])
    try: price = int(p[2])
    except: return bot.reply_to(m, "Число")
    if price <= 0: return bot.reply_to(m, "> 0")
    if owner(item) != m.from_user.id: return bot.reply_to(m, "Нет такого")
    cur.execute("SELECT rarity FROM inventory WHERE item=?",(item,))
    rar = cur.fetchone()[0]
    cur.execute("DELETE FROM inventory WHERE item=?",(item,))
    clear_eq(m.from_user.id, item)
    curr = "stars" if typ=="nft" else "coins"
    cur.execute("INSERT INTO listings(seller_id,item,type,rarity,price,currency) VALUES(?,?,?,?,?,?)",
                (m.from_user.id, item, typ, rar, price, curr)); conn.commit()
    bot.reply_to(m, f"✅ {item} за {price:,} {'⭐' if curr=='stars' else '🪙'}")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("снять"))
def unlist(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "снять <id>")
    try: lid = int(p[1])
    except: return bot.reply_to(m, "ID — число")
    cur.execute("SELECT seller_id, item, type, rarity, price FROM listings WHERE id=?",(lid,))
    r = cur.fetchone()
    if not r: return bot.reply_to(m, "Лот не найден")
    seller, item, typ, rar, price = r
    if seller != m.from_user.id: return bot.reply_to(m, "Не твой лот")
    if count_items(seller, typ) >= slots_limit(seller, typ): return bot.reply_to(m, "❌ Нет места")
    cur.execute("DELETE FROM listings WHERE id=?",(lid,))
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (seller, item, typ, rar, price)); conn.commit()
    bot.reply_to(m, f"✅ {item} возвращён")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("купить"))
def buy_lot(m):
    text = m.text.lower()
    if text.startswith("купить звёзды"): return
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "купить <id>")
    try: lid = int(p[1])
    except: return bot.reply_to(m, "ID — число")
    cur.execute("SELECT seller_id, item, type, rarity, price, currency FROM listings WHERE id=?",(lid,))
    r = cur.fetchone()
    if not r: return bot.reply_to(m, "Лот не найден")
    seller, item, typ, rar, price, curr = r
    if seller == m.from_user.id: return bot.reply_to(m, "Твой лот")
    if count_items(m.from_user.id, typ) >= slots_limit(m.from_user.id, typ):
        return bot.reply_to(m, "❌ Нет места")
    if curr == "stars":
        if get_stars(m.from_user.id) < price: return bot.reply_to(m, f"❌ {price:,} ⭐")
        add_stars(m.from_user.id, -price); add_stars(seller, price)
    else:
        if get_coins(m.from_user.id) < price: return bot.reply_to(m, f"❌ {price:,} 🪙")
        add_coins(m.from_user.id, -price); add_coins(seller, price)
    cur.execute("DELETE FROM listings WHERE id=?",(lid,))
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",
                (m.from_user.id, item, typ, rar, price)); conn.commit()
    bot.reply_to(m, f"✅ Купил {item} за {price:,} {'⭐' if curr=='stars' else '🪙'}")

# ==================== БОНУС ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower() in ("бонус","ежедневно"))
def daily(m):
    register(m.from_user.id, m.from_user.username)
    cur.execute("SELECT last_claim FROM daily WHERE tg_id=?",(m.from_user.id,))
    r = cur.fetchone()
    now = int(time.time())
    if r and now - r[0] < 86400:
        left = 86400 - (now - r[0]); h, rem = divmod(left, 3600)
        return bot.reply_to(m, f"⏳ Через <b>{h}ч {rem//60}м</b>", parse_mode="HTML")
    reward = random.randint(50, 200)
    add_coins(m.from_user.id, reward)
    msg = f"🎁 +<b>{reward:,}</b> 🪙"
    if random.random() < 0.05:
        add_stars(m.from_user.id, 1)
        msg += "\n⭐ +1 звезда (удача!)"
    cur.execute("INSERT OR REPLACE INTO daily(tg_id,last_claim) VALUES(?,?)",(m.from_user.id,now)); conn.commit()
    bot.reply_to(m, msg + f"\n💰 {get_coins(m.from_user.id):,} 🪙", parse_mode="HTML")

# ==================== АДМИНКА ====================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("админ выдать"))
def admin_give(m):
    if not is_admin(m.from_user.id, m.from_user.username): return bot.reply_to(m, "❌ Нет прав")
    p = m.text.split()
    if len(p) < 4: return bot.reply_to(m, "админ выдать @user 1000")
    try: amount = int(p[3])
    except: return bot.reply_to(m, "Число")
    tid = by_uname(p[2]) if p[2].startswith("@") else (int(p[2]) if p[2].lstrip("-").isdigit() else None)
    if not tid: return bot.reply_to(m, "Не найден")
    add_coins(tid, amount)
    bot.reply_to(m, f"✅ {amount:,} 🪙 → {display_name(tid)}")

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
    bot.reply_to(m, f"✅ {amount} ⭐ → {display_name(tid)}")

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
    cur.execute("INSERT OR REPLACE INTO slots(tg_id,ub,nb,nbft) VALUES(?,?,?,?)",(tid,ub+count,nb+count,nbft+count)); conn.commit()
    bot.reply_to(m, f"✅ +{count} слотов → {display_name(tid)}")

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

@bot.message_handler(func=lambda m: m.text and m.from_user.username)
def track(m):
    register(m.from_user.id, m.from_user.username)

print("Бот запущен...")
bot.infinity_polling(timeout=60, long_polling_timeout=60)