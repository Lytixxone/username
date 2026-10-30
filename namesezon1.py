import sqlite3, re, random, time, telebot
from collections import Counter
from datetime import datetime
from telebot import types

# ==================== ТОКЕН ====================
TOKEN_PART1 = "8650713388:"
TOKEN_PART2 = "AAFbY_4Drg29xAJSYwi1qu7C3x_0q7C3tEY"
bot = telebot.TeleBot(TOKEN_PART1 + TOKEN_PART2)
ADMIN_USERNAMES = {"lytixx"}
ADMIN_IDS = set()

# ==================== СЕЗОН ====================
SEASON_END = datetime(2026, 11, 30, 23, 59, 59)
def season_ended(): return datetime.now() > SEASON_END

def is_admin(tg_id=None, username=None):
    if username and username.lower().lstrip("@") in ADMIN_USERNAMES: return True
    if tg_id and tg_id in ADMIN_IDS: return True
    return False

# ==================== БАЗА ====================
conn = sqlite3.connect("usernames.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(tg_id INTEGER PRIMARY KEY, username TEXT, joined_at INTEGER DEFAULT 0)")
cur.execute("""CREATE TABLE IF NOT EXISTS inventory(
    id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, item TEXT UNIQUE,
    type TEXT, rarity TEXT, price INTEGER)""")
cur.execute("CREATE TABLE IF NOT EXISTS balances(tg_id INTEGER PRIMARY KEY, coins INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS equipped(tg_id INTEGER PRIMARY KEY, best_user TEXT, best_number TEXT, best_nft TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS slots(tg_id INTEGER PRIMARY KEY, ub INTEGER DEFAULT 0, nb INTEGER DEFAULT 0, nbft INTEGER DEFAULT 0)")
cur.execute("""CREATE TABLE IF NOT EXISTS listings(
    id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, item TEXT,
    type TEXT, rarity TEXT, price INTEGER, currency TEXT DEFAULT 'coins')""")
cur.execute("CREATE TABLE IF NOT EXISTS daily(tg_id INTEGER PRIMARY KEY, last_claim INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS stars(tg_id INTEGER PRIMARY KEY, amount INTEGER DEFAULT 0)")
cur.execute("""CREATE TABLE IF NOT EXISTS promo_codes(
    code TEXT PRIMARY KEY, reward_type TEXT, reward_value TEXT,
    max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0, created_at INTEGER)""")
cur.execute("CREATE TABLE IF NOT EXISTS promo_used(tg_id INTEGER, code TEXT, PRIMARY KEY(tg_id, code))")
conn.commit()
for q in [
    "ALTER TABLE equipped ADD COLUMN best_nft TEXT",
    "ALTER TABLE slots ADD COLUMN nbft INTEGER DEFAULT 0",
    "ALTER TABLE listings ADD COLUMN currency TEXT DEFAULT 'coins'",
    "ALTER TABLE users ADD COLUMN joined_at INTEGER DEFAULT 0",
]:
    try: cur.execute(q)
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
    "@tmex":{"rarity":"эпический","fixed":["@mebx","@setx"],"rand":2,"min":"обычный","chance":0.9},
    "@tgsx":{"rarity":"эпический","fixed":["@tgl","@father"],"rand":2,"min":"обычный","chance":0.9},
    "@telegram":{"rarity":"мифический","fixed":["@tmex","@webx"],"rand":3,"min":"эпический","chance":0.6},
    "@botfather":{"rarity":"мифический","fixed":["@botx","@father"],"rand":3,"min":"редкий","chance":0.7},
    "@developer":{"rarity":"мифический","fixed":["@tgl","@botx"],"rand":5,"min":"легендарный","chance":0.5},
    "@tgpremium":{"rarity":"мифический","fixed":["@tgsx","@premium"],"rand":5,"min":"эпический","chance":0.55},
    "@melstroy":{"rarity":"мифический","fixed":["@crow","@free"],"rand":5,"min":"эпический","chance":0.55},
    "@musk":{"rarity":"мифический","fixed":["@tgl","@webx"],"rand":5,"min":"эпический","chance":0.55},
    "@trump":{"rarity":"мифический","fixed":["@botx","@father"],"rand":6,"min":"легендарный","chance":0.5},
    "@putin":{"rarity":"мифический","fixed":["@melstroy","@trump"],"rand":8,"min":"легендарный","chance":0.45},
    "@durov":{"rarity":"мега","fixed":["@crow","@free"],"rand":7,"min":"эпический","chance":0.5},
    "@lytixx":{"rarity":"мега","fixed":[],"rand":10,"min":"эпический","chance":0.5},
}

# ==================== NFT ====================
NFT_TYPES = {
    "IceCream":{"emoji":"🍦","name":"Мороженое","aliases":["icecream","ice","мороженое","айс"],"min_price":500,"max_price":10000,"max_num":999999},
    "MirageLamp":{"emoji":"🪔","name":"Мираж-лампа","aliases":["miragelamp","mirage","лампа","мираж"],"min_price":800,"max_price":20000,"max_num":999999},
    "SnoopDogg":{"emoji":"🐶","name":"Снуп Догг","aliases":["snoopdogg","snoop","снуп","собака"],"min_price":1000,"max_price":100000,"max_num":9999999},
    "PlushPepe":{"emoji":"🐸","name":"Плюш Пепе","aliases":["plushpepe","pepe","пепе","плюш","жаба"],"min_price":1000000,"max_price":10000000,"max_num":3000},
    "ToyBear":{"emoji":"🧸","name":"Мишка","aliases":["toybear","bear","мишка","медведь"],"min_price":3000,"max_price":500000,"max_num":9999999},
    "ResistanceDog":{"emoji":"🐕","name":"Собака сопротивления","aliases":["resistancedog","resistance","сопротивление"],"min_price":50000,"max_price":1500000,"max_num":15000},
    "ScaredCat":{"emoji":"🐈","name":"Испуганный кот","aliases":["scaredcat","cat","кошка","кот"],"min_price":30000,"max_price":1000000,"max_num":19000},
}

def nft_link(item):
    return f'<a href="https://{item}">{item}</a>'

def nft_price(nft_type, num):
    t = NFT_TYPES[nft_type]
    base, cap = t["min_price"], t["max_price"]
    s = str(num); L = len(s)
    len_f = 0.05 if L>=6 else 0.15 if L==5 else 0.35 if L==4 else 0.55 if L==3 else 0.80 if L==2 else 1.0
    cnt = Counter(s).most_common(1)[0][1]
    rep_f = 1.0 if (cnt==L and L>1) else 0.7 if cnt>=3 else 0.4 if cnt>=2 else 0.0
    f = min(1.0, len_f*0.7 + rep_f*0.3)
    return int(base + (cap-base)*f)

def nft_rarity(price):
    if price>=1000000: return "мега"
    if price>=100000: return "мифический"
    if price>=20000: return "легендарный"
    if price>=5000: return "эпический"
    if price>=1000: return "редкий"
    return "обычный"

