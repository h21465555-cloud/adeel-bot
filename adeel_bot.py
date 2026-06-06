# ══════════════════════════════════════════════════════════════════════
#  🌟  NEXORA  ELITE  ✦  PREMIUM  NUMBER  PANEL  •  v5  (FINAL)  🌟
#  ----------------------------------------------------------------
#  ✦ Single-file • Multi-thread safe SQLite (WAL)
#  ✦ Multi-language (বাংলা / English)
#  ✦ Flow: GET NUMBER → CATEGORY → COUNTRY → Number Card
#  ✦ Main-Admin + Sub-Admins
#  ✦ Smart OTP auto-forward
#  ✦ Cooldown • Daily Limit • Maintenance • VIP
#  ✦ /cancel anywhere • Broadcast • Dashboard
#  ✦ Member menu: History, Leader, Limit বাটন সরানো হয়েছে
#  Install : pip install pyTelegramBotAPI
#  Run     : python nexora_full_bot_v5.py
# ══════════════════════════════════════════════════════════════════════

# ╔══════════════════════════════════════════════════════════╗
# ║          🔧  শুধু এই অংশ এডিট করো                         ║
# ╚══════════════════════════════════════════════════════════╝
API_TOKEN      = "8570804997:AAF0RREfbDotPlYxnRT5STafBQhFAvhG_uY"
ADMIN_ID       = 8190027280
OTP_CHAT_ID    = -1003921588568
OTP_GROUP_LINK = "https://t.me/adeelotpbot7889"
BOT_USERNAME   = "Aadibot7889_bot"
DEFAULT_LANG   = "bn"
# ══════════════════════════════════════════════════════════════════════

import re
import time
import sqlite3
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