def parse_nft(text):
    text = text.strip()
    m = re.search(r"([a-zа-яё]+)[\-_\s]?(\d+)", text, re.IGNORECASE)
    if not m: return None
    type_in = m.group(1).lower()
    try: num = int(m.group(2))
    except: return None
    nft_type = None
    for name, t in NFT_TYPES.items():
        if type_in in t["aliases"] or type_in == name.lower():
            nft_type = name; break
    if not nft_type: return None
    if num <= 0 or num > NFT_TYPES[nft_type]["max_num"]:
        return {"error": f"Число 1–{NFT_TYPES[nft_type]['max_num']:,}"}
    price = nft_price(nft_type, num)
    return {"type": nft_type, "num": num, "item": f"t.me/nft/{nft_type}-{num}", "price": price}

# ==================== УТИЛИТЫ ====================
def norm(u): u=u.strip().lower(); return u if u.startswith("@") else "@"+u
def norm_num(s):
    s = re.sub(r"[\s\-()]","",s.strip())
    return s if s.startswith("+") else "+"+s
def rarity_user(u):
    if u in SPECIAL_RARITIES: return SPECIAL_RARITIES[u]
    name = u[1:].lower()
    if not re.fullmatch(r"[a-z]+",name): return "редкий" if len(name)<=3 else "обычный"
    L = len(name)
    return "мифический" if L<=3 else "легендарный" if L<=4 else "эпический" if L<=5 else "редкий" if L<=7 else "обычный"
def rarity_number(num):
    d = re.sub(r"\D","",num)
    if not d: return "обычный"
    c = Counter(d).most_common(1)[0][1]
    return "мифический" if c>=6 else "легендарный" if c>=5 else "эпический" if c>=4 else "редкий" if c>=3 else "обычный"
def price_of(item, rar): return SPECIAL_PRICES.get(item, RARITIES[rar]["price"])
def owner(item):
    cur.execute("SELECT tg_id FROM inventory WHERE item=?",(item,)); r=cur.fetchone(); return r[0] if r else None
def by_uname(u):
    cur.execute("SELECT tg_id FROM users WHERE username=?",(norm(u),)); r=cur.fetchone(); return r[0] if r else None
def get_coins(tg_id):
    cur.execute("SELECT coins FROM balances WHERE tg_id=?",(tg_id,)); r=cur.fetchone()
    if not r:
        cur.execute("INSERT INTO balances(tg_id,coins) VALUES(?,0)",(tg_id,)); conn.commit(); return 0
    return r[0]
def add_coins(tg_id, n):
    cur.execute("INSERT OR IGNORE INTO balances(tg_id,coins) VALUES(?,0)",(tg_id,))
    cur.execute("UPDATE balances SET coins=coins+? WHERE tg_id=?",(n,tg_id)); conn.commit()
def get_stars(tg_id):
    cur.execute("SELECT amount FROM stars WHERE tg_id=?",(tg_id,)); r=cur.fetchone()
    if not r:
        cur.execute("INSERT INTO stars(tg_id,amount) VALUES(?,0)",(tg_id,)); conn.commit(); return 0
    return r[0]
def add_stars(tg_id, n):
    cur.execute("INSERT OR IGNORE INTO stars(tg_id,amount) VALUES(?,0)",(tg_id,))
    cur.execute("UPDATE stars SET amount=amount+? WHERE tg_id=?",(n,tg_id)); conn.commit()
def get_inv(tg_id, typ=None):
    if typ: cur.execute("SELECT item, rarity, price FROM inventory WHERE tg_id=? AND type=?",(tg_id,typ))
    else: cur.execute("SELECT item, rarity, price, type FROM inventory WHERE tg_id=?",(tg_id,))
    return cur.fetchall()
def count_items(tg_id, typ):
    cur.execute("SELECT COUNT(*) FROM inventory WHERE tg_id=? AND type=?",(tg_id,typ)); return cur.fetchone()[0]
def get_bought(tg_id):
    cur.execute("SELECT ub, nb, nbft FROM slots WHERE tg_id=?",(tg_id,)); r=cur.fetchone()
    if not r:
        cur.execute("INSERT INTO slots(tg_id,ub,nb,nbft) VALUES(?,0,0,0)",(tg_id,)); conn.commit(); return 0,0,0
    return r
def slots_limit(tg_id, typ):
    ub, nb, nbft = get_bought(tg_id)
    return 5+5*ub if typ=="user" else 5+5*nb if typ=="number" else 3+3*nbft
def slot_cost(tg_id, typ):
    ub, nb, nbft = get_bought(tg_id)
    return 100*(ub+1) if typ=="user" else 100*(nb+1) if typ=="number" else 500*(nbft+1)
def get_equipped(tg_id):
    cur.execute("SELECT best_user, best_number, best_nft FROM equipped WHERE tg_id=?",(tg_id,))
    return cur.fetchone() or (None,None,None)
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
    cur.execute("SELECT username FROM users WHERE tg_id=?",(tg_id,)); r=cur.fetchone(); return r[0] if r else None
def display_name(tg_id):
    u = username_of(tg_id)
    if not u: return f"ID {tg_id}"
    return f"✅ {u}" if u.lower().lstrip("@") in ADMIN_USERNAMES else u
def parse_item(arg):
    if arg.startswith("+"): return norm_num(arg), "number"
    if re.fullmatch(r"\d{5,15}", arg): return norm_num(arg), "number"
    nft = parse_nft(arg)
    if nft and "error" not in nft: return nft["item"], "nft"
    return norm(arg), "user"
def register(tg_id, username):
    if username:
        cur.execute("INSERT OR IGNORE INTO users(tg_id,username,joined_at) VALUES(?,?,?)",(tg_id,norm(username),int(time.time())))
        cur.execute("UPDATE users SET username=? WHERE tg_id=?",(norm(username),tg_id))
        conn.commit()

# ==================== АНИМАЦИЯ ====================
def drop_animation(chat_id, reply_to_id, final_text, rarity):
    if rarity in ("мега","мифический"):
        frames = [("🎰 |",0.2),("🎰 /",0.2),("🎰 —",0.2),("🎰 \\",0.2),("✨✨✨",0.3)]
    elif rarity in ("легендарный","эпический"):
        frames = [("🎰 ...",0.25),("✨",0.3)]
    else:
        bot.send_message(chat_id, final_text, parse_mode="HTML", reply_to_message_id=reply_to_id); return
    msg = bot.send_message(chat_id, frames[0][0])
    for t,d in frames[1:]:
        time.sleep(d)
        try: bot.edit_message_text(t, chat_id, msg.message_id)
        except: pass
    time.sleep(0.3)
    try: bot.edit_message_text(final_text, chat_id, msg.message_id, parse_mode="HTML")
    except: bot.send_message(chat_id, final_text, parse_mode="HTML")