logging.basicConfig(
    filename="nexora.log", level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("nexora")

bot = telebot.TeleBot(API_TOKEN, parse_mode="Markdown")
DB_PATH = "nexora.db"
db_lock = threading.Lock()
user_temp: dict[int, dict] = {}


def utcnow_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def utcnow_dt() -> datetime:
    return datetime.now(timezone.utc)


# ╔══════════════════════════════════════════════════════════╗
# ║                       DATABASE (WAL)                      ║
# ╚══════════════════════════════════════════════════════════╝
@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    try:
        with db_lock:
            yield conn
            conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        cur = conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            taken INTEGER DEFAULT 0,
            vip INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            ref_count INTEGER DEFAULT 0,
            ref_by INTEGER DEFAULT 0,
            lang TEXT DEFAULT 'bn',
            joined_at TEXT,
            last_taken TEXT
        );
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY,
            emoji TEXT DEFAULT '📞'
        );
        CREATE TABLE IF NOT EXISTS countries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cat TEXT,
            name TEXT,
            emoji TEXT DEFAULT '🌐',
            UNIQUE(cat, name)
        );
        CREATE TABLE IF NOT EXISTS numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num TEXT UNIQUE,
            cat TEXT,
            country TEXT,
            used INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER, num TEXT, cat TEXT, country TEXT, taken_at TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT
        );
        CREATE TABLE IF NOT EXISTS sub_admins (
            uid INTEGER PRIMARY KEY,
            added_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_hist_uid ON history(uid);
        CREATE INDEX IF NOT EXISTS idx_num_cat  ON numbers(cat, country);
        """)

        # Migrate old DB: add country/last_taken columns if missing
        for col, default in [("country", "''"), ("last_taken", "NULL")]:
            try:
                conn.execute(f"ALTER TABLE numbers ADD COLUMN country TEXT DEFAULT {default}")
            except sqlite3.OperationalError:
                pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN last_taken TEXT")
        except sqlite3.OperationalError:
            pass

        for name, emoji in [
            ("General", "📞"), ("WhatsApp", "🟢"), ("Telegram", "💎"),
            ("IMO", "🔵"), ("Facebook", "🌐"),
        ]:
            conn.execute("INSERT OR IGNORE INTO categories(name,emoji) VALUES(?,?)", (name, emoji))

        for k, v in [
            ("cooldown", "30"), ("maintenance", "off"),
            ("daily_limit", "20"), ("ref_target", "5"), ("per_request", "2"),
        ]:
            conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))


def setting(key: str, default: str = "") -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    with db() as conn:
        conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


# ╔══════════════════════════════════════════════════════════╗
# ║                  🌐  i18n  (bn / en)                      ║
# ╚══════════════════════════════════════════════════════════╝
I18N = {
    "bn": {
        "btn_number":  "📱 𝗡𝗨𝗠𝗕𝗘𝗥",
        "btn_stock":   "📦 𝗦𝗧𝗢𝗖𝗞",
        "btn_profile": "👤 𝗣𝗥𝗢𝗙𝗜𝗟𝗘",
        "btn_vip":     "⭐ 𝗩𝗜𝗣",
        "btn_otp":     "🔔 𝗢𝗧𝗣",
        "btn_refer":   "🎁 𝗥𝗘𝗙𝗘𝗥",
        "btn_support": "💬 𝗦𝗨𝗣𝗣𝗢𝗥𝗧",
        "btn_lang":    "🌐 𝗟𝗔𝗡𝗚𝗨𝗔𝗚𝗘",
        "btn_admin":   "👑 𝗔𝗗𝗠𝗜𝗡",
        "btn_back":    "🔙 𝗕𝗔𝗖𝗞",
        "banned":      "🚫 আপনি ব্যান হয়েছেন!",
        "maintenance": "🛠️ বট মেইনটেনেন্সে আছে!",
        "pick_cat":    "🗂 *ক্যাটাগরি সিলেক্ট করুন:*",
        "pick_country":"🌍 *দেশ বেছে নিন:*",
        "main_menu":   "🏠 মেইন মেনু",
        "wait_sec":    "⏳ {s} সেকেন্ড অপেক্ষা করুন!",
        "no_stock":    "❌ এই দেশের কোনো নাম্বার নেই।",
        "no_cat":      "⚠️ কোনো ক্যাটাগরি নেই।",
        "no_country":  "⚠️ এই ক্যাটাগরিতে কোনো দেশ নেই।",
        "limit_done":  "📊 আজকের লিমিট ({n}) শেষ!",
        "fetching":    "⏳ আনছি...",
        "tap_copy":    "_👆 ট্যাপ করে কপি করুন_",
        "wait_otp":    "⏳ OTP-এর জন্য অপেক্ষা করুন...",
        "numbers_assigned": "✅ নাম্বার পাওয়া গেছে",
        "vip_badge":   "👑 𝗩𝗜𝗣",
        "elite_badge": "💎 𝗘𝗟𝗜𝗧𝗘",
        "stock_title": "📦 *স্টক আপডেট*",
        "stock_empty": "\n⚠️ কোনো স্টক নেই!",
        "profile_title":"👤 *প্রোফাইল*",
        "p_name": "📛 নাম", "p_id": "🆔 ID", "p_taken": "📞 নেওয়া",
        "p_vip": "⭐ VIP", "p_ref": "🎁 রেফার",
        "yes": "✅ হ্যাঁ", "no": "❌ না",
        "vip_active":    "⭐ *আপনি VIP সদস্য!*\n• কোনো কুলডাউন নেই\n• সীমাহীন নাম্বার",
        "vip_inactive_t":"💎 *নিয়মিত সদস্য*",
        "vip_get":       "🎁 VIP পেতে এডমিনে যোগাযোগ করুন।",
        "otp_title":     "🔔 *OTP গ্রুপ*\nকোড আসলে স্বয়ংক্রিয়ভাবে আপনার DM-এ আসবে!",
        "otp_join":      "🔔 OTP গ্রুপে জয়েন",
        "refer_title":   "🎁 *রেফার লিংক*",
        "refer_share":   "📤 শেয়ার করুন",
        "refer_count":   "👥 রেফার",
        "refer_target":  "🎯 {n} জন = VIP ⭐",
        "support_title": "💬 *সাপোর্ট*\nযেকোনো সমস্যায় এডমিনের সাথে যোগাযোগ করুন।",
        "support_btn":   "👑 এডমিনকে মেসেজ",
        "lang_pick":     "🌐 *ভাষা সিলেক্ট করুন:*",
        "lang_saved":    "✅ ভাষা পরিবর্তন হয়েছে!",
        "cancelled":     "❌ বাতিল করা হয়েছে।",
        "btn_chg":       "🔄 আরেকটি নাম্বার",
        "btn_otpgrp":    "🔔 OTP গ্রুপ",
        "btn_other":     "📂 অন্য ক্যাটাগরি",
        "btn_home":      "🏠 মেইন",
        "hello":         "হ্যালো",
        "welcome_sub":   "📞 প্রিমিয়াম নাম্বার প্যানেল",
        "welcome_hint":  "⚡ _নিচের মেনু থেকে বেছে নিন_ ⚡",
        "confirm_del":   "⚠️ নিশ্চিত? *{country}* এর {n} টি নাম্বার মুছে যাবে?",
        "deleted_country":"🗑 *{country}* এর {n} টি নাম্বার মুছে ফেলা হয়েছে।",
    },
    "en": {
        "btn_number":  "📱 𝗡𝗨𝗠𝗕𝗘𝗥",
        "btn_stock":   "📦 𝗦𝗧𝗢𝗖𝗞",
        "btn_profile": "👤 𝗣𝗥𝗢𝗙𝗜𝗟𝗘",
        "btn_vip":     "⭐ 𝗩𝗜𝗣",
        "btn_otp":     "🔔 𝗢𝗧𝗣",
        "btn_refer":   "🎁 𝗥𝗘𝗙𝗘𝗥",
        "btn_support": "💬 𝗦𝗨𝗣𝗣𝗢𝗥𝗧",
        "btn_lang":    "🌐 𝗟𝗔𝗡𝗚𝗨𝗔𝗚𝗘",
        "btn_admin":   "👑 𝗔𝗗𝗠𝗜𝗡",
        "btn_back":    "🔙 𝗕𝗔𝗖𝗞",
        "banned":      "🚫 You are banned!",
        "maintenance": "🛠️ Bot is under maintenance!",
        "pick_cat":    "🗂 *Pick a category:*",
        "pick_country":"🌍 *Pick a country:*",
        "main_menu":   "🏠 Main Menu",
        "wait_sec":    "⏳ Wait {s} seconds!",
        "no_stock":    "❌ No numbers in stock for this country.",
        "no_cat":      "⚠️ No categories yet.",
        "no_country":  "⚠️ No countries in this category.",
        "limit_done":  "📊 Daily limit ({n}) reached!",
        "fetching":    "⏳ Fetching...",
        "tap_copy":    "_👆 Tap to copy_",
        "wait_otp":    "⏳ Waiting for OTP...",
        "numbers_assigned": "✅ Numbers Assigned",
        "vip_badge":   "👑 𝗩𝗜𝗣",
        "elite_badge": "💎 𝗘𝗟𝗜𝗧𝗘",
        "stock_title": "📦 *Stock Update*",
        "stock_empty": "\n⚠️ No stock!",
        "profile_title":"👤 *Profile*",
        "p_name": "📛 Name", "p_id": "🆔 ID", "p_taken": "📞 Taken",
        "p_vip": "⭐ VIP", "p_ref": "🎁 Referrals",
        "yes": "✅ Yes", "no": "❌ No",
        "vip_active":    "⭐ *You are a VIP member!*\n• No cooldown\n• Unlimited numbers",
        "vip_inactive_t":"💎 *Regular member*",
        "vip_get":       "🎁 Contact admin to get VIP.",
        "otp_title":     "🔔 *OTP Group*\nCodes will be auto-forwarded to your DM!",
        "otp_join":      "🔔 Join OTP Group",
        "refer_title":   "🎁 *Referral Link*",
        "refer_share":   "📤 Share",
        "refer_count":   "👥 Referrals",
        "refer_target":  "🎯 {n} referrals = VIP ⭐",
        "support_title": "💬 *Support*\nContact the admin for any issue.",
        "support_btn":   "👑 Message Admin",
        "lang_pick":     "🌐 *Select language:*",
        "lang_saved":    "✅ Language updated!",
        "cancelled":     "❌ Cancelled.",
        "btn_chg":       "🔄 Get Another",
        "btn_otpgrp":    "🔔 OTP Group",
        "btn_other":     "📂 Other Category",
        "btn_home":      "🏠 Home",
        "hello":         "Hello",
        "welcome_sub":   "📞 Premium Number Panel",
        "welcome_hint":  "⚡ _Pick from the menu below_ ⚡",
        "confirm_del":   "⚠️ Sure? All {n} numbers of *{country}* will be removed?",
        "deleted_country":"🗑 Removed {n} numbers of *{country}*.",
    },
}

_BTN_INDEX: dict[str, str] = {}
for _lang, _d in I18N.items():
    for _k, _v in _d.items():
        if _k.startswith("btn_"):
            _BTN_INDEX[_v] = _k

def lang_of(uid: int) -> str:
    with db() as conn:
        r = conn.execute("SELECT lang FROM users WHERE id=?", (uid,)).fetchone()
    return (r["lang"] if r and r["lang"] else DEFAULT_LANG) or "bn"

def t(uid: int, key: str, **kw) -> str:
    lng = lang_of(uid)
    s = I18N.get(lng, I18N["bn"]).get(key) or I18N["bn"].get(key, key)
    return s.format(**kw) if kw else s

def btn_is(text: str, key: str) -> bool:
    return _BTN_INDEX.get(text or "") == key


# ╔══════════════════════════════════════════════════════════╗
# ║                   ADMIN BUTTON LABELS                     ║
# ╚══════════════════════════════════════════════════════════╝
ADM_ADD_CAT    = "📂 𝗔𝗗𝗗 𝗖𝗔𝗧𝗘𝗚𝗢𝗥𝗬"
ADM_DEL_CAT    = "🗑️ 𝗗𝗘𝗟 𝗖𝗔𝗧𝗘𝗚𝗢𝗥𝗬"
ADM_ADD_COUNTRY= "🌍 𝗔𝗗𝗗 𝗖𝗢𝗨𝗡𝗧𝗥𝗬"
ADM_ADD_NUM    = "📥 𝗔𝗗𝗗 𝗡𝗨𝗠𝗕𝗘𝗥𝗦"
ADM_DEL_NUM    = "🗑️ 𝗗𝗘𝗟 𝗡𝗨𝗠𝗕𝗘𝗥𝗦"
ADM_USERS      = "📋 𝗨𝗦𝗘𝗥𝗦"
ADM_DASH       = "📊 𝗗𝗔𝗦𝗛𝗕𝗢𝗔𝗥𝗗"
ADM_VIP        = "⭐ 𝗠𝗔𝗞𝗘 𝗩𝗜𝗣"
ADM_RM_VIP     = "💔 𝗥𝗘𝗠𝗢𝗩𝗘 𝗩𝗜𝗣"
ADM_BAN        = "🚫 𝗕𝗔𝗡"
ADM_UNBAN      = "✅ 𝗨𝗡𝗕𝗔𝗡"
ADM_CD         = "⏱️ 𝗖𝗢𝗢𝗟𝗗𝗢𝗪𝗡"
ADM_LIMIT      = "🎚️ 𝗗𝗔𝗜𝗟𝗬 𝗟𝗜𝗠𝗜𝗧"
ADM_PER_REQ    = "📱 𝗣𝗘𝗥 𝗥𝗘𝗤𝗨𝗘𝗦𝗧"
ADM_MAINT      = "🛠️ 𝗠𝗔𝗜𝗡𝗧𝗘𝗡𝗔𝗡𝗖𝗘"
ADM_BCAST      = "📢 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧"
ADM_SUB        = "🛡️ 𝗦𝗨𝗕-𝗔𝗗𝗠𝗜𝗡𝗦"


# ╔══════════════════════════════════════════════════════════╗
# ║                       KEYBOARDS                           ║
# ╚══════════════════════════════════════════════════════════╝
def main_menu(uid: int) -> types.ReplyKeyboardMarkup:
    # ❌ History, Leader, Limit বাটন সরানো হয়েছে
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    L = I18N.get(lang_of(uid), I18N["bn"])
    kb.row(L["btn_number"],  L["btn_stock"])
    kb.row(L["btn_profile"], L["btn_vip"])
    kb.row(L["btn_otp"],     L["btn_refer"])
    kb.row(L["btn_support"], L["btn_lang"])
    if is_admin(uid):
        kb.row(L["btn_admin"])
    return kb

def admin_menu(uid: int) -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row(ADM_ADD_CAT,  ADM_DEL_CAT)
    kb.row(ADM_ADD_COUNTRY, ADM_ADD_NUM)
    kb.row(ADM_DEL_NUM,  ADM_USERS)
    kb.row(ADM_DASH,     ADM_VIP)
    kb.row(ADM_RM_VIP,   ADM_BAN)
    kb.row(ADM_UNBAN,    ADM_CD)
    kb.row(ADM_LIMIT,    ADM_PER_REQ)
    kb.row(ADM_MAINT,    ADM_BCAST)
    kb.row(ADM_SUB)
    kb.row(I18N[lang_of(uid)]["btn_back"])
    return kb

def category_kb(uid: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    with db() as conn:
        cats = conn.execute("SELECT name, emoji FROM categories ORDER BY name").fetchall()
    rows = []
    row = []
    for cat in cats:
        with db() as conn:
            cnt = conn.execute(
                "SELECT COUNT(*) n FROM numbers WHERE cat=? AND used=0",
                (cat["name"],)).fetchone()["n"]
        dot = "🟢" if cnt > 10 else ("🟡" if cnt > 0 else "🔴")
        row.append(types.InlineKeyboardButton(
            f"{cat['emoji']} {cat['name']} {dot}({cnt})",
            callback_data=f"cat_{cat['name']}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    for r in rows:
        kb.row(*r)
    kb.add(types.InlineKeyboardButton("🏠 Home", callback_data="home"))
    return kb

def country_kb(uid: int, cat: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    with db() as conn:
        countries = conn.execute(
            "SELECT c.name, c.emoji, COUNT(n.id) AS cnt "
            "FROM countries c "
            "LEFT JOIN numbers n ON n.cat=c.cat AND n.country=c.name AND n.used=0 "
            "WHERE c.cat=? GROUP BY c.id ORDER BY c.name",
            (cat,)).fetchall()
    if not countries:
        return kb
    rows = []; row = []
    for c in countries:
        label = f"{c['emoji'] or '🌐'} {c['name']} ({c['cnt']})"
        row.append(types.InlineKeyboardButton(label, callback_data=f"country_{cat}_{c['name']}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    for r in rows:
        kb.row(*r)
    kb.add(types.InlineKeyboardButton(t(uid, "btn_back"), callback_data="pick"))
    return kb

def lang_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🇧🇩 বাংলা",  callback_data="setlang_bn"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en"),
    )
    return kb

def number_kb(uid: int, cat: str, country: str) -> types.InlineKeyboardMarkup:
    L = I18N.get(lang_of(uid), I18N["bn"])
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(L["btn_chg"],    callback_data=f"change_{cat}_{country}"),
        types.InlineKeyboardButton(L["btn_otpgrp"], url=OTP_GROUP_LINK),
    )
    kb.add(
        types.InlineKeyboardButton(L["btn_other"],  callback_data="pick"),
        types.InlineKeyboardButton(L["btn_home"],   callback_data="home"),
    )
    return kb


# ╔══════════════════════════════════════════════════════════╗
# ║                       HELPERS                             ║
# ╚══════════════════════════════════════════════════════════╝
def is_admin(uid: int) -> bool:
    if uid == ADMIN_ID:
        return True
    with db() as conn:
        r = conn.execute("SELECT 1 FROM sub_admins WHERE uid=?", (uid,)).fetchone()
    return bool(r)

def is_banned(uid: int) -> bool:
    with db() as conn:
        r = conn.execute("SELECT banned FROM users WHERE id=?", (uid,)).fetchone()
    return bool(r and r["banned"])

def is_vip(uid: int) -> bool:
    with db() as conn:
        r = conn.execute("SELECT vip FROM users WHERE id=?", (uid,)).fetchone()
    return bool(r and r["vip"])

def cooldown_remaining(uid: int) -> int:
    if is_vip(uid) or is_admin(uid):
        return 0
    cd = int(setting("cooldown", "30"))
    with db() as conn:
        r = conn.execute(
            "SELECT last_taken FROM users WHERE id=?", (uid,)).fetchone()
    if not r or not r["last_taken"]:
        return 0
    try:
        last = datetime.strptime(r["last_taken"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        diff = (utcnow_dt() - last).total_seconds()
        return max(0, int(cd - diff))
    except Exception:
        return 0

def register_user(m):
    uid = m.from_user.id
    name = m.from_user.first_name or "User"
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO users(id,name,lang,joined_at) VALUES(?,?,?,?)",
                     (uid, name, DEFAULT_LANG, utcnow_str()))

def _ask(uid: int, text: str, fn):
    bot.send_message(uid, text, parse_mode="Markdown")
    bot.register_next_step_handler_by_chat_id(uid, fn)


# ╔══════════════════════════════════════════════════════════╗
# ║                  NUMBER CARD                              ║
# ╚══════════════════════════════════════════════════════════╝
def build_number_card(uid: int, cat: str, country: str, country_emoji: str, nums: list) -> str:
    circles = ['➊','➋','➌','➍','➎','➏','➐','➑','➒','➓']
    lng = lang_of(uid)
    if lng == "bn":
        head = "✅ *নাম্বার সফলভাবে পাওয়া গেছে*"
        wait = "🌀 *OTP-এর জন্য অপেক্ষা করুন*"
        hint = "_এই স্ক্রিনে থাকুন — OTP এলে এখানে দেখাবে_"
    else:
        head = "✅ *Numbers Assigned Successfully*"
        wait = "🌀 *Waiting for OTP*"
        hint = "_Stay on this screen — OTP will appear here_"

    lines = [
        "╔══ ✦ 𝗡𝗘𝗫𝗢𝗥𝗔 𝗘𝗟𝗜𝗧𝗘 ✦ ══╗",
        "",
        head,
        "",
        f"{country_emoji} *{cat}*  ┊  {country}",
        "",
    ]
    for i, num in enumerate(nums):
        c = circles[i] if i < len(circles) else f"({i+1})"
        lines.append(f"{c} 📱 `{num}`")
    lines += ["", wait, hint, "", "╚══════════════════════╝"]
    return "\n".join(lines)


# ╔══════════════════════════════════════════════════════════╗
# ║              OTP AUTO-FORWARD                             ║
# ╚══════════════════════════════════════════════════════════╝
def handle_otp_message(msg):
    text = msg.get("text") or msg.get("caption") or ""
    if not text:
        return
    import re as _re
    nums = _re.findall(r'\d{7,}', text)
    target = None
    if nums:
        for d in nums:
            with db() as conn:
                r = conn.execute(
                    "SELECT uid FROM history WHERE replace(replace(num,'+',''),' ','') LIKE ? "
                    "ORDER BY id DESC LIMIT 1", (f"%{d}%",)).fetchone()
            if r:
                target = int(r["uid"]); break
    if not target:
        with db() as conn:
            r = conn.execute("SELECT uid FROM history ORDER BY id DESC LIMIT 1").fetchone()
        if r:
            target = int(r["uid"])
    if target:
        try:
            bot.send_message(target, f"🔔 *OTP Received*\n\n```\n{text}\n```")
        except Exception:
            pass


# ╔══════════════════════════════════════════════════════════╗
# ║                  /start  /cancel  /lang                   ║
# ╚══════════════════════════════════════════════════════════╝
@bot.message_handler(commands=["start"])
def cmd_start(m):
    register_user(m)
    uid = m.from_user.id
    name = m.from_user.first_name or "User"

    # Referral
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("ref_"):
        try:
            ref_id = int(parts[1][4:])
            if ref_id != uid:
                with db() as conn:
                    row = conn.execute("SELECT ref_by FROM users WHERE id=?", (uid,)).fetchone()
                    if row and not row["ref_by"]:
                        conn.execute("UPDATE users SET ref_by=? WHERE id=?", (ref_id, uid))
                        conn.execute("UPDATE users SET ref_count=ref_count+1 WHERE id=?", (ref_id,))
                        target = int(setting("ref_target", "5"))
                        cnt = conn.execute("SELECT ref_count FROM users WHERE id=?",
                                           (ref_id,)).fetchone()["ref_count"]
                        if cnt and cnt % target == 0:
                            conn.execute("UPDATE users SET vip=1 WHERE id=?", (ref_id,))
                            try:
                                bot.send_message(ref_id, f"🎉 *{target} refs = VIP ⭐*")
                            except Exception: pass
        except Exception: pass

    if is_banned(uid):
        return bot.send_message(uid, t(uid, "banned"))

    banner = (
        "◈━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◈\n"
        "    💎  *𝗡𝗘𝗫𝗢𝗥𝗔 𝗘𝗟𝗜𝗧𝗘*  💎\n"
        "◈━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◈\n"
        f"   👋 {t(uid,'hello')} *{name}*!\n"
        f"   {t(uid,'welcome_sub')}\n"
        "◈━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◈\n"
        f"{t(uid,'welcome_hint')}"
    )
    bot.send_message(uid, banner, reply_markup=main_menu(uid))


@bot.message_handler(commands=["cancel"])
def cmd_cancel(m):
    uid = m.from_user.id
    try: bot.clear_step_handler_by_chat_id(uid)
    except Exception: pass
    user_temp.pop(uid, None)
    bot.send_message(uid, t(uid, "cancelled"), reply_markup=main_menu(uid))


@bot.callback_query_handler(func=lambda cq: cq.data.startswith("setlang_"))
def cb_setlang(cq):
    uid = cq.from_user.id
    code = cq.data[len("setlang_"):]
    if code not in I18N:
        return bot.answer_callback_query(cq.id, "❌")
    with db() as conn:
        conn.execute("UPDATE users SET lang=? WHERE id=?", (code, uid))
    bot.answer_callback_query(cq.id, "✅")
    try: bot.delete_message(cq.message.chat.id, cq.message.message_id)
    except Exception: pass
    bot.send_message(uid, t(uid, "lang_saved"), reply_markup=main_menu(uid))


# ╔══════════════════════════════════════════════════════════╗
# ║            USER • GET NUMBER FLOW (Cat→Country→Number)    ║
# ╚══════════════════════════════════════════════════════════╝
@bot.message_handler(func=lambda m: btn_is(m.text, "btn_number"))
def h_number(m):
    uid = m.from_user.id
    if is_banned(uid): return bot.send_message(uid, t(uid, "banned"))
    if setting("maintenance") == "on" and not is_admin(uid):
        return bot.send_message(uid, t(uid, "maintenance"))
    bot.send_message(uid, t(uid, "pick_cat"), reply_markup=category_kb(uid))


@bot.callback_query_handler(func=lambda cq: cq.data.startswith("cat_"))
def cb_pick_category(cq):
    uid = cq.from_user.id
    cat = cq.data[4:]
    if is_banned(uid):
        return bot.answer_callback_query(cq.id, "🚫", show_alert=True)
    # Check if countries exist
    with db() as conn:
        countries = conn.execute(
            "SELECT id FROM countries WHERE cat=? LIMIT 1", (cat,)).fetchone()
    if not countries:
        return bot.answer_callback_query(cq.id, t(uid, "no_country"), show_alert=True)
    bot.answer_callback_query(cq.id)
    try:
        bot.edit_message_text(
            t(uid, "pick_country") + f"\n_{cat}_",
            cq.message.chat.id, cq.message.message_id,
            reply_markup=country_kb(uid, cat), parse_mode="Markdown")
    except Exception:
        bot.send_message(uid, t(uid, "pick_country"), reply_markup=country_kb(uid, cat))


@bot.callback_query_handler(func=lambda cq: cq.data.startswith("country_"))
def cb_pick_country(cq):
    uid = cq.from_user.id
    parts = cq.data.split("_", 2)
    if len(parts) < 3:
        return bot.answer_callback_query(cq.id, "❌")
    cat = parts[1]; country = parts[2]

    if is_banned(uid):
        return bot.answer_callback_query(cq.id, "🚫", show_alert=True)
    wait = cooldown_remaining(uid)
    if wait > 0:
        return bot.answer_callback_query(cq.id, t(uid, "wait_sec", s=wait), show_alert=True)
    limit = int(setting("daily_limit", "20"))
    if limit > 0 and not is_vip(uid) and not is_admin(uid):
        today = utcnow_dt().strftime("%Y-%m-%d")
        with db() as conn:
            used = conn.execute(
                "SELECT COUNT(*) n FROM history WHERE uid=? AND taken_at LIKE ?",
                (uid, today + "%")).fetchone()["n"]
        if used >= limit:
            return bot.answer_callback_query(cq.id, t(uid, "limit_done", n=limit), show_alert=True)

    bot.answer_callback_query(cq.id, t(uid, "fetching"))
    _send_numbers(uid, cat, country, cq.message.chat.id)


def _send_numbers(uid: int, cat: str, country: str, chat_id: int):
    per = max(1, int(setting("per_request", "2")))
    with db() as conn:
        # Get country emoji
        ce_row = conn.execute(
            "SELECT emoji FROM countries WHERE cat=? AND name=?", (cat, country)).fetchone()
        country_emoji = ce_row["emoji"] if ce_row else "🌐"
        # Get numbers
        rows = conn.execute(
            "SELECT id, num FROM numbers WHERE cat=? AND country=? AND used=0 LIMIT ?",
            (cat, country, per)).fetchall()
        if not rows:
            bot.send_message(chat_id, t(uid, "no_stock"))
            return
        now = utcnow_str()
        nums = []
        for r in rows:
            conn.execute("UPDATE numbers SET used=1 WHERE id=?", (r["id"],))
            conn.execute(
                "INSERT INTO history(uid,num,cat,country,taken_at) VALUES(?,?,?,?,?)",
                (uid, r["num"], cat, country, now))
            nums.append(r["num"])
        conn.execute(
            "UPDATE users SET taken=taken+?, last_taken=? WHERE id=?",
            (len(nums), now, uid))

    card = build_number_card(uid, cat, country, country_emoji, nums)
    bot.send_message(chat_id, card,
                     reply_markup=number_kb(uid, cat, country),
                     parse_mode="Markdown",
                     disable_web_page_preview=True)


@bot.callback_query_handler(func=lambda cq: cq.data.startswith("change_"))
def cb_change(cq):
    uid = cq.from_user.id
    parts = cq.data.split("_", 2)
    cat = parts[1] if len(parts) > 1 else "General"
    country = parts[2] if len(parts) > 2 else ""
    wait = cooldown_remaining(uid)
    if wait > 0:
        return bot.answer_callback_query(cq.id, t(uid, "wait_sec", s=wait), show_alert=True)
    bot.answer_callback_query(cq.id, "🔄")
    _send_numbers(uid, cat, country, cq.message.chat.id)


@bot.callback_query_handler(func=lambda cq: cq.data == "pick")
def cb_pick(cq):
    uid = cq.from_user.id
    bot.answer_callback_query(cq.id)
    bot.send_message(uid, t(uid, "pick_cat"), reply_markup=category_kb(uid))


@bot.callback_query_handler(func=lambda cq: cq.data == "home")
def cb_home(cq):
    uid = cq.from_user.id
    bot.answer_callback_query(cq.id)
    try: bot.delete_message(cq.message.chat.id, cq.message.message_id)
    except Exception: pass
    bot.send_message(uid, t(uid, "main_menu"), reply_markup=main_menu(uid))


@bot.message_handler(func=lambda m: btn_is(m.text, "btn_back"))
def h_back(m):
    uid = m.from_user.id
    bot.send_message(uid, t(uid, "main_menu"), reply_markup=main_menu(uid))


# ╔══════════════════════════════════════════════════════════╗
# ║                   USER • OTHER MENU                       ║
# ╚══════════════════════════════════════════════════════════╝
@bot.message_handler(func=lambda m: btn_is(m.text, "btn_stock"))
def h_stock(m):
    uid = m.from_user.id
    with db() as conn:
        rows = conn.execute(
            "SELECT cat, country, COUNT(*) c FROM numbers WHERE used=0 "
            "GROUP BY cat, country ORDER BY cat, country").fetchall()
    if not rows:
        return bot.send_message(uid, t(uid, "stock_empty"))
    lines = [t(uid, "stock_title"), "━━━━━━━━━━━━━━━━━━━━"]
    for r in rows:
        lines.append(f"• {r['cat']} • {r['country']} → *{r['c']}*")
    bot.send_message(uid, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(func=lambda m: btn_is(m.text, "btn_profile"))
def h_profile(m):
    uid = m.from_user.id
    with db() as conn:
        u = conn.execute("SELECT name, taken, vip, ref_count FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        return bot.send_message(uid, "❌")
    txt = (
        f"{t(uid,'profile_title')}\n━━━━━━━━━━━━━━━━━━━━\n"
        f"{t(uid,'p_name')}: {u['name']}\n"
        f"{t(uid,'p_id')}: `{uid}`\n"
        f"{t(uid,'p_taken')}: *{u['taken']}*\n"
        f"{t(uid,'p_vip')}: {t(uid,'yes') if u['vip'] else t(uid,'no')}\n"
        f"{t(uid,'p_ref')}: *{u['ref_count']}*"
    )
    bot.send_message(uid, txt, parse_mode="Markdown")


@bot.message_handler(func=lambda m: btn_is(m.text, "btn_vip"))
def h_vip(m):
    uid = m.from_user.id
    if is_vip(uid):
        txt = t(uid, "vip_active")
    else:
        txt = f"{t(uid,'vip_inactive_t')}\n\n{t(uid,'vip_get')}"
    bot.send_message(uid, txt, parse_mode="Markdown")


@bot.message_handler(func=lambda m: btn_is(m.text, "btn_otp"))
def h_otp(m):
    uid = m.from_user.id
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t(uid, "otp_join"), url=OTP_GROUP_LINK))
    bot.send_message(uid, t(uid, "otp_title"), reply_markup=kb, parse_mode="Markdown")


@bot.message_handler(func=lambda m: btn_is(m.text, "btn_refer"))
def h_refer(m):
    uid = m.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    with db() as conn:
        r = conn.execute("SELECT ref_count FROM users WHERE id=?", (uid,)).fetchone()
    cnt = r["ref_count"] if r else 0
    target = setting("ref_target", "5")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t(uid, "refer_share"),
        url=f"https://t.me/share/url?url={link}&text=Nexora%20Elite%20Bot"))
    bot.send_message(uid,
        f"{t(uid,'refer_title')}\n━━━━━━━━━━━━━━━━━\n"
        f"{t(uid,'refer_count')}: *{cnt}*\n"
        f"{t(uid,'refer_target', n=target)}\n\n🔗 `{link}`",
        reply_markup=kb, parse_mode="Markdown")


@bot.message_handler(func=lambda m: btn_is(m.text, "btn_support"))
def h_support(m):
    uid = m.from_user.id
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t(uid, "support_btn"), url=f"tg://user?id={ADMIN_ID}"))
    bot.send_message(uid, t(uid, "support_title"), reply_markup=kb, parse_mode="Markdown")


@bot.message_handler(func=lambda m: btn_is(m.text, "btn_lang"))
def h_lang(m):
    bot.send_message(m.from_user.id, t(m.from_user.id, "lang_pick"), reply_markup=lang_kb())


# ╔══════════════════════════════════════════════════════════╗
# ║                     ADMIN HANDLERS                        ║
# ╚══════════════════════════════════════════════════════════╝
def _admin_guard(m) -> bool:
    return is_admin(m.from_user.id)

def _main_admin_only(m) -> bool:
    return m.from_user.id == ADMIN_ID


# ─── Admin menu entry ───
@bot.message_handler(func=lambda m: btn_is(m.text, "btn_admin"))
def h_admin(m):
    uid = m.from_user.id
    if not is_admin(uid):
        return bot.send_message(uid, "🚫 Admin only.")
    bot.send_message(uid, "👑 *ADMIN PANEL*", reply_markup=admin_menu(uid))


# ─── Back from admin ───
@bot.message_handler(func=lambda m: m.text == I18N["bn"]["btn_back"] or
                                     m.text == I18N["en"]["btn_back"])
def h_admin_back(m):
    uid = m.from_user.id
    bot.send_message(uid, t(uid, "main_menu"), reply_markup=main_menu(uid))


# ─── Add Category ───
@bot.message_handler(func=lambda m: m.text == ADM_ADD_CAT and _admin_guard(m))
def adm_add_cat(m):
    uid = m.from_user.id
    _ask(uid, "📂 *ক্যাটাগরি যোগ করুন*\nপাঠান: `<emoji> <Name>`\nউদাহরণ: `📘 Facebook`", _save_cat)

def _save_cat(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    text = (m.text or "").strip()
    if text.startswith("/cancel"):
        return bot.send_message(uid, t(uid, "cancelled"), reply_markup=admin_menu(uid))
    parts = text.split(maxsplit=1)
    emoji = parts[0] if len(parts[0]) <= 4 else "📞"
    name = parts[1].strip() if len(parts) > 1 else text
    if not name:
        return bot.send_message(uid, "❌ নাম দিন!", reply_markup=admin_menu(uid))
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO categories(name,emoji) VALUES(?,?)", (name, emoji))
    bot.send_message(uid, f"✅ ক্যাটাগরি যোগ: {emoji} *{name}*", reply_markup=admin_menu(uid),
                     parse_mode="Markdown")


# ─── Delete Category ───
@bot.message_handler(func=lambda m: m.text == ADM_DEL_CAT and _admin_guard(m))
def adm_del_cat(m):
    uid = m.from_user.id
    with db() as conn:
        cats = conn.execute("SELECT name, emoji FROM categories ORDER BY name").fetchall()
    if not cats:
        return bot.send_message(uid, "⚠️ কোনো ক্যাটাগরি নেই।", reply_markup=admin_menu(uid))
    kb = types.InlineKeyboardMarkup(row_width=1)
    for c in cats:
        kb.add(types.InlineKeyboardButton(f"{c['emoji']} {c['name']}", callback_data=f"delcat_{c['name']}"))
    bot.send_message(uid, "❌ *কোন ক্যাটাগরি ডিলিট করবেন?*", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("delcat_"))
def cb_delcat(cq):
    if not is_admin(cq.from_user.id):
        return bot.answer_callback_query(cq.id, "🚫", show_alert=True)
    cat = cq.data[7:]
    with db() as conn:
        conn.execute("DELETE FROM categories WHERE name=?", (cat,))
        conn.execute("DELETE FROM countries WHERE cat=?", (cat,))
        conn.execute("DELETE FROM numbers WHERE cat=?", (cat,))
    bot.answer_callback_query(cq.id, "✅ Deleted")
    bot.edit_message_text(f"🗑 *{cat}* ডিলিট হয়েছে।",
                          cq.message.chat.id, cq.message.message_id, parse_mode="Markdown")


# ─── Add Country ───
@bot.message_handler(func=lambda m: m.text == ADM_ADD_COUNTRY and _admin_guard(m))
def adm_add_country(m):
    uid = m.from_user.id
    with db() as conn:
        cats = conn.execute("SELECT name, emoji FROM categories ORDER BY name").fetchall()
    if not cats:
        return bot.send_message(uid, "⚠️ আগে ক্যাটাগরি যোগ করুন।", reply_markup=admin_menu(uid))
    kb = types.InlineKeyboardMarkup(row_width=2)
    for c in cats:
        kb.add(types.InlineKeyboardButton(f"{c['emoji']} {c['name']}", callback_data=f"addcountry_{c['name']}"))
    bot.send_message(uid, "🌍 *কোন ক্যাটাগরিতে দেশ যোগ করবেন?*", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("addcountry_"))
def cb_addcountry(cq):
    if not is_admin(cq.from_user.id):
        return bot.answer_callback_query(cq.id, "🚫", show_alert=True)
    uid = cq.from_user.id
    cat = cq.data[11:]
    user_temp[uid] = {"add_country_cat": cat}
    bot.answer_callback_query(cq.id)
    bot.send_message(uid, f"🌍 *{cat}* ক্যাটাগরিতে দেশ যোগ করুন\n"
                          "পাঠান: `<emoji> <Country Name>`\nউদাহরণ: `🇧🇩 Bangladesh`\n\n/cancel",
                     parse_mode="Markdown")
    bot.register_next_step_handler_by_chat_id(uid, _save_country)

def _save_country(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    text = (m.text or "").strip()
    if text.startswith("/cancel"):
        user_temp.pop(uid, None)
        return bot.send_message(uid, t(uid, "cancelled"), reply_markup=admin_menu(uid))
    cat = user_temp.get(uid, {}).get("add_country_cat", "")
    if not cat:
        return bot.send_message(uid, "❌ Error.", reply_markup=admin_menu(uid))
    parts = text.split(maxsplit=1)
    first = parts[0] if parts else ""
    if len(first) <= 4 and len(parts) > 1:
        emoji = first; name = parts[1].strip()
    else:
        emoji = "🌐"; name = text
    if not name:
        return bot.send_message(uid, "❌ নাম দিন!", reply_markup=admin_menu(uid))
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO countries(cat,name,emoji) VALUES(?,?,?)", (cat, name, emoji))
    user_temp.pop(uid, None)
    bot.send_message(uid, f"✅ দেশ যোগ: {emoji} *{name}* → _{cat}_",
                     reply_markup=admin_menu(uid), parse_mode="Markdown")


# ─── Add Numbers ───
@bot.message_handler(func=lambda m: m.text == ADM_ADD_NUM and _admin_guard(m))
def adm_add_num(m):
    uid = m.from_user.id
    with db() as conn:
        cats = conn.execute("SELECT name, emoji FROM categories ORDER BY name").fetchall()
    if not cats:
        return bot.send_message(uid, "⚠️ আগে ক্যাটাগরি যোগ করুন।", reply_markup=admin_menu(uid))
    kb = types.InlineKeyboardMarkup(row_width=2)
    for c in cats:
        kb.add(types.InlineKeyboardButton(f"{c['emoji']} {c['name']}", callback_data=f"addnum_cat_{c['name']}"))
    bot.send_message(uid, "📥 *কোন ক্যাটাগরিতে নাম্বার যোগ করবেন?*", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("addnum_cat_"))
def cb_addnum_cat(cq):
    if not is_admin(cq.from_user.id):
        return bot.answer_callback_query(cq.id, "🚫", show_alert=True)
    uid = cq.from_user.id
    cat = cq.data[11:]
    with db() as conn:
        countries = conn.execute("SELECT name, emoji FROM countries WHERE cat=? ORDER BY name", (cat,)).fetchall()
    if not countries:
        return bot.answer_callback_query(cq.id, "⚠️ আগে এই ক্যাটাগরিতে দেশ যোগ করুন।", show_alert=True)
    kb = types.InlineKeyboardMarkup(row_width=2)
    for c in countries:
        kb.add(types.InlineKeyboardButton(f"{c['emoji']} {c['name']}", callback_data=f"addnum_c_{cat}_{c['name']}"))
    bot.answer_callback_query(cq.id)
    bot.edit_message_text(f"📥 *{cat}* — দেশ সিলেক্ট করুন:", cq.message.chat.id,
                          cq.message.message_id, reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("addnum_c_"))
def cb_addnum_country(cq):
    if not is_admin(cq.from_user.id):
        return bot.answer_callback_query(cq.id, "🚫", show_alert=True)
    uid = cq.from_user.id
    parts = cq.data.split("_", 3)
    cat = parts[2]; country = parts[3]
    user_temp[uid] = {"add_num_cat": cat, "add_num_country": country}
    bot.answer_callback_query(cq.id)
    bot.send_message(uid, f"📥 *{cat} • {country}*\nনাম্বার পেস্ট করুন (প্রতি লাইনে একটি বা স্পেস দিয়ে):\n\n/cancel",
                     parse_mode="Markdown")
    bot.register_next_step_handler_by_chat_id(uid, _save_numbers)

def _save_numbers(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    text = (m.text or "").strip()
    if text.startswith("/cancel"):
        user_temp.pop(uid, None)
        return bot.send_message(uid, t(uid, "cancelled"), reply_markup=admin_menu(uid))
    cat = user_temp.get(uid, {}).get("add_num_cat", "")
    country = user_temp.get(uid, {}).get("add_num_country", "")
    lines = re.split(r'[\r\n,\s]+', text)
    added = 0
    with db() as conn:
        for ln in lines:
            num = re.sub(r'[^\d+]', '', ln)
            if len(num) < 6: continue
            try:
                conn.execute("INSERT OR IGNORE INTO numbers(num,cat,country,used) VALUES(?,?,?,0)", (num, cat, country))
                added += 1
            except Exception: pass
    user_temp.pop(uid, None)
    bot.send_message(uid, f"✅ *{added}* টি নাম্বার যোগ হয়েছে → _{cat} • {country}_",
                     reply_markup=admin_menu(uid), parse_mode="Markdown")


# ─── Delete Numbers by Country ───
@bot.message_handler(func=lambda m: m.text == ADM_DEL_NUM and _admin_guard(m))
def adm_del_num(m):
    uid = m.from_user.id
    with db() as conn:
        cats = conn.execute("SELECT name, emoji FROM categories ORDER BY name").fetchall()
    if not cats:
        return bot.send_message(uid, "⚠️ কোনো ক্যাটাগরি নেই।", reply_markup=admin_menu(uid))
    kb = types.InlineKeyboardMarkup(row_width=2)
    for c in cats:
        kb.add(types.InlineKeyboardButton(f"{c['emoji']} {c['name']}", callback_data=f"delnum_cat_{c['name']}"))
    bot.send_message(uid, "🗑 *কোন ক্যাটাগরি থেকে নাম্বার ডিলিট করবেন?*", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("delnum_cat_"))
def cb_delnum_cat(cq):
    if not is_admin(cq.from_user.id): return
    uid = cq.from_user.id
    cat = cq.data[11:]
    with db() as conn:
        countries = conn.execute(
            "SELECT c.name, c.emoji, COUNT(n.id) cnt "
            "FROM countries c LEFT JOIN numbers n ON n.cat=c.cat AND n.country=c.name AND n.used=0 "
            "WHERE c.cat=? GROUP BY c.id ORDER BY c.name", (cat,)).fetchall()
    if not countries:
        return bot.answer_callback_query(cq.id, "⚠️ দেশ নেই।", show_alert=True)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for c in countries:
        kb.add(types.InlineKeyboardButton(
            f"{c['emoji']} {c['name']} ({c['cnt']})",
            callback_data=f"delnum_c_{cat}_{c['name']}"))
    bot.answer_callback_query(cq.id)
    bot.edit_message_text(f"🗑 *{cat}* — কোন দেশের নাম্বার মুছবেন?",
                          cq.message.chat.id, cq.message.message_id, reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("delnum_c_"))
def cb_delnum_country(cq):
    if not is_admin(cq.from_user.id): return
    uid = cq.from_user.id
    parts = cq.data.split("_", 3)
    cat = parts[2]; country = parts[3]
    with db() as conn:
        cnt = conn.execute("SELECT COUNT(*) n FROM numbers WHERE cat=? AND country=? AND used=0",
                           (cat, country)).fetchone()["n"]
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ হ্যাঁ, মুছুন", callback_data=f"delgo_{cat}_{country}"),
        types.InlineKeyboardButton("❌ না", callback_data="cancel_del")
    )
    bot.answer_callback_query(cq.id)
    bot.edit_message_text(t(uid, "confirm_del", country=country, n=cnt),
                          cq.message.chat.id, cq.message.message_id, reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("delgo_"))
def cb_delgo(cq):
    if not is_admin(cq.from_user.id): return
    uid = cq.from_user.id
    parts = cq.data.split("_", 2)
    cat = parts[1]; country = parts[2]
    with db() as conn:
        conn.execute("DELETE FROM numbers WHERE cat=? AND country=?", (cat, country))
        cnt = conn.total_changes
    bot.answer_callback_query(cq.id, "✅ Deleted")
    bot.edit_message_text(t(uid, "deleted_country", country=country, n=cnt),
                          cq.message.chat.id, cq.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda cq: cq.data == "cancel_del")
def cb_cancel_del(cq):
    bot.answer_callback_query(cq.id, "❌ বাতিল")
    try: bot.delete_message(cq.message.chat.id, cq.message.message_id)
    except Exception: pass


# ─── Users / Dashboard ───
@bot.message_handler(func=lambda m: m.text == ADM_USERS and _admin_guard(m))
def adm_users(m):
    uid = m.from_user.id
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        vip   = conn.execute("SELECT COUNT(*) n FROM users WHERE vip=1").fetchone()["n"]
        banned= conn.execute("SELECT COUNT(*) n FROM users WHERE banned=1").fetchone()["n"]
    bot.send_message(uid,
        f"👥 *ইউজার তালিকা*\n━━━━━━━━━━━━\n"
        f"মোট: *{total}*\nVIP: *{vip}*\nBanned: *{banned}*",
        reply_markup=admin_menu(uid), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == ADM_DASH and _admin_guard(m))
def adm_dash(m):
    uid = m.from_user.id
    with db() as conn:
        total_num = conn.execute("SELECT COUNT(*) n FROM numbers WHERE used=0").fetchone()["n"]
        total_used = conn.execute("SELECT COUNT(*) n FROM numbers WHERE used=1").fetchone()["n"]
        total_users = conn.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
    bot.send_message(uid,
        f"📊 *ড্যাশবোর্ড*\n━━━━━━━━━━━━\n"
        f"📦 স্টকে: *{total_num}*\n✅ ব্যবহৃত: *{total_used}*\n👥 ইউজার: *{total_users}*",
        reply_markup=admin_menu(uid), parse_mode="Markdown")


# ─── VIP / Ban ───
@bot.message_handler(func=lambda m: m.text == ADM_VIP and _admin_guard(m))
def adm_vip(m):
    uid = m.from_user.id
    _ask(uid, "⭐ *VIP দিন* — ইউজার ID পাঠান:", _do_vip)

def _do_vip(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    if (m.text or "").startswith("/cancel"):
        return bot.send_message(uid, t(uid, "cancelled"), reply_markup=admin_menu(uid))
    try:
        tid = int((m.text or "").strip())
        with db() as conn:
            conn.execute("UPDATE users SET vip=1 WHERE id=?", (tid,))
        bot.send_message(uid, f"✅ `{tid}` VIP হয়েছেন।", reply_markup=admin_menu(uid))
        try: bot.send_message(tid, "⭐ *আপনি VIP হয়েছেন!*")
        except Exception: pass
    except Exception:
        bot.send_message(uid, "❌ ভুল ID!", reply_markup=admin_menu(uid))

@bot.message_handler(func=lambda m: m.text == ADM_RM_VIP and _admin_guard(m))
def adm_rm_vip(m):
    uid = m.from_user.id
    _ask(uid, "💔 *VIP সরান* — ইউজার ID পাঠান:", _do_rm_vip)

def _do_rm_vip(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    if (m.text or "").startswith("/cancel"):
        return bot.send_message(uid, t(uid, "cancelled"), reply_markup=admin_menu(uid))
    try:
        tid = int((m.text or "").strip())
        with db() as conn:
            conn.execute("UPDATE users SET vip=0 WHERE id=?", (tid,))
        bot.send_message(uid, f"✅ `{tid}` VIP সরানো হয়েছে।", reply_markup=admin_menu(uid))
    except Exception:
        bot.send_message(uid, "❌ ভুল ID!", reply_markup=admin_menu(uid))

@bot.message_handler(func=lambda m: m.text == ADM_BAN and _admin_guard(m))
def adm_ban(m):
    _ask(m.from_user.id, "🚫 *ব্যান* — ইউজার ID পাঠান:", _do_ban)

def _do_ban(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    if (m.text or "").startswith("/cancel"):
        return bot.send_message(uid, t(uid, "cancelled"), reply_markup=admin_menu(uid))
    try:
        tid = int((m.text or "").strip())
        with db() as conn:
            conn.execute("UPDATE users SET banned=1 WHERE id=?", (tid,))
        bot.send_message(uid, f"✅ `{tid}` ব্যান হয়েছেন।", reply_markup=admin_menu(uid))
    except Exception:
        bot.send_message(uid, "❌ ভুল ID!", reply_markup=admin_menu(uid))

@bot.message_handler(func=lambda m: m.text == ADM_UNBAN and _admin_guard(m))
def adm_unban(m):
    _ask(m.from_user.id, "✅ *আনব্যান* — ইউজার ID পাঠান:", _do_unban)

def _do_unban(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    if (m.text or "").startswith("/cancel"):
        return bot.send_message(uid, t(uid, "cancelled"), reply_markup=admin_menu(uid))
    try:
        tid = int((m.text or "").strip())
        with db() as conn:
            conn.execute("UPDATE users SET banned=0 WHERE id=?", (tid,))
        bot.send_message(uid, f"✅ `{tid}` আনব্যান হয়েছেন।", reply_markup=admin_menu(uid))
    except Exception:
        bot.send_message(uid, "❌ ভুল ID!", reply_markup=admin_menu(uid))


# ─── Settings ───
@bot.message_handler(func=lambda m: m.text == ADM_CD and _admin_guard(m))
def adm_cd(m):
    uid = m.from_user.id
    bot.send_message(uid, f"⏱️ *কুলডাউন*\nবর্তমান: {setting('cooldown','30')} সেকেন্ড\nনতুন মান পাঠান:")
    bot.register_next_step_handler_by_chat_id(uid, _save_cd)

def _save_cd(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    try:
        v = max(0, int((m.text or "").strip()))
        set_setting("cooldown", str(v))
        bot.send_message(uid, f"✅ কুলডাউন: {v}s", reply_markup=admin_menu(uid))
    except Exception:
        bot.send_message(uid, "❌ সংখ্যা দিন!", reply_markup=admin_menu(uid))

@bot.message_handler(func=lambda m: m.text == ADM_LIMIT and _admin_guard(m))
def adm_limit(m):
    uid = m.from_user.id
    bot.send_message(uid, f"🎚️ *দৈনিক লিমিট*\nবর্তমান: {setting('daily_limit','20')} (0=∞)\nনতুন মান পাঠান:")
    bot.register_next_step_handler_by_chat_id(uid, _save_limit)

def _save_limit(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    try:
        v = max(0, int((m.text or "").strip()))
        set_setting("daily_limit", str(v))
        bot.send_message(uid, f"✅ লিমিট: {v}", reply_markup=admin_menu(uid))
    except Exception:
        bot.send_message(uid, "❌ সংখ্যা দিন!", reply_markup=admin_menu(uid))

@bot.message_handler(func=lambda m: m.text == ADM_PER_REQ and _admin_guard(m))
def adm_per_req(m):
    uid = m.from_user.id
    bot.send_message(uid, f"📱 *প্রতি রিকোয়েস্টে নাম্বার*\nবর্তমান: {setting('per_request','2')}\nনতুন মান পাঠান (১-১০):")
    bot.register_next_step_handler_by_chat_id(uid, _save_per_req)

def _save_per_req(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    try:
        v = max(1, min(10, int((m.text or "").strip())))
        set_setting("per_request", str(v))
        bot.send_message(uid, f"✅ Per request: {v}", reply_markup=admin_menu(uid))
    except Exception:
        bot.send_message(uid, "❌ সংখ্যা দিন!", reply_markup=admin_menu(uid))

@bot.message_handler(func=lambda m: m.text == ADM_MAINT and _admin_guard(m))
def adm_maint(m):
    uid = m.from_user.id
    cur = setting("maintenance", "off")
    new = "off" if cur == "on" else "on"
    set_setting("maintenance", new)
    bot.send_message(uid, f"🛠️ মেইনটেনেন্স: *{new.upper()}*", reply_markup=admin_menu(uid),
                     parse_mode="Markdown")


# ─── Broadcast ───
@bot.message_handler(func=lambda m: m.text == ADM_BCAST and _admin_guard(m))
def adm_bcast(m):
    uid = m.from_user.id
    bot.send_message(uid, "📢 *ব্রডকাস্ট* — মেসেজ পাঠান:")
    bot.register_next_step_handler_by_chat_id(uid, _do_bcast)

def _do_bcast(m):
    uid = m.from_user.id
    if not is_admin(uid): return
    text = (m.text or "").strip()
    if not text or text.startswith("/"):
        return bot.send_message(uid, "❌ বাতিল।", reply_markup=admin_menu(uid))
    with db() as conn:
        users = [r["id"] for r in conn.execute("SELECT id FROM users WHERE banned=0").fetchall()]
    bot.send_message(uid, f"📤 শুরু… {len(users)} জন")
    ok = fail = 0
    for tid in users:
        try:
            bot.send_message(tid, f"📢 *ব্রডকাস্ট*\n━━━━━━━━━━━━━━━━\n{text}")
            ok += 1
        except Exception:
            fail += 1
        time.sleep(0.05)
    bot.send_message(uid, f"✅ {ok} • ❌ {fail}", reply_markup=admin_menu(uid))


# ─── Sub-Admins ───
@bot.message_handler(func=lambda m: m.text == ADM_SUB and _main_admin_only(m))
def adm_sub(m):
    uid = m.from_user.id
    with db() as conn:
        subs = conn.execute("SELECT uid, added_at FROM sub_admins ORDER BY added_at").fetchall()
    lines = ["🛡️ *সাব-এডমিন তালিকা*", "━━━━━━━━━━━━━━━━━━━━"]
    if subs:
        for s in subs:
            lines.append(f"• `{s['uid']}` ({s['added_at'][:10]})")
    else:
        lines.append("_(কেউ নেই)_")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ যোগ করুন", callback_data="subadd"),
        types.InlineKeyboardButton("➖ সরান",    callback_data="subrm"),
    )
    bot.send_message(uid, "\n".join(lines), reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda cq: cq.data == "subadd")
def cb_subadd(cq):
    if cq.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(cq.id, "🚫 শুধু Main Admin", show_alert=True)
    bot.answer_callback_query(cq.id)
    bot.send_message(ADMIN_ID, "➕ *সাব-এডমিন যোগ* — ইউজার ID পাঠান:", parse_mode="Markdown")
    bot.register_next_step_handler_by_chat_id(ADMIN_ID, _do_subadd)

def _do_subadd(m):
    if m.from_user.id != ADMIN_ID: return
    if (m.text or "").startswith("/"):
        return bot.send_message(ADMIN_ID, "❌ বাতিল।", reply_markup=admin_menu(ADMIN_ID))
    try:
        tid = int((m.text or "").strip())
        if tid == ADMIN_ID:
            return bot.send_message(ADMIN_ID, "ℹ️ আপনি ইতিমধ্যেই Main Admin।",
                                    reply_markup=admin_menu(ADMIN_ID))
        with db() as conn:
            conn.execute("INSERT OR IGNORE INTO sub_admins(uid,added_at) VALUES(?,?)", (tid, utcnow_str()))
            conn.execute("INSERT OR IGNORE INTO users(id,name,joined_at) VALUES(?,?,?)",
                         (tid, "Sub-Admin", utcnow_str()))
        bot.send_message(ADMIN_ID, f"✅ `{tid}` সাব-এডমিন হয়েছেন।", reply_markup=admin_menu(ADMIN_ID))
        try: bot.send_message(tid, "🛡️ *আপনি সাব-এডমিন হয়েছেন!*\n/start চাপুন।")
        except Exception: pass
    except Exception:
        bot.send_message(ADMIN_ID, "❌ ভুল ID!", reply_markup=admin_menu(ADMIN_ID))

@bot.callback_query_handler(func=lambda cq: cq.data == "subrm")
def cb_subrm(cq):
    if cq.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(cq.id, "🚫 শুধু Main Admin", show_alert=True)
    bot.answer_callback_query(cq.id)
    bot.send_message(ADMIN_ID, "➖ *সাব-এডমিন সরান* — ইউজার ID পাঠান:", parse_mode="Markdown")
    bot.register_next_step_handler_by_chat_id(ADMIN_ID, _do_subrm)

def _do_subrm(m):
    if m.from_user.id != ADMIN_ID: return
    if (m.text or "").startswith("/"):
        return bot.send_message(ADMIN_ID, "❌ বাতিল।", reply_markup=admin_menu(ADMIN_ID))
    try:
        tid = int((m.text or "").strip())
        with db() as conn:
            conn.execute("DELETE FROM sub_admins WHERE uid=?", (tid,))
        bot.send_message(ADMIN_ID, f"✅ `{tid}` সরানো হয়েছে।", reply_markup=admin_menu(ADMIN_ID))
        try: bot.send_message(tid, "ℹ️ আপনার সাব-এডমিন স্ট্যাটাস সরানো হয়েছে।")
        except Exception: pass
    except Exception:
        bot.send_message(ADMIN_ID, "❌ ভুল ID!", reply_markup=admin_menu(ADMIN_ID))


# ╔══════════════════════════════════════════════════════════╗
# ║                     OTP GROUP HANDLER                     ║
# ╚══════════════════════════════════════════════════════════╝
@bot.message_handler(
    func=lambda m: m.chat.id == OTP_CHAT_ID,
    content_types=["text", "photo", "document", "sticker", "voice", "video"]
)
def otp_group_handler(m):
    handle_otp_message({"text": m.text or m.caption or ""})


# ╔══════════════════════════════════════════════════════════╗
# ║                          BOOT                             ║
# ╚══════════════════════════════════════════════════════════╝
if __name__ == "__main__":
    init_db()
    print("""
╔═══════════════════════════════════════════════════════╗
║   🌟  𝐍𝐄𝐗𝐎𝐑𝐀  𝐄𝐋𝐈𝐓𝐄  𝐁𝐎𝐓  •  v5  (FINAL)  🌟   ║
║   Cat → Country → Number Flow  •  Multi-lang          ║
╚═══════════════════════════════════════════════════════╝""")
    print(f"  ✅ Bot live  |  @{BOT_USERNAME}  |  Main-Admin: {ADMIN_ID}")
    print(f"  🔔 OTP group chat_id: {OTP_CHAT_ID}\n")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
        except Exception as e:
            log.exception("polling crash")
            print(f"⚠️  Polling crashed: {e}  — retry in 5s")
            time.sleep(5)