# ==================== ИНВЕНТАРЬ ====================
def build_inv_page(tg_id, typ, page):
    items = get_inv(tg_id, typ)
    total = len(items)
    ps = 1 if typ=="nft" else 8
    pages = max(1, (total+ps-1)//ps)
    page = max(0, min(page, pages-1))
    chunk = items[page*ps:(page+1)*ps]
    titles = {"user":"👤 Ники","number":"📱 Номера","nft":"🖼 NFT"}
    txt = f"<b>{titles[typ]}</b> ({total}/{slots_limit(tg_id,typ)}) — стр. {page+1}/{pages}\n\n"
    if not chunk: txt += "пусто"
    else:
        for row in chunk:
            if typ=="nft":
                it, rar, price = row
                txt += f"{RARITIES[rar]['emoji']} <b>{nft_link(it)}</b>\n   {rar} | {price:,} ⭐\n"
            else:
                it, rar, price = row
                txt += f"{RARITIES[rar]['emoji']} {it} — {rar} ({price:,} 🪙)\n"
    return txt, page, pages

def inv_keyboard(owner_id, typ, page, pages):
    kb = types.InlineKeyboardMarkup()
    row = []
    if page > 0: row.append(types.InlineKeyboardButton("◀", callback_data=f"inv:{owner_id}:{typ}:{page-1}"))
    row.append(types.InlineKeyboardButton(f"{page+1}/{pages}", callback_data="noop"))
    if page < pages-1: row.append(types.InlineKeyboardButton("▶", callback_data=f"inv:{owner_id}:{typ}:{page+1}"))
    kb.row(*row)
    other = {"user":"number","number":"nft","nft":"user"}[typ]
    names = {"user":"👤 Ники","number":"📱 Номера","nft":"🖼 NFT"}
    kb.row(types.InlineKeyboardButton(names[other], callback_data=f"inv:{owner_id}:{other}:0"))
    return kb

# ==================== МЕНЮ ====================
MENU_PAGES = [
    {"title":"🎒 КОЛЛЕКЦИЯ","lines":[
        "• <code>взять @user</code> — ник",
        "• <code>номер +7777</code> — номер",
        "• <code>инвентарь</code> — листать",
        "• <code>поставить @user</code> — лучший",
        "• <code>дать @user</code> — ответом",
    ]},
    {"title":"🖼 NFT","lines":[
        "• <code>нфт пепе-100</code>",
        "• <code>нфт icecream-7</code>",
        "• <code>нфт t.me/nft/ScaredCat-2467</code>",
        "• <code>каталог нфт</code>",
        "",
        "7 типов: мороженое, лампа, снуп, пепе, мишка, собака, кошка",
        "💡 Цена: короче число + повторы (777)",
    ]},
    {"title":"⭐ ЗВЁЗДЫ","lines":[
        "• <code>мои звёзды</code> — баланс",
        "• Только с продажи ников и NFT",
        "",
        "🟣 50 ⭐ | 🟡 100 ⭐ | 🔴 300 ⭐ | 💎 1000 ⭐",
    ]},
    {"title":"🛠 КРАФТ","lines":[
        "• <code>крафт</code> — рецепты",
        "• <code>крафт @durov</code> — крафт",
        "• Шанс 45–90%",
    ]},
    {"title":"💰 ПРОДАЖА","lines":[
        "• <code>продать @user</code> — валюта на выбор",
        "• <code>продать icecream-7</code>",
        "• <code>продать всё</code>",
        "",
        "🏦 <b>БИРЖА:</b>",
        "• <code>биржа</code>",
        "• <code>выставить @user 500</code>",
        "• <code>купить <id></code>",
    ]},
    {"title":"📦 ЭКОНОМИКА","lines":[
        "• <code>бонус</code> — 50–200 🪙",
        "• <code>баланс</code> — всё",
        "• <code>топ</code> — рейтинг",
        "• <code>слот</code> — инфо",
        "• <code>слот купить юзы</code> — +5",
        "• <code>слот купить номера</code> — +5",
        "• <code>слот купить нфт</code> — +3",
        "• <code>промо КОД</code> — активировать",
    ]},
    {"title":"👑 АДМИНКА","lines":[
        "• <code>админ выдать @user 1000</code>",
        "• <code>админ звезда @user 10</code>",
        "• <code>админ слот @user 5</code>",
        "• <code>создать промо</code> (в ЛС)",
        "• <code>админ топ</code>",
    ]},
]

def build_menu(page=0):
    page = max(0, min(page, len(MENU_PAGES)-1))
    p = MENU_PAGES[page]
    text = f"📋 <b>Меню</b> — {page+1}/{len(MENU_PAGES)}\n\n<b>{p['title']}</b>\n" + "\n".join(p["lines"])
    kb = types.InlineKeyboardMarkup()
    row = []
    if page > 0: row.append(types.InlineKeyboardButton("◀ Назад", callback_data=f"menu:{page-1}"))
    row.append(types.InlineKeyboardButton(f"{page+1}/{len(MENU_PAGES)}", callback_data="noop"))
    if page < len(MENU_PAGES)-1: row.append(types.InlineKeyboardButton("Далее ▶", callback_data=f"menu:{page+1}"))
    kb.row(*row)
    nav = []
    for i in range(len(MENU_PAGES)):
        nav.append(types.InlineKeyboardButton(str(i+1), callback_data=f"menu:{i}"))
    kb.row(*nav)
    return text, kb

# ==================== ПРОМОКОДЫ ====================
promo_state = {}

def promo_start(chat_id):
    promo_state[chat_id] = {"step":"code","data":{}}
    bot.send_message(chat_id, "🎟 <b>Создание промокода</b>\n\nВведи название кода (латиница/цифры, без пробелов):", parse_mode="HTML")

def promo_type_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("💰 Валюта", callback_data="ptype:coins"))
    kb.row(types.InlineKeyboardButton("⭐ Звёзды", callback_data="ptype:stars"))
    kb.row(types.InlineKeyboardButton("🖼 NFT", callback_data="ptype:nft"))
    kb.row(types.InlineKeyboardButton("📱 Номер", callback_data="ptype:number"))
    kb.row(types.InlineKeyboardButton("👤 Юзы", callback_data="ptype:user"))
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="noop"))
    return kb

def promo_nft_keyboard():
    kb = types.InlineKeyboardMarkup()
    for name in NFT_TYPES:
        kb.row(types.InlineKeyboardButton(f"{NFT_TYPES[name]['emoji']} {name}", callback_data=f"pnft:{name}"))
    kb.row(types.InlineKeyboardButton("🎲 Рандом", callback_data="pnft:random"))
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="noop"))
    return kb

# ==================== ХЕНДЛЕРЫ ====================
@bot.message_handler(commands=["start"])
def start(m):
    register(m.from_user.id, m.from_user.username)
    if season_ended() and not is_admin(m.from_user.id, m.from_user.username):
        bot.reply_to(m, "🎉 <b>Сезон 1 закончился!</b>\n\nСкоро будет загружена обнова — сезон 2.\n\nПока доступно:\n• <code>стата</code>\n• <code>обнова</code>", parse_mode="HTML")
        return
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📋 Меню", callback_data="menu:0"))
    bot.reply_to(m, "👋 Привет!\nНажми кнопку или пиши <code>команды</code>.", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "noop")
def cb_noop(call): bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("menu:"))
def cb_menu(call):
    bot.answer_callback_query(call.id)
    try: page = int(call.data.split(":")[1])
    except: return
    text, kb = build_menu(page)
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        if "not modified" in str(e).lower(): return
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("inv:"))
def cb_inv(call):
    parts = call.data.split(":")
    owner_id = int(parts[1]); typ = parts[2]; page = int(parts[3])
    if call.from_user.id != owner_id:
        return bot.answer_callback_query(call.id, "Не твой", show_alert=True)
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
    cur.execute("SELECT price, rarity FROM inventory WHERE item=?",(item,)); price, rar = cur.fetchone()
    cur.execute("DELETE FROM inventory WHERE item=?",(item,)); clear_eq(call.from_user.id, item)
    if currency == "coins":
        add_coins(call.from_user.id, price); result = f"💰 +{price:,} 🪙"
    else:
        if typ == "nft": gain = int(price*0.8); add_stars(call.from_user.id, gain); result = f"⭐ +{gain:,}"
        else:
            gain = RARITIES[rar]["stars"]
            if gain == 0: return bot.answer_callback_query(call.id, "Нельзя за ⭐", show_alert=True)
            add_stars(call.from_user.id, gain); result = f"⭐ +{gain}"
    conn.commit()
    title = nft_link(item) if typ=="nft" else item
    bot.edit_message_text(f"✅ Продал <b>{title}</b> ({rar})\n{result}", call.message.chat.id, call.message.message_id, parse_mode="HTML")
    bot.answer_callback_query(call.id)

# ============ ПРОМО шаги ============
@bot.callback_query_handler(func=lambda c: c.data.startswith("ptype:"))
def cb_ptype(call):
    chat = call.message.chat.id
    if chat not in promo_state: return bot.answer_callback_query(call.id)
    typ = call.data.split(":")[1]
    promo_state[chat]["data"]["reward_type"] = typ
    if typ == "nft":
        promo_state[chat]["step"] = "nfttype"
        bot.edit_message_text("Выбери тип NFT:", chat, call.message.message_id, reply_markup=promo_nft_keyboard())
    elif typ in ("coins","stars"):
        promo_state[chat]["step"] = "value"
        unit = "монет" if typ=="coins" else "звёзд"
        bot.edit_message_text(f"Введи количество {unit}:", chat, call.message.message_id)
    else:
        promo_state[chat]["step"] = "uses"
        promo_state[chat]["data"]["reward_value"] = "random"
        bot.edit_message_text("Сколько активаций?", chat, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pnft:"))
def cb_pnft(call):
    chat = call.message.chat.id
    if chat not in promo_state: return bot.answer_callback_query(call.id)
    nft = call.data.split(":")[1]
    promo_state[chat]["data"]["reward_value"] = nft
    promo_state[chat]["step"] = "uses"
    bot.edit_message_text("Сколько активаций?", chat, call.message.message_id)
    bot.answer_callback_query(call.id)

# ============ ОБЩИЕ КОМАНДЫ ============
@bot.message_handler(func=lambda m: m.text and m.text.lower() in ("команды","меню"))
def commands(m):
    text, kb = build_menu(0)
    bot.reply_to(m, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "обнова")
def updates(m):
    txt = (
        "📢 <b>Список обновлений</b>\n\n"
        "<b>v2.0 — Сезон 1</b>\n"
        "• 🖼 Система NFT (7 типов)\n"
        "• 🏦 Биржа NFT\n"
        "• ⭐ Звёзды за продажу ников\n"
        "• 🎟 Промокоды\n"
        "• 💱 Выбор валюты при продаже\n"
        "• 🔗 Кликабельные ссылки на NFT\n"
        "• 📄 Постраничный инвентарь\n"
        "• 🏆 Топ с полной статистикой\n\n"
        "<b>v1.5</b>\n"
        "• ❌ Убраны гифты\n"
        "• 🛠 Крафты (12 рецептов)\n"
        "• 🏦 Биржа\n"
        "• 📅 Бонус\n\n"
        "<b>v1.0</b>\n"
        "• 🚀 Запуск бота\n"
        "• 💎 Система редкостей\n"
        "• 👤 Взять ники и номера"
    )
    bot.reply_to(m, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "стата")
def stats(m):
    tg_id = m.from_user.id
    register(tg_id, m.from_user.username)
    cur.execute("SELECT joined_at FROM users WHERE tg_id=?",(tg_id,))
    r = cur.fetchone()
    joined = r[0] if r and r[0] else int(time.time())
    days = max(1, (int(time.time()) - joined) // 86400)
    users = get_inv(tg_id, "user")
    numbers = get_inv(tg_id, "number")
    nfts = get_inv(tg_id, "nft")
    bu, bn, bf = get_equipped(tg_id)
    coins = get_coins(tg_id)
    stars = get_stars(tg_id)
    xp = getattr(getattr(bot, "_xp", None), "get", lambda *_: 0)  # заглушка
    txt = (
        f"📊 <b>Статистика игрока</b>\n\n"
        f"👤 <b>{display_name(tg_id)}</b>\n"
        f"📅 Дней в игре: <b>{days}</b>\n"
        f"💰 Монеты: <b>{coins:,}</b> 🪙\n"
        f"⭐ Звёзды: <b>{stars}</b>\n\n"
        f"🎒 <b>Коллекция:</b>\n"
        f"• Ники: {len(users)}/{slots_limit(tg_id,'user')}\n"
        f"• Номера: {len(numbers)}/{slots_limit(tg_id,'number')}\n"
        f"• NFT: {len(nfts)}/{slots_limit(tg_id,'nft')}\n\n"
        f"⭐ Лучший ник: {bu or '—'}\n"
        f"📱 Лучший номер: {bn or '—'}\n"
        f"🖼 Лучший NFT: {nft_link(bf) if bf else '—'}\n\n"
        f"🎉 Сезон закончится: <b>30.11.2026</b>"
    )
    bot.reply_to(m, txt, parse_mode="HTML")

# ============ ПРОМО ДЛЯ ИГРОКОВ ============
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("промо "))
def use_promo(m):
    tg_id = m.from_user.id
    register(tg_id, m.from_user.username)
    code = m.text.split(maxsplit=1)[1].strip().upper()
    cur.execute("SELECT reward_type, reward_value, max_uses, used_count FROM promo_codes WHERE code=?",(code,))
    r = cur.fetchone()
    if not r: return bot.reply_to(m, "❌ Промокод не найден")
    rtype, rvalue, mx, used = r
    if used >= mx: return bot.reply_to(m, "❌ Промокод закончился")
    cur.execute("SELECT 1 FROM promo_used WHERE tg_id=? AND code=?",(tg_id,code))
    if cur.fetchone(): return bot.reply_to(m, "❌ Ты уже активировал")
    # Выдаём
    msg = "🎁 <b>Промокод активирован!</b>\n"
    if rtype == "coins":
        add_coins(tg_id, int(rvalue)); msg += f"💰 +{int(rvalue):,} 🪙"
    elif rtype == "stars":
        add_stars(tg_id, int(rvalue)); msg += f"⭐ +{int(rvalue)}"
    elif rtype == "nft":
        nft_type = rvalue
        if nft_type == "random": nft_type = random.choice(list(NFT_TYPES.keys()))
        if nft_type not in NFT_TYPES: return bot.reply_to(m, "❌ Ошибка промокода")
        mx_num = NFT_TYPES[nft_type]["max_num"]
        for _ in range(20):
            num = random.randint(1, min(9999, mx_num))
            item = f"t.me/nft/{nft_type}-{num}"
            if not owner(item): break
        else: return bot.reply_to(m, "❌ Не удалось выдать NFT")
        price = nft_price(nft_type, num); rar = nft_rarity(price)
        if count_items(tg_id, "nft") >= slots_limit(tg_id, "nft"):
            return bot.reply_to(m, "❌ Нет места для NFT")
        cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",(tg_id,item,"nft",rar,price))
        msg += f"🖼 {nft_link(item)} ({price:,} ⭐)"
    elif rtype == "number":
        for _ in range(20):
            num = "+7" + "".join([str(random.randint(0,9)) for _ in range(10)])
            if not owner(num): break
        else: return bot.reply_to(m, "❌ Не удалось выдать номер")
        rar = rarity_number(num); price = RARITIES[rar]["price"]
        if count_items(tg_id, "number") >= slots_limit(tg_id, "number"):
            return bot.reply_to(m, "❌ Нет места для номера")
        cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",(tg_id,num,"number",rar,price))
        msg += f"📱 {num}"
    elif rtype == "user":
        pool = ["@test","@player","@winner","@lucky","@cool","@pro","@star"]
        for _ in range(20):
            u = random.choice(pool) + str(random.randint(1,99))
            if not owner(u): break
        else: return bot.reply_to(m, "❌ Не удалось выдать юз")
        rar = rarity_user(u); price = price_of(u, rar)
        if count_items(tg_id, "user") >= slots_limit(tg_id, "user"):
            return bot.reply_to(m, "❌ Нет места для ника")
        cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",(tg_id,u,"user",rar,price))
        msg += f"👤 {u}"
    cur.execute("UPDATE promo_codes SET used_count=used_count+1 WHERE code=?",(code,))
    cur.execute("INSERT INTO promo_used(tg_id,code) VALUES(?,?)",(tg_id,code))
    conn.commit()
    bot.reply_to(m, msg, parse_mode="HTML")

# ============ МАСТЕР ПРОМО (админ, ЛС) ============
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "создать промо")
def create_promo(m):
    if m.chat.type != "private": return
    if not is_admin(m.from_user.id, m.from_user.username): return bot.reply_to(m, "❌ Только админ")
    promo_start(m.chat.id)

@bot.message_handler(func=lambda m: m.chat.id in promo_state and m.chat.type == "private")
def promo_input(m):
    st = promo_state[m.chat.id]
    step = st["step"]
    data = st["data"]
    text = (m.text or "").strip()
    if step == "code":
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", text):
            return bot.reply_to(m, "❌ Латиница/цифры, 3–20 символов. Попробуй ещё:")
        data["code"] = text.upper()
        st["step"] = "type"
        bot.reply_to(m, f"Код: <b>{data['code']}</b>\n\nЧто выдаёт?", parse_mode="HTML", reply_markup=promo_type_keyboard())
    elif step == "value":
        try: v = int(text)
        except: return bot.reply_to(m, "Число")
        if v <= 0: return bot.reply_to(m, "> 0")
        data["reward_value"] = str(v)
        st["step"] = "uses"
        bot.reply_to(m, "Сколько активаций?")
    elif step == "uses":
        try: u = int(text)
        except: return bot.reply_to(m, "Число")
        if u <= 0: return bot.reply_to(m, "> 0")
        cur.execute("INSERT INTO promo_codes(code,reward_type,reward_value,max_uses,used_count,created_at) VALUES(?,?,?,?,0,?)",
                    (data["code"], data["reward_type"], data["reward_value"], u, int(time.time())))
        conn.commit()
        bot.reply_to(m, f"✅ <b>Промокод создан!</b>\n\nКод: <code>{data['code']}</code>\nТип: {data['reward_type']}\nЗначение: {data['reward_value']}\nАктиваций: {u}", parse_mode="HTML")
        promo_state.pop(m.chat.id, None)

# ============ СЕЗОН-БЛОКИРОВЩИК ============
@bot.message_handler(func=lambda m: season_ended() and m.text and not is_admin(m.from_user.id, m.from_user.username)
                     and m.text.lower().split()[0] not in ("стата","обнова","команды","меню","start","/start"), content_types=['text'])
def season_block(m):
    bot.reply_to(m, "🎉 <b>Сезон 1 закончился!</b>\n\nСкоро будет загружена обнова — сезон 2.\n\nДоступно:\n• <code>стата</code>\n• <code>обнова</code>", parse_mode="HTML")

# ============ ВЗЯТЬ / НОМЕР / ДАТЬ ============
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("взять"))
def take(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "взять @user")
    u = norm(p[1])
    if not re.fullmatch(r"@[a-z0-9_]{3,32}", u): return bot.reply_to(m, "Плохой юз")
    if u in CRAFT_TARGETS: return bot.reply_to(m, f"❌ {u} только крафт", parse_mode="HTML")
    if owner(u): return bot.reply_to(m, "Занят")
    if count_items(m.from_user.id, "user") >= slots_limit(m.from_user.id, "user"):
        return bot.reply_to(m, "❌ Лимит. <code>слот купить юзы</code>", parse_mode="HTML")
    rar = rarity_user(u); price = price_of(u, rar)
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",(m.from_user.id,u,"user",rar,price)); conn.commit()
    drop_animation(m.chat.id, m.message_id, f"✅ <b>{u}</b> твой!\n{RARITIES[rar]['emoji']} <b>{rar}</b> — {price:,} 🪙", rar)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("номер"))
def take_number(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "номер +77777777777")
    num = norm_num(p[1])
    if not re.fullmatch(r"\+[0-9]{5,15}", num): return bot.reply_to(m, "Формат: +77777777777")
    if owner(num): return bot.reply_to(m, "Занят")
    if count_items(m.from_user.id, "number") >= slots_limit(m.from_user.id, "number"):
        return bot.reply_to(m, "❌ Лимит. <code>слот купить номера</code>", parse_mode="HTML")
    rar = rarity_number(num); price = RARITIES[rar]["price"]
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",(m.from_user.id,num,"number",rar,price)); conn.commit()
    drop_animation(m.chat.id, m.message_id, f"✅ <b>{num}</b> твой!\n{RARITIES[rar]['emoji']} <b>{rar}</b> — {price:,} 🪙", rar)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("дать"))
def give(m):
    p = m.text.split(maxsplit=1)
    if len(p) < 2: return bot.reply_to(m, "дать @user / +7777 / NFT (ответом)")
    item, typ = parse_item(p[1])
    if owner(item) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого")
    if m.reply_to_message: target = m.reply_to_message.from_user.id
    elif typ == "user": target = by_uname(p[1])
    else: return bot.reply_to(m, "Только ответом на сообщение")
    if not target: return bot.reply_to(m, "Ответь на сообщение")
    if count_items(target, typ) >= slots_limit(target, typ): return bot.reply_to(m, "У получателя нет места")
    cur.execute("UPDATE inventory SET tg_id=? WHERE item=?",(target,item)); conn.commit()
    bot.reply_to(m, f"➡️ {item} передан")

# ============ NFT ============
@bot.message_handler(func=lambda m: m.text and (m.text.lower().startswith("нфт ") or m.text.lower().startswith("nft ")))
def take_nft(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split(maxsplit=1)
    if len(p) < 2: return bot.reply_to(m, "<code>нфт пепе-100</code>\n<code>нфт t.me/nft/ScaredCat-2467</code>", parse_mode="HTML")
    nft = parse_nft(p[1])
    if not nft: return bot.reply_to(m, "❌ Формат: <code>нфт пепе-100</code>", parse_mode="HTML")
    if "error" in nft: return bot.reply_to(m, f"❌ {nft['error']}", parse_mode="HTML")
    item = nft["item"]
    if owner(item): return bot.reply_to(m, f"❌ {nft_link(item)} занят", parse_mode="HTML")
    if count_items(m.from_user.id, "nft") >= slots_limit(m.from_user.id, "nft"):
        return bot.reply_to(m, f"❌ Лимит. <code>слот купить нфт</code>", parse_mode="HTML")
    price = nft["price"]
    if get_stars(m.from_user.id) < price:
        return bot.reply_to(m, f"❌ Нужно <b>{price:,} ⭐</b> (у тебя {get_stars(m.from_user.id)})", parse_mode="HTML")
    add_stars(m.from_user.id, -price)
    rar = nft_rarity(price)
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",(m.from_user.id,item,"nft",rar,price)); conn.commit()
    drop_animation(m.chat.id, m.message_id, f"🖼 <b>NFT!</b>\n\n{RARITIES[rar]['emoji']} <b>{rar}</b>\n{nft_link(item)}\n💸 {price:,} ⭐\n⭐ Осталось: {get_stars(m.from_user.id)}", rar)

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "каталог нфт")
def nft_catalog(m):
    txt = "🖼 <b>Каталог NFT</b>\n\n"
    for name, t in NFT_TYPES.items():
        txt += f"{t['emoji']} <b>{name}</b> ({t['name']})\n"
        txt += f"   {t['min_price']:,}–{t['max_price']:,} ⭐ | макс {t['max_num']:,}\n"
        txt += f"   {nft_link(f't.me/nft/{name}-7')}\n\n"
    bot.reply_to(m, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "цены")
def prices(m):
    bot.reply_to(m,
        "💸 <b>Продажа</b>\n\n⚪ 100🪙 | 🔵 500🪙 | 🟣 2000🪙/50⭐ | 🟡 10000🪙/100⭐ | 🔴 50000🪙/300⭐ | 💎 99M🪙/1000⭐\n\n"
        "<b>NFT (⭐):</b> мороженое 500–10k | лампа 800–20k | снуп 1k–100k | пепе 1M–10M | мишка 3k–500k | собака 50k–1.5M | кошка 30k–1M",
        parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower() in ("мои звёзды","звёзды","⭐"))
def my_stars(m):
    bot.reply_to(m, f"⭐ <b>{get_stars(m.from_user.id)}</b>\n💰 {get_coins(m.from_user.id):,} 🪙", parse_mode="HTML")

# ============ КРАФТ ============
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("крафт"))
def craft(m):
    register(m.from_user.id, m.from_user.username)
    p = m.text.split()
    if len(p) < 2:
        txt = "🛠 <b>Рецепты</b>\n\n"
        for t, r in RECIPES.items():
            txt += f"<b>{t}</b> ({RARITIES[r['rarity']]['emoji']} {int(r['chance']*100)}%)\n"
            if r["fixed"]: txt += f"  • {', '.join(r['fixed'])}\n"
            txt += f"  • +{r['rand']} ({r['min']}+)\n"
        return bot.reply_to(m, txt, parse_mode="HTML")
    target = norm(p[1])
    recipe = RECIPES.get(target)
    if not recipe: return bot.reply_to(m, "❌ Нет рецепта")
    if owner(target) == m.from_user.id: return bot.reply_to(m, "Уже есть")
    if owner(target): return bot.reply_to(m, "❌ Занят")
    for f in recipe["fixed"]:
        cur.execute("SELECT 1 FROM inventory WHERE tg_id=? AND item=?",(m.from_user.id,f))
        if not cur.fetchone(): return bot.reply_to(m, f"❌ Нет: {f}")
    order = ["обычный","редкий","эпический","легендарный","мифический","мега"]
    allowed = set(order[order.index(recipe["min"]):])
    exclude = set(recipe["fixed"]) | set(CRAFT_TARGETS)
    cur.execute("SELECT item, rarity FROM inventory WHERE tg_id=? AND type='user'",(m.from_user.id,))
    cand = [i for i,r in cur.fetchall() if r in allowed and i not in exclude]
    if len(cand) < recipe["rand"]: return bot.reply_to(m, f"❌ Нужно {recipe['rand']} юзов {recipe['min']}+")
    rand = random.sample(cand, recipe["rand"])
    all_comp = recipe["fixed"] + rand
    for c in all_comp:
        cur.execute("DELETE FROM inventory WHERE item=?",(c,)); clear_eq(m.from_user.id, c)
    conn.commit()
    if random.random() < recipe["chance"]:
        rar = recipe["rarity"]; price = price_of(target, rar)
        cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",(m.from_user.id,target,"user",rar,price)); conn.commit()
        drop_animation(m.chat.id, m.message_id, f"✨ <b>УСПЕХ!</b>\n\n{RARITIES[rar]['emoji']} <b>{rar}</b>\n<b>{target}</b>\n💰 {price:,} 🪙", rar)
    else:
        bot.reply_to(m, f"💀 <b>ПРОВАЛ</b>\n🔥 Сгорело: {', '.join(all_comp)}", parse_mode="HTML")

# ============ ПРОДАЖА ============
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("продать"))
def sell(m):
    if m.text.lower() in ("продать всё","продать все"):
        items = get_inv(m.from_user.id)
        if not items: return bot.reply_to(m, "Нечего продавать")
        c = 0; s = 0
        for it, rar, pr, typ in items:
            if typ == "nft": s += int(pr*0.8)
            else: c += pr; s += RARITIES[rar]["stars"]
        cur.execute("DELETE FROM inventory WHERE tg_id=?",(m.from_user.id,))
        cur.execute("DELETE FROM equipped WHERE tg_id=?",(m.from_user.id,))
        add_coins(m.from_user.id, c); add_stars(m.from_user.id, s)
        conn.commit()
        return bot.reply_to(m, f"💰 +{c:,} 🪙, ⭐ +{s} за {len(items)} шт.", parse_mode="HTML")
    p = m.text.split(maxsplit=1)
    if len(p) < 2: return bot.reply_to(m, "продать @user")
    item, typ = parse_item(p[1])
    if owner(item) != m.from_user.id: return bot.reply_to(m, "У тебя нет такого")
    cur.execute("SELECT price, rarity FROM inventory WHERE item=?",(item,)); price, rar = cur.fetchone()
    kb = types.InlineKeyboardMarkup()
    if typ == "nft":
        sg = int(price*0.8)
        kb.add(types.InlineKeyboardButton(f"⭐ Продать за {sg:,}", callback_data=f"sellcur:{item}:nft:stars"))
        title = nft_link(item)
    else:
        kb.add(types.InlineKeyboardButton(f"💰 Продать за {price:,}", callback_data=f"sellcur:{item}:{typ}:coins"))
        sg = RARITIES[rar]["stars"]
        if sg > 0: kb.add(types.InlineKeyboardButton(f"⭐ Продать за {sg}", callback_data=f"sellcur:{item}:{typ}:stars"))
        title = item
    kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="noop"))
    bot.reply_to(m, f"💰 <b>{title}</b> ({rar})\nВалюта:", reply_markup=kb, parse_mode="HTML")

# ============ БАЛАНС / ТОП / ПРОФИЛЬ ============
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "баланс")
def balance(m):
    bot.reply_to(m, f"💰 <b>{get_coins(m.from_user.id):,}</b> 🪙\n⭐ <b>{get_stars(m.from_user.id)}</b>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "топ")
def top(m):
    cur.execute("""SELECT b.tg_id, b.coins, COALESCE(s.amount,0),
                   (SELECT COUNT(*) FROM inventory WHERE tg_id=b.tg_id AND type='nft')
                   FROM balances b LEFT JOIN stars s ON s.tg_id=b.tg_id ORDER BY b.coins DESC LIMIT 10""")
    rows = cur.fetchall()
    if not rows: return bot.reply_to(m, "Пусто")
    txt = "🏆 <b>Топ игроков</b>\n\n"
    for i, row in enumerate(rows, 1):
        tid, c, s, n = row
        txt += f"{i}. <b>{display_name(tid)}</b>\n   💰 {c:,} | ⭐ {s} | 🖼 {n}\n"
    bot.reply_to(m, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("профиль"))
def profile(m):
    p = m.text.split(); target_id = m.from_user.id
    if len(p) >= 2:
        t = by_uname(p[1])
        if not t: return bot.reply_to(m, "Не найден")
        target_id = t
    elif m.reply_to_message: target_id = m.reply_to_message.from_user.id
    coins = get_coins(target_id); stars = get_stars(target_id)
    bu, bn, bf = get_equipped(target_id)
    users = get_inv(target_id, "user"); numbers = get_inv(target_id, "number"); nfts = get_inv(target_id, "nft")
    admin = " 👑" if is_admin(target_id, username_of(target_id)) else ""
    txt = (f"👤 <b>Профиль</b>\n\n"
           f"🔗 {display_name(target_id)}{admin}\n💰 {coins:,} 🪙\n⭐ {stars}\n\n"
           f"⭐ Лучший ник: {bu or '—'}\n📱 Лучший номер: {bn or '—'}\n🖼 Лучший NFT: {nft_link(bf) if bf else '—'}\n\n"
           f"👤 Ники ({len(users)}/{slots_limit(target_id,'user')}):\n")
    for it, rar, pr in users[:5]:
        txt += f"{RARITIES[rar]['emoji']} {it} — {pr:,} 🪙{' ⭐' if it==bu else ''}\n"
    if len(users) > 5: txt += f"… +{len(users)-5}\n"
    txt += f"\n📱 Номера ({len(numbers)}/{slots_limit(target_id,'number')}):\n"
    for it, rar, pr in numbers[:5]:
        txt += f"{RARITIES[rar]['emoji']} {it} — {pr:,} 🪙{' ⭐' if it==bn else ''}\n"
    if len(numbers) > 5: txt += f"… +{len(numbers)-5}\n"
    txt += f"\n🖼 NFT ({len(nfts)}/{slots_limit(target_id,'nft')}):\n"
    for it, rar, pr in nfts[:3]:
        txt += f"{RARITIES[rar]['emoji']} {nft_link(it)} — {pr:,} ⭐{' ⭐ЛУЧШИЙ' if it==bf else ''}\n"
    if len(nfts) > 3: txt += f"… +{len(nfts)-3}\n"
    bot.reply_to(m, txt, parse_mode="HTML")

# ============ СЛОТЫ ============
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("слот"))
def slot_cmd(m):
    text = m.text.lower().strip()
    if text in ("слот","слоты"):
        return bot.reply_to(m,
            f"📦 <b>Слоты</b>\n\n"
            f"👤 {count_items(m.from_user.id,'user')}/{slots_limit(m.from_user.id,'user')} — <code>слот купить юзы</code> ({slot_cost(m.from_user.id,'user'):,} 🪙)\n"
            f"📱 {count_items(m.from_user.id,'number')}/{slots_limit(m.from_user.id,'number')} — <code>слот купить номера</code> ({slot_cost(m.from_user.id,'number'):,} 🪙)\n"
            f"🖼 {count_items(m.from_user.id,'nft')}/{slots_limit(m.from_user.id,'nft')} — <code>слот купить нфт</code> ({slot_cost(m.from_user.id,'nft'):,} 🪙)",
            parse_mode="HTML")
    for t, field in [("слот купить юзы","user"),("слот купить номера","number"),("слот купить нфт","nft")]:
        if text == t:
            cost = slot_cost(m.from_user.id, field)
            if get_coins(m.from_user.id) < cost: return bot.reply_to(m, f"❌ {cost:,} 🪙")
            add_coins(m.from_user.id, -cost)
            ub, nb, nbft = get_bought(m.from_user.id)
            if field=="user": cur.execute("UPDATE slots SET ub=? WHERE tg_id=?",(ub+1,m.from_user.id))
            elif field=="number": cur.execute("UPDATE slots SET nb=? WHERE tg_id=?",(nb+1,m.from_user.id))
            else: cur.execute("UPDATE slots SET nbft=? WHERE tg_id=?",(nbft+1,m.from_user.id))
            conn.commit()
            return bot.reply_to(m, f"✅ Лимит: {slots_limit(m.from_user.id, field)}")
    bot.reply_to(m, "слот | слот купить юзы | слот купить номера | слот купить нфт")

# ============ ИНВЕНТАРЬ / ПОСТАВИТЬ ============
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "инвентарь")
def inv(m):
    register(m.from_user.id, m.from_user.username)
    txt, page, pages = build_inv_page(m.from_user.id, "user", 0)
    kb = inv_keyboard(m.from_user.id, "user", page, pages)
    bot.reply_to(m, txt, parse_mode="HTML", reply_markup=kb)

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

# ============ БИРЖА ============
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "биржа")
def exchange(m):
    cur.execute("SELECT id, seller_id, item, type, rarity, price, currency FROM listings ORDER BY id DESC LIMIT 30")
    rows = cur.fetchall()
    if not rows: return bot.reply_to(m, "🏦 Пусто")
    txt = "🏦 <b>Биржа</b>\n\n"
    for lid, seller, item, typ, rar, price, curr in rows:
        s = "⭐" if curr=="stars" else "🪙"
        title = nft_link(item) if typ=="nft" else item
        txt += f"<code>#{lid}</code> {RARITIES[rar]['emoji']} {title} — <b>{price:,}</b> {s} (от {display_name(seller)})\n"
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
    cur.execute("SELECT rarity FROM inventory WHERE item=?",(item,)); rar = cur.fetchone()[0]
    cur.execute("DELETE FROM inventory WHERE item=?",(item,)); clear_eq(m.from_user.id, item)
    curr = "stars" if typ=="nft" else "coins"
    cur.execute("INSERT INTO listings(seller_id,item,type,rarity,price,currency) VALUES(?,?,?,?,?,?)",(m.from_user.id,item,typ,rar,price,curr)); conn.commit()
    bot.reply_to(m, f"✅ {item} за {price:,} {'⭐' if curr=='stars' else '🪙'}")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("снять"))
def unlist(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "снять <id>")
    try: lid = int(p[1])
    except: return bot.reply_to(m, "ID")
    cur.execute("SELECT seller_id, item, type, rarity, price FROM listings WHERE id=?",(lid,)); r = cur.fetchone()
    if not r: return bot.reply_to(m, "Нет лота")
    seller, item, typ, rar, price = r
    if seller != m.from_user.id: return bot.reply_to(m, "Не твой")
    if count_items(seller, typ) >= slots_limit(seller, typ): return bot.reply_to(m, "❌ Нет места")
    cur.execute("DELETE FROM listings WHERE id=?",(lid,))
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",(seller,item,typ,rar,price)); conn.commit()
    bot.reply_to(m, f"✅ {item} возвращён")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("купить"))
def buy_lot(m):
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "купить <id>")
    try: lid = int(p[1])
    except: return bot.reply_to(m, "ID")
    cur.execute("SELECT seller_id, item, type, rarity, price, currency FROM listings WHERE id=?",(lid,)); r = cur.fetchone()
    if not r: return bot.reply_to(m, "Нет лота")
    seller, item, typ, rar, price, curr = r
    if seller == m.from_user.id: return bot.reply_to(m, "Твой лот")
    if count_items(m.from_user.id, typ) >= slots_limit(m.from_user.id, typ): return bot.reply_to(m, "❌ Нет места")
    if curr == "stars":
        if get_stars(m.from_user.id) < price: return bot.reply_to(m, f"❌ {price:,} ⭐")
        add_stars(m.from_user.id, -price); add_stars(seller, price)
    else:
        if get_coins(m.from_user.id) < price: return bot.reply_to(m, f"❌ {price:,} 🪙")
        add_coins(m.from_user.id, -price); add_coins(seller, price)
    cur.execute("DELETE FROM listings WHERE id=?",(lid,))
    cur.execute("INSERT INTO inventory(tg_id,item,type,rarity,price) VALUES(?,?,?,?,?)",(m.from_user.id,item,typ,rar,price)); conn.commit()
    bot.reply_to(m, f"✅ Купил за {price:,} {'⭐' if curr=='stars' else '🪙'}")

# ============ БОНУС ============
@bot.message_handler(func=lambda m: m.text and m.text.lower() in ("бонус","ежедневно"))
def daily(m):
    register(m.from_user.id, m.from_user.username)
    cur.execute("SELECT last_claim FROM daily WHERE tg_id=?",(m.from_user.id,)); r = cur.fetchone()
    now = int(time.time())
    if r and now - r[0] < 86400:
        left = 86400 - (now - r[0]); h, rem = divmod(left, 3600)
        return bot.reply_to(m, f"⏳ {h}ч {rem//60}м")
    reward = random.randint(50, 200); add_coins(m.from_user.id, reward)
    msg = f"🎁 +{reward:,} 🪙"
    if random.random() < 0.05: add_stars(m.from_user.id, 1); msg += "\n⭐ +1 (удача!)"
    cur.execute("INSERT OR REPLACE INTO daily(tg_id,last_claim) VALUES(?,?)",(m.from_user.id,now)); conn.commit()
    bot.reply_to(m, msg + f"\n💰 {get_coins(m.from_user.id):,}")

# ============ АДМИНКА ============
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("админ выдать"))
def admin_give(m):
    if not is_admin(m.from_user.id, m.from_user.username): return
    p = m.text.split()
    if len(p) < 4: return bot.reply_to(m, "админ выдать @user 1000")
    try: n = int(p[3])
    except: return
    tid = by_uname(p[2]) if p[2].startswith("@") else (int(p[2]) if p[2].lstrip("-").isdigit() else None)
    if tid: add_coins(tid, n); bot.reply_to(m, f"✅ {n:,} → {display_name(tid)}")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("админ звезда"))
def admin_star(m):
    if not is_admin(m.from_user.id, m.from_user.username): return
    p = m.text.split()
    if len(p) < 4: return bot.reply_to(m, "админ звезда @user 10")
    try: n = int(p[3])
    except: return
    tid = by_uname(p[2]) if p[2].startswith("@") else (int(p[2]) if p[2].lstrip("-").isdigit() else None)
    if tid: add_stars(tid, n); bot.reply_to(m, f"✅ {n} ⭐ → {display_name(tid)}")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("админ слот"))
def admin_slot(m):
    if not is_admin(m.from_user.id, m.from_user.username): return
    p = m.text.split()
    if len(p) < 4: return bot.reply_to(m, "админ слот @user 5")
    try: n = int(p[3])
    except: return
    tid = by_uname(p[2]) if p[2].startswith("@") else (int(p[2]) if p[2].lstrip("-").isdigit() else None)
    if tid:
        ub, nb, nbft = get_bought(tid)
        cur.execute("INSERT OR REPLACE INTO slots(tg_id,ub,nb,nbft) VALUES(?,?,?,?)",(tid,ub+n,nb+n,nbft+n)); conn.commit()
        bot.reply_to(m, f"✅ +{n} → {display_name(tid)}")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "админ топ")
def admin_top(m):
    if not is_admin(m.from_user.id, m.from_user.username): return
    cur.execute("SELECT COUNT(*) FROM users"); u = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM inventory"); i = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM inventory WHERE type='nft'"); n = cur.fetchone()[0]
    cur.execute("SELECT SUM(coins) FROM balances"); c = cur.fetchone()[0] or 0
    cur.execute("SELECT SUM(amount) FROM stars"); s = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM promo_codes"); pc = cur.fetchone()[0]
    bot.reply_to(m, f"📊 👥{u} 🎒{i} 🖼{n} 💰{c:,} ⭐{s:,} 🎟{pc}", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text and m.from_user.username)
def track(m): register(m.from_user.id, m.from_user.username)

print("Бот запущен...")
bot.infinity_polling(timeout=60, long_polling_timeout=60)