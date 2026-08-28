# telegram-b
import asyncio
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

DB_PATH = os.getenv("DB_PATH", "gold_rates_pro.db")

PREMIUM_STARS = 200
PREMIUM_DAYS = 30

FRANKFURTER_URL = "https://api.frankfurter.dev/v2"
COINGECKO_URL = "https://api.coingecko.com/api/v3"
GOLD_URL = "https://api.goldprice.dev/v1/prices"

CACHE_TTL = 300

SUPPORTED_LANGUAGES = ("ar", "en", "ur")
SUPPORTED_INTERESTS = ("gold", "currency", "crypto", "full")

CURRENCY_LIST = ["USD", "SAR", "EUR", "GBP", "AED", "PKR"]

CRYPTO_FREE = [
    "bitcoin",
    "ethereum",
    "tether",
    "binancecoin",
    "solana",
    "ripple",
    "usd-coin",
    "dogecoin",
    "cardano",
    "avalanche-2",
    "tron",
    "chainlink",
    "shiba-inu",
    "polkadot",
    "wrapped-bitcoin",
    "bitcoin-cash",
    "near",
    "uniswap",
    "litecoin",
    "stellar",
]

CRYPTO_PREMIUM = CRYPTO_FREE + [
    "internet-computer",
    "dai",
    "aptos",
    "filecoin",
    "cosmos",
    "cronos",
    "hedera-hashgraph",
    "arbitrum",
    "vechain",
    "optimism",
]

CRYPTO_SYMBOLS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "tether": "USDT",
    "binancecoin": "BNB",
    "solana": "SOL",
    "ripple": "XRP",
    "usd-coin": "USDC",
    "dogecoin": "DOGE",
    "cardano": "ADA",
    "avalanche-2": "AVAX",
    "tron": "TRX",
    "chainlink": "LINK",
    "shiba-inu": "SHIB",
    "polkadot": "DOT",
    "wrapped-bitcoin": "WBTC",
    "bitcoin-cash": "BCH",
    "near": "NEAR",
    "uniswap": "UNI",
    "litecoin": "LTC",
    "stellar": "XLM",
    "internet-computer": "ICP",
    "dai": "DAI",
    "aptos": "APT",
    "filecoin": "FIL",
    "cosmos": "ATOM",
    "cronos": "CRO",
    "hedera-hashgraph": "HBAR",
    "arbitrum": "ARB",
    "vechain": "VET",
    "optimism": "OP",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("gold_rates_pro")

dp = Dispatcher()

http_session: Optional[aiohttp.ClientSession] = None

memory_cache = {}
cache_lock = asyncio.Lock()


TEXT = {
    "ar": {
        "choose_language": "🌍 اختر لغتك:",
        "choose_interest": "🎯 اختر ما تريد متابعته:",
        "gold_only": "🥇 الذهب فقط",
        "currency_only": "💱 العملات فقط",
        "crypto_only": "₿ العملات الرقمية فقط",
        "full": "🌐 الكل",
        "welcome": (
            "مرحباً بك في <b>Gold & Rates Pro</b> 👋\n\n"
            "أسعار الذهب والعملات والعملات الرقمية بسرعة وبشكل واضح."
        ),
        "rates": "📊 الأسعار الآن",
        "converter": "🔄 المحول",
        "alert": "🔔 تنبيه سعري",
        "watchlist": "⭐ قائمتي",
        "settings": "⚙️ الإعدادات",
        "premium": "💎 الخطة المميزة",
        "back": "🔙 رجوع",
        "gold": "🥇 الذهب",
        "currencies": "💱 العملات",
        "crypto": "₿ العملات الرقمية",
        "language": "🌍 اللغة",
        "interest": "🎯 الاهتمامات",
        "premium_active": "💎 الباقة المميزة مفعلة",
        "premium_inactive": "🆓 الباقة المجانية",
        "source": "المصدر",
        "loading": "⏳ جاري جلب البيانات...",
        "error": "⚠️ تعذر جلب البيانات حالياً. حاول مرة أخرى بعد قليل.",
        "premium_title": "💎 Gold & Rates Pro Premium",
        "premium_text": (
            "احصل على تجربة متقدمة مقابل <b>200 ⭐ شهرياً</b>.\n\n"
            "✅ تنبيهات غير محدودة\n"
            "✅ أفضل 50 عملة رقمية\n"
            "✅ تنبيهات فورية\n"
            "✅ سجل الأسعار لـ 7 أيام\n"
            "✅ قائمة مراقبة متقدمة\n"
            "✅ ملخص صباحي مفصل\n"
            "✅ دعم أولوية"
        ),
        "buy": "⭐ شراء Premium — 200 Stars",
        "already": "💎 أنت مشترك بالفعل في Premium.",
        "payment_created": "⭐ تم إنشاء فاتورة الدفع.",
        "payment_success": "🎉 تم تفعيل Premium بنجاح!",
        "premium_expired": "انتهت صلاحية Premium وتم الرجوع إلى الخطة المجانية.",
        "alert_help": (
            "استخدم الأمر التالي لإنشاء تنبيه:\n"
            "<code>/alert BTC above 100000</code>\n"
            "<code>/alert GOLD below 500</code>\n\n"
            "الاتجاهات: above / below / at"
        ),
        "alert_created": "✅ تم إنشاء التنبيه.",
        "alert_limit": "🆓 الحد المجاني هو 3 تنبيهات نشطة.",
        "invalid_alert": "❌ صيغة التنبيه غير صحيحة.",
        "no_alerts": "لا توجد تنبيهات نشطة.",
        "watch_empty": "قائمة المراقبة فارغة.",
        "admin_only": "⛔ هذا الأمر للمشرف فقط.",
        "broadcast_help": "استخدم: /broadcast your message",
        "broadcast_done": "📢 تم إرسال الرسالة إلى المستخدمين.",
        "stats": "📈 الإحصائيات",
        "converter_help": (
            "استخدم:\n"
            "<code>/convert 100 USD SAR</code>\n"
            "<code>/convert 50 EUR PKR</code>"
        ),
        "invalid_convert": "❌ صيغة التحويل غير صحيحة.",
        "digest": "☀️ الملخص الصباحي",
        "history": "📈 سجل 7 أيام",
    },
    "en": {
        "choose_language": "🌍 Choose your language:",
        "choose_interest": "🎯 What do you want to follow?",
        "gold_only": "🥇 Gold Only",
        "currency_only": "💱 Currencies Only",
        "crypto_only": "₿ Crypto Only",
        "full": "🌐 Everything",
        "welcome": (
            "Welcome to <b>Gold & Rates Pro</b> 👋\n\n"
            "Fast and clear gold, currency and crypto rates."
        ),
        "rates": "📊 Live Rates",
        "converter": "🔄 Converter",
        "alert": "🔔 Price Alert",
        "watchlist": "⭐ Watchlist",
        "settings": "⚙️ Settings",
        "premium": "💎 Premium Plan",
        "back": "🔙 Back",
        "gold": "🥇 Gold",
        "currencies": "💱 Currencies",
        "crypto": "₿ Crypto",
        "language": "🌍 Language",
        "interest": "🎯 Interest",
        "premium_active": "💎 Premium Active",
        "premium_inactive": "🆓 Free Plan",
        "source": "Source",
        "loading": "⏳ Loading data...",
        "error": "⚠️ Unable to fetch data right now. Please try again.",
        "premium_title": "💎 Gold & Rates Pro Premium",
        "premium_text": (
            "Get advanced features for <b>200 ⭐ per month</b>.\n\n"
            "✅ Unlimited alerts\n"
            "✅ Top 50 cryptocurrencies\n"
            "✅ Instant alerts\n"
            "✅ 7-day price history\n"
            "✅ Advanced watchlist\n"
            "✅ Detailed morning digest\n"
            "✅ Priority support"
        ),
        "buy": "⭐ Buy Premium — 200 Stars",
        "already": "💎 You already have Premium.",
        "payment_created": "⭐ Payment invoice created.",
        "payment_success": "🎉 Premium activated successfully!",
        "premium_expired": "Your Premium expired. You are back on the Free plan.",
        "alert_help": (
            "Create an alert with:\n"
            "<code>/alert BTC above 100000</code>\n"
            "<code>/alert GOLD below 500</code>\n\n"
            "Directions: above / below / at"
        ),
        "alert_created": "✅ Alert created.",
        "alert_limit": "🆓 Free users can have 3 active alerts.",
        "invalid_alert": "❌ Invalid alert format.",
        "no_alerts": "No active alerts.",
        "watch_empty": "Your watchlist is empty.",
        "admin_only": "⛔ Admin only.",
        "broadcast_help": "Use: /broadcast your message",
        "broadcast_done": "📢 Broadcast sent.",
        "stats": "📈 Statistics",
        "converter_help": (
            "Use:\n"
            "<code>/convert 100 USD SAR</code>\n"
            "<code>/convert 50 EUR PKR</code>"
        ),
        "invalid_convert": "❌ Invalid conversion format.",
        "digest": "☀️ Morning Digest",
        "history": "📈 7-Day History",
    },
    "ur": {
        "choose_language": "🌍 اپنی زبان منتخب کریں:",
        "choose_interest": "🎯 آپ کیا دیکھنا چاہتے ہیں؟",
        "gold_only": "🥇 صرف گولڈ",
        "currency_only": "💱 صرف کرنسی",
        "crypto_only": "₿ صرف کرپٹو",
        "full": "🌐 سب کچھ",
        "welcome": (
            "خوش آمدید <b>Gold & Rates Pro</b> 👋\n\n"
            "گولڈ، کرنسی اور کرپٹو کے ریٹس تیزی سے حاصل کریں۔"
        ),
        "rates": "📊 آج کے ریٹس",
        "converter": "🔄 کنورٹر",
        "alert": "🔔 پرائس الرٹ",
        "watchlist": "⭐ میری واچ لسٹ",
        "settings": "⚙️ سیٹنگز",
        "premium": "💎 پریمیم پلان",
        "back": "🔙 واپس",
        "gold": "🥇 گولڈ",
        "currencies": "💱 کرنسیز",
        "crypto": "₿ کرپٹو",
        "language": "🌍 زبان",
        "interest": "🎯 دلچسپی",
        "premium_active": "💎 پریمیم فعال ہے",
        "premium_inactive": "🆓 فری پلان",
        "source": "سورس",
        "loading": "⏳ ڈیٹا حاصل کیا جا رہا ہے...",
        "error": "⚠️ اس وقت ڈیٹا حاصل نہیں ہو سکا، دوبارہ کوشش کریں۔",
        "premium_title": "💎 Gold & Rates Pro Premium",
        "premium_text": (
            "<b>200 ⭐ ماہانہ</b> میں Premium حاصل کریں۔\n\n"
            "✅ Unlimited alerts\n"
            "✅ Top 50 cryptocurrencies\n"
            "✅ فوری alerts\n"
            "✅ 7 دن کی price history\n"
            "✅ Advanced watchlist\n"
            "✅ Detailed morning digest\n"
            "✅ Priority support"
        ),
        "buy": "⭐ Premium خریدیں — 200 Stars",
        "already": "💎 آپ کے پاس پہلے ہی Premium ہے۔",
        "payment_created": "⭐ Payment invoice تیار ہے۔",
        "payment_success": "🎉 Premium کامیابی سے فعال ہوگیا!",
        "premium_expired": "آپ کا Premium ختم ہوگیا، آپ Free plan پر واپس آگئے ہیں۔",
        "alert_help": (
            "الرٹ بنانے کے لیے:\n"
            "<code>/alert BTC above 100000</code>\n"
            "<code>/alert GOLD below 500</code>\n\n"
            "Directions: above / below / at"
        ),
        "alert_created": "✅ الرٹ بن گیا۔",
        "alert_limit": "🆓 Free users کے لیے 3 active alerts کی حد ہے۔",
        "invalid_alert": "❌ Alert کا format درست نہیں۔",
        "no_alerts": "کوئی active alert نہیں۔",
        "watch_empty": "آپ کی watchlist خالی ہے۔",
        "admin_only": "⛔ صرف Admin کے لیے۔",
        "broadcast_help": "استعمال: /broadcast your message",
        "broadcast_done": "📢 Broadcast بھیج دیا گیا۔",
        "stats": "📈 اعداد و شمار",
        "converter_help": (
            "استعمال:\n"
            "<code>/convert 100 USD SAR</code>\n"
            "<code>/convert 50 EUR PKR</code>"
        ),
        "invalid_convert": "❌ Conversion format درست نہیں۔",
        "digest": "☀️ صبح کا ڈائجسٹ",
        "history": "📈 7 دن کی تاریخ",
    },
}


def tr(lang, key):
    return TEXT.get(lang, TEXT["ar"]).get(key, key)


def now_ts():
    return int(time.time())


def utc_now():
    return datetime.now(timezone.utc)


def format_number(value, decimals=2):
    try:
        return f"{float(value):,.{decimals}f}"
    except Exception:
        return str(value)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT NOT NULL DEFAULT 'ar',
            interest TEXT NOT NULL DEFAULT 'full',
            is_premium INTEGER NOT NULL DEFAULT 0,
            premium_until INTEGER,
            created_at INTEGER NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            asset TEXT NOT NULL,
            target_price REAL NOT NULL,
            direction TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            triggered_at INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            user_id INTEGER NOT NULL,
            asset TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, asset)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset TEXT NOT NULL,
            price REAL NOT NULL,
            quote TEXT NOT NULL,
            recorded_at INTEGER NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            charge_id TEXT,
            stars INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = db()
    row = conn.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return row


def ensure_user(user_id):
    conn = db()
    row = conn.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if not row:
        conn.execute(
            """
            INSERT INTO users
            (user_id, language, interest, is_premium, premium_until, created_at)
            VALUES (?, 'ar', 'full', 0, NULL, ?)
            """,
            (user_id, now_ts()),
        )
        conn.commit()

    conn.close()


def set_language(user_id, language):
    conn = db()
    conn.execute(
        "UPDATE users SET language = ? WHERE user_id = ?",
        (language, user_id),
    )
    conn.commit()
    conn.close()


def set_interest(user_id, interest):
    conn = db()
    conn.execute(
        "UPDATE users SET interest = ? WHERE user_id = ?",
        (interest, user_id),
    )
    conn.commit()
    conn.close()


def is_premium(user_id):
    row = get_user(user_id)

    if not row:
        return False

    until = row["premium_until"]

    if row["is_premium"] and until and until > now_ts():
        return True

    if row["is_premium"]:
        conn = db()
        conn.execute(
            """
            UPDATE users
            SET is_premium = 0, premium_until = NULL
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()
        conn.close()

    return False


def activate_premium(user_id, days=PREMIUM_DAYS):
    until = now_ts() + days * 86400

    conn = db()
    conn.execute(
        """
        UPDATE users
        SET is_premium = 1, premium_until = ?
        WHERE user_id = ?
        """,
        (until, user_id),
    )
    conn.commit()
    conn.close()


def save_payment(user_id, charge_id, stars):
    conn = db()
    conn.execute(
        """
        INSERT INTO payments
        (user_id, charge_id, stars, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, charge_id, stars, now_ts()),
    )
    conn.commit()
    conn.close()


def active_alert_count(user_id):
    conn = db()
    row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM alerts
        WHERE user_id = ? AND is_active = 1
        """,
        (user_id,),
    ).fetchone()
    conn.close()
    return int(row["c"])


def create_alert(user_id, asset, target, direction):
    conn = db()
    conn.execute(
        """
        INSERT INTO alerts
        (user_id, asset, target_price, direction, is_active, created_at)
        VALUES (?, ?, ?, ?, 1, ?)
        """,
        (user_id, asset.upper(), target, direction, now_ts()),
    )
    conn.commit()
    conn.close()


def get_active_alerts():
    conn = db()
    rows = conn.execute(
        """
        SELECT *
        FROM alerts
        WHERE is_active = 1
        """
    ).fetchall()
    conn.close()
    return rows


def deactivate_alert(alert_id):
    conn = db()
    conn.execute(
        """
        UPDATE alerts
        SET is_active = 0, triggered_at = ?
        WHERE id = ?
        """,
        (now_ts(), alert_id),
    )
    conn.commit()
    conn.close()


def add_watch(user_id, asset):
    conn = db()
    conn.execute(
        """
        INSERT OR IGNORE INTO watchlist
        (user_id, asset, created_at)
        VALUES (?, ?, ?)
        """,
        (user_id, asset.upper(), now_ts()),
    )
    conn.commit()
    conn.close()


def remove_watch(user_id, asset):
    conn = db()
    conn.execute(
        """
        DELETE FROM watchlist
        WHERE user_id = ? AND asset = ?
        """,
        (user_id, asset.upper()),
    )
    conn.commit()
    conn.close()


def get_watchlist(user_id):
    conn = db()
    rows = conn.execute(
        """
        SELECT asset
        FROM watchlist
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return [r["asset"] for r in rows]


def save_history(asset, price, quote="USD"):
    conn = db()
    conn.execute(
        """
        INSERT INTO price_history
        (asset, price, quote, recorded_at)
        VALUES (?, ?, ?, ?)
        """,
        (asset.upper(), float(price), quote, now_ts()),
    )

    cutoff = now_ts() - 14 * 86400

    conn.execute(
        """
        DELETE FROM price_history
        WHERE recorded_at < ?
        """,
        (cutoff,),
    )

    conn.commit()
    conn.close()


def get_history(asset, days=7):
    cutoff = now_ts() - days * 86400

    conn = db()
    rows = conn.execute(
        """
        SELECT price, quote, recorded_at
        FROM price_history
        WHERE asset = ? AND recorded_at >= ?
        ORDER BY recorded_at ASC
        """,
        (asset.upper(), cutoff),
    ).fetchall()
    conn.close()

    return rows


def stats():
    conn = db()

    users = conn.execute(
        "SELECT COUNT(*) AS c FROM users"
    ).fetchone()["c"]

    premium = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM users
        WHERE is_premium = 1 AND premium_until > ?
        """,
        (now_ts(),),
    ).fetchone()["c"]

    alerts = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM alerts
        WHERE is_active = 1
        """
    ).fetchone()["c"]

    conn.close()

    return users, premium, alerts


async def http_get_json(url, params=None, headers=None):
    global http_session

    if http_session is None:
        http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        )

    async with http_session.get(
        url,
        params=params,
        headers=headers,
    ) as response:
        if response.status >= 400:
            raise RuntimeError(
                f"HTTP {response.status}: {await response.text()}"
            )

        return await response.json()


async def cached_json(key, url, params=None, ttl=CACHE_TTL, headers=None):
    current = time.time()

    async with cache_lock:
        item = memory_cache.get(key)

        if item and current - item["time"] < ttl:
            return item["data"]

    data = await http_get_json(url, params=params, headers=headers)

    async with cache_lock:
        memory_cache[key] = {
            "time": current,
            "data": data,
        }

    return data


async def get_fx_rates():
    data = await cached_json(
        "fx_usd",
        f"{FRANKFURTER_URL}/rates",
        params={
            "base": "USD",
            "quotes": ",".join(
                x for x in CURRENCY_LIST if x != "USD"
            ),
        },
        ttl=3600,
    )

    result = {"USD": 1.0}

    for row in data:
        quote = row.get("quote")
        rate = row.get("rate")

        if quote and rate is not None:
            result[quote] = float(rate)

    if "SAR" not in result:
        result["SAR"] = 3.75

    return result


async def get_crypto_prices(premium=False):
    ids = CRYPTO_PREMIUM if premium else CRYPTO_FREE

    data = await cached_json(
        f"crypto_{premium}",
        f"{COINGECKO_URL}/simple/price",
        params={
            "ids": ",".join(ids),
            "vs_currencies": "usd,sar",
            "include_24hr_change": "true",
        },
        ttl=300,
    )

    return data


async def get_gold_usd():
    data = await cached_json(
        "gold_usd",
        GOLD_URL,
        params={"symbol": "XAU-USD-SPOT"},
        ttl=300,
    )

    symbols = data.get("symbols", [])

    if not symbols:
        raise RuntimeError("Gold API returned no symbols")

    price = float(symbols[0]["price"])

    return price


async def get_gold():
    gold_usd_oz = await get_gold_usd()

    fx = await get_fx_rates()

    usd_sar = float(fx.get("SAR", 3.75))

    sar_oz = gold_usd_oz * usd_sar

    grams_per_troy_ounce = 31.1034768

    sar_gram = sar_oz / grams_per_troy_ounce
    usd_gram = gold_usd_oz / grams_per_troy_ounce

    sar_tola = sar_gram * 11.6638125
    usd_tola = usd_gram * 11.6638125

    return {
        "usd_oz": gold_usd_oz,
        "sar_oz": sar_oz,
        "usd_gram": usd_gram,
        "sar_gram": sar_gram,
        "usd_tola": usd_tola,
        "sar_tola": sar_tola,
    }


async def get_all_rates():
    gold = await get_gold()
    fx = await get_fx_rates()
    crypto = await get_crypto_prices(False)

    return {
        "gold": gold,
        "fx": fx,
        "crypto": crypto,
    }


def lang_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="العربية",
                    callback_data="lang:ar",
                ),
                InlineKeyboardButton(
                    text="English",
                    callback_data="lang:en",
                ),
                InlineKeyboardButton(
                    text="اردو",
                    callback_data="lang:ur",
                ),
            ]
        ]
    )


def interest_keyboard(lang):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(lang, "gold_only"),
                    callback_data="interest:gold",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "currency_only"),
                    callback_data="interest:currency",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "crypto_only"),
                    callback_data="interest:crypto",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "full"),
                    callback_data="interest:full",
                )
            ],
        ]
    )


def main_keyboard(lang, premium=False, interest="full"):
    rows = []

    if interest in ("gold", "full"):
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr(lang, "gold"),
                    callback_data="rates:gold",
                )
            ]
        )

    if interest in ("currency", "full"):
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr(lang, "currencies"),
                    callback_data="rates:currency",
                )
            ]
        )

    if interest in ("crypto", "full"):
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr(lang, "crypto"),
                    callback_data="rates:crypto",
                )
            ]
        )

    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text=tr(lang, "rates"),
                    callback_data="rates:all",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "converter"),
                    callback_data="converter",
                ),
                InlineKeyboardButton(
                    text=tr(lang, "alert"),
                    callback_data="alert_help",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "watchlist"),
                    callback_data="watchlist",
                ),
                InlineKeyboardButton(
                    text=tr(lang, "settings"),
                    callback_data="settings",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=(
                        tr(lang, "premium_active")
                        if premium
                        else tr(lang, "premium")
                    ),
                    callback_data="premium",
                )
            ],
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(lang):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(lang, "language"),
                    callback_data="settings:language",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "interest"),
                    callback_data="settings:interest",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "back"),
                    callback_data="home",
                )
            ],
        ]
    )


def premium_keyboard(lang):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(lang, "buy"),
                    callback_data="buy_premium",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "back"),
                    callback_data="home",
                )
            ],
        ]
    )


async def send_home(message, user_id):
    ensure_user(user_id)
    user = get_user(user_id)

    lang = user["language"]
    premium = is_premium(user_id)

    await message.answer(
        tr(lang, "welcome"),
        reply_markup=main_keyboard(
            lang,
            premium,
            user["interest"],
        ),
    )


@dp.message(CommandStart())
async def start_handler(message: Message):
    ensure_user(message.from_user.id)

    await message.answer(
        "🌍 Gold & Rates Pro\n\n"
        + "Choose your language / اختر لغتك / اپنی زبان منتخب کریں:",
        reply_markup=lang_keyboard(),
    )


@dp.callback_query(F.data.startswith("lang:"))
async def language_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = callback.data.split(":", 1)[1]

    if lang not in SUPPORTED_LANGUAGES:
        lang = "ar"

    ensure_user(user_id)
    set_language(user_id, lang)

    await callback.message.edit_text(
        tr(lang, "choose_interest"),
        reply_markup=interest_keyboard(lang),
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("interest:"))
async def interest_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    interest = callback.data.split(":", 1)[1]

    ensure_user(user_id)

    if interest not in SUPPORTED_INTERESTS:
        interest = "full"

    set_interest(user_id, interest)

    user = get_user(user_id)
    lang = user["language"]

    await callback.message.edit_text(
        tr(lang, "welcome"),
        reply_markup=main_keyboard(
            lang,
            is_premium(user_id),
            interest,
        ),
    )

    await callback.answer()


@dp.callback_query(F.data == "home")
async def home_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    ensure_user(user_id)

    user = get_user(user_id)
    lang = user["language"]

    await callback.message.edit_text(
        tr(lang, "welcome"),
        reply_markup=main_keyboard(
            lang,
            is_premium(user_id),
            user["interest"],
        ),
    )

    await callback.answer()


async def format_gold(lang):
    gold = await get_gold()

    return (
        f"<b>{tr(lang, 'gold')}</b>\n\n"
        f"24K / gram:\n"
        f"🇸🇦 {format_number(gold['sar_gram'])} SAR\n"
        f"🇺🇸 {format_number(gold['usd_gram'])} USD\n\n"
        f"24K / tola:\n"
        f"🇸🇦 {format_number(gold['sar_tola'])} SAR\n"
        f"🇺🇸 {format_number(gold['usd_tola'])} USD\n\n"
        f"1 troy oz:\n"
        f"🇸🇦 {format_number(gold['sar_oz'])} SAR\n"
        f"🇺🇸 {format_number(gold['usd_oz'])} USD\n\n"
        f"ℹ️ {tr(lang, 'source')}: goldprice.dev"
    )


async def format_currencies(lang):
    fx = await get_fx_rates()

    lines = [f"<b>{tr(lang, 'currencies')}</b>\n"]

    for currency in CURRENCY_LIST:
        value = fx.get(currency)

        if value is None:
            continue

        lines.append(
            f"USD → {currency}: <b>{format_number(value, 4)}</b>"
        )

    lines.append("\nℹ️ Source: Frankfurter")

    return "\n".join(lines)


async def format_crypto(lang, premium=False):
    data = await get_crypto_prices(premium)

    limit = 50 if premium else 20

    lines = [
        f"<b>{tr(lang, 'crypto')}</b>",
        "",
    ]

    for index, coin_id in enumerate(
        CRYPTO_PREMIUM if premium else CRYPTO_FREE,
        start=1,
    ):
        if index > limit:
            break

        item = data.get(coin_id)

        if not item:
            continue

        usd = item.get("usd")
        sar = item.get("sar")
        change = item.get("usd_24h_change")

        symbol = CRYPTO_SYMBOLS.get(
            coin_id,
            coin_id.upper(),
        )

        change_text = (
            f"{float(change):+.2f}%"
            if change is not None
            else "N/A"
        )

        lines.append(
            f"{index}. <b>{symbol}</b>  "
            f"${format_number(usd)}  |  "
            f"{format_number(sar)} SAR  "
            f"({change_text})"
        )

    lines.append("\nℹ️ Source: CoinGecko")

    if not premium:
        lines.append(
            "\n💎 Premium unlocks Top 50 crypto."
        )

    return "\n".join(lines)


@dp.callback_query(F.data.startswith("rates:"))
async def rates_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    ensure_user(user_id)

    user = get_user(user_id)
    lang = user["language"]
    kind = callback.data.split(":", 1)[1]
    premium = is_premium(user_id)

    await callback.answer(tr(lang, "loading"))

    try:
        if kind == "gold":
            text = await format_gold(lang)

        elif kind == "currency":
            text = await format_currencies(lang)

        elif kind == "crypto":
            text = await format_crypto(lang, premium)

        else:
            gold_text = await format_gold(lang)
            fx_text = await format_currencies(lang)

            crypto_text = await format_crypto(
                lang,
                premium,
            )

            text = (
                f"{gold_text}\n\n"
                f"━━━━━━━━━━━━━━\n\n"
                f"{fx_text}\n\n"
                f"━━━━━━━━━━━━━━\n\n"
                f"{crypto_text}"
            )

        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=tr(lang, "back"),
                            callback_data="home",
                        )
                    ]
                ]
            ),
        )

    except Exception:
        logger.exception("Rate request failed")

        await callback.message.edit_text(
            tr(lang, "error"),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=tr(lang, "back"),
                            callback_data="home",
                        )
                    ]
                ]
            ),
        )


@dp.callback_query(F.data == "converter")
async def converter_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    ensure_user(user_id)

    lang = get_user(user_id)["language"]

    await callback.message.answer(
        tr(lang, "converter_help")
    )

    await callback.answer()


@dp.message(Command("convert"))
async def convert_handler(message: Message):
    ensure_user(message.from_user.id)

    user = get_user(message.from_user.id)
    lang = user["language"]

    parts = message.text.split()

    if len(parts) != 4:
        await message.answer(
            tr(lang, "invalid_convert")
            + "\n\n"
            + tr(lang, "converter_help")
        )
        return

    try:
        amount = float(parts[1])
        base = parts[2].upper()
        quote = parts[3].upper()

        if base not in CURRENCY_LIST:
            raise ValueError()

        if quote not in CURRENCY_LIST:
            raise ValueError()

        fx = await get_fx_rates()

        usd_base = fx.get(base)
        usd_quote = fx.get(quote)

        if usd_base is None or usd_quote is None:
            raise ValueError()

        result = amount / usd_base * usd_quote

        await message.answer(
            f"<b>{format_number(amount, 4)} {base}</b> = "
            f"<b>{format_number(result, 4)} {quote}</b>\n\n"
            f"ℹ️ Source: Frankfurter"
        )

    except Exception:
        await message.answer(
            tr(lang, "invalid_convert")
        )


@dp.callback_query(F.data == "alert_help")
async def alert_help_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    ensure_user(user_id)

    lang = get_user(user_id)["language"]

    await callback.message.answer(
        tr(lang, "alert_help")
    )

    await callback.answer()


@dp.message(Command("alert"))
async def alert_handler(message: Message):
    ensure_user(message.from_user.id)

    user_id = message.from_user.id
    lang = get_user(user_id)["language"]

    parts = message.text.split()

    if len(parts) != 4:
        await message.answer(tr(lang, "invalid_alert"))
        return

    asset = parts[1].upper()
    direction = parts[2].lower()

    try:
        target = float(parts[3])
    except ValueError:
        await message.answer(tr(lang, "invalid_alert"))
        return

    if direction not in ("above", "below", "at"):
        await message.answer(tr(lang, "invalid_alert"))
        return

    premium = is_premium(user_id)

    if not premium and active_alert_count(user_id) >= 3:
        await message.answer(tr(lang, "alert_limit"))
        return

    valid_assets = {
        "GOLD",
        "BTC",
        "ETH",
        "USDT",
        "BNB",
        "SOL",
        "XRP",
        "USDC",
        "DOGE",
        "ADA",
        "AVAX",
        "TRX",
        "LINK",
        "SHIB",
        "DOT",
        "LTC",
        "XLM",
    }

    if asset not in valid_assets:
        await message.answer(
            tr(lang, "invalid_alert")
        )
        return

    create_alert(
        user_id,
        asset,
        target,
        direction,
    )

    await message.answer(
        f"{tr(lang, 'alert_created')}\n\n"
        f"Asset: <b>{asset}</b>\n"
        f"Direction: <b>{direction}</b>\n"
        f"Target: <b>{format_number(target)}</b>"
    )


@dp.callback_query(F.data == "watchlist")
async def watchlist_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    ensure_user(user_id)

    lang = get_user(user_id)["language"]
    items = get_watchlist(user_id)

    if not items:
        text = tr(lang, "watch_empty")
    else:
        text = (
            f"<b>{tr(lang, 'watchlist')}</b>\n\n"
            + "\n".join(
                f"• {asset}" for asset in items
            )
            + "\n\n"
            + "Add with: /watch BTC"
            + "\nRemove with: /unwatch BTC"
        )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=tr(lang, "back"),
                        callback_data="home",
                    )
                ]
            ]
        ),
    )

    await callback.answer()


@dp.message(Command("watch"))
async def watch_handler(message: Message):
    ensure_user(message.from_user.id)

    user_id = message.from_user.id
    lang = get_user(user_id)["language"]

    parts = message.text.split()

    if len(parts) != 2:
        await message.answer(
            "Use: /watch BTC"
        )
        return

    add_watch(
        user_id,
        parts[1].upper(),
    )

    await message.answer(
        f"⭐ Added <b>{parts[1].upper()}</b> to your watchlist."
    )


@dp.message(Command("unwatch"))
async def unwatch_handler(message: Message):
    ensure_user(message.from_user.id)

    user_id = message.from_user.id
    parts = message.text.split()

    if len(parts) != 2:
        await message.answer(
            "Use: /unwatch BTC"
        )
        return

    remove_watch(
        user_id,
        parts[1].upper(),
    )

    await message.answer(
        f"Removed <b>{parts[1].upper()}</b>."
    )


@dp.callback_query(F.data == "settings")
async def settings_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    ensure_user(user_id)

    lang = get_user(user_id)["language"]

    await callback.message.edit_text(
        f"<b>{tr(lang, 'settings')}</b>",
        reply_markup=settings_keyboard(lang),
    )

    await callback.answer()


@dp.callback_query(F.data == "settings:language")
async def settings_language_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "🌍 Choose language / اختر اللغة / زبان منتخب کریں:",
        reply_markup=lang_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "settings:interest")
async def settings_interest_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user(user_id)["language"]

    await callback.message.edit_text(
        tr(lang, "choose_interest"),
        reply_markup=interest_keyboard(lang),
    )

    await callback.answer()


@dp.callback_query(F.data == "premium")
async def premium_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    ensure_user(user_id)

    lang = get_user(user_id)["language"]

    if is_premium(user_id):
        user = get_user(user_id)
        expiry = datetime.fromtimestamp(
            user["premium_until"],
            tz=timezone.utc,
        ).strftime("%Y-%m-%d")

        await callback.message.edit_text(
            tr(lang, "already")
            + f"\n\nExpires: <b>{expiry}</b>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=tr(lang, "back"),
                            callback_data="home",
                        )
                    ]
                ]
            ),
        )

    else:
        await callback.message.edit_text(
            f"<b>{tr(lang, 'premium_title')}</b>\n\n"
            f"{tr(lang, 'premium_text')}",
            reply_markup=premium_keyboard(lang),
        )

    await callback.answer()


@dp.callback_query(F.data == "buy_premium")
async def buy_premium_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    ensure_user(user_id)

    lang = get_user(user_id)["language"]

    if is_premium(user_id):
        await callback.answer(
            tr(lang, "already"),
            show_alert=True,
        )
        return

    await callback.message.answer(
        tr(lang, "payment_created")
    )

    await callback.message.answer_invoice(
        title="Gold & Rates Pro Premium",
        description=(
            "30-day Premium access: unlimited alerts, "
            "Top 50 crypto, instant alerts, 7-day history "
            "and advanced features."
        ),
        payload=f"premium:{user_id}:{now_ts()}",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="Premium — 30 days",
                amount=PREMIUM_STARS,
            )
        ],
        provider_token="",
    )

    await callback.answer()


@dp.pre_checkout_query()
async def pre_checkout_handler(
    query: PreCheckoutQuery,
):
    try:
        payload = query.invoice_payload

        if not payload.startswith("premium:"):
            await query.answer(
                ok=False,
                error_message="Invalid payment.",
            )
            return

        await query.answer(ok=True)

    except Exception:
        logger.exception(
            "Pre-checkout processing failed"
        )

        try:
            await query.answer(
                ok=False,
                error_message="Payment validation failed.",
            )
        except Exception:
            pass


@dp.message(F.successful_payment)
async def successful_payment_handler(
    message: Message,
):
    user_id = message.from_user.id
    ensure_user(user_id)

    payment = message.successful_payment

    charge_id = payment.telegram_payment_charge_id

    save_payment(
        user_id,
        charge_id,
        PREMIUM_STARS,
    )

    activate_premium(
        user_id,
        PREMIUM_DAYS,
    )

    lang = get_user(user_id)["language"]

    await message.answer(
        tr(lang, "payment_success")
        + "\n\n"
        + "💎 Premium: 30 days"
    )


@dp.callback_query(F.data == "history")
async def history_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    ensure_user(user_id)

    lang = get_user(user_id)["language"]

    if not is_premium(user_id):
        await callback.answer(
            "Premium feature",
            show_alert=True,
        )
        return

    rows = get_history("BTC", 7)

    if not rows:
        await callback.message.answer(
            "No BTC history collected yet."
        )
        await callback.answer()
        return

    lines = [
        f"<b>{tr(lang, 'history')} — BTC</b>",
        "",
    ]

    for row in rows[-20:]:
        dt = datetime.fromtimestamp(
            row["recorded_at"],
            timezone.utc,
        ).strftime("%m-%d %H:%M")

        lines.append(
            f"{dt} UTC — "
            f"${format_number(row['price'])}"
        )

    await callback.message.answer(
        "\n".join(lines)
    )

    await callback.answer() 
    async def get_asset_price_usd(asset):
    asset = asset.upper()

    if asset == "GOLD":
        return await get_gold_usd()

    coin_id = None

    for cid, symbol in CRYPTO_SYMBOLS.items():
        if symbol == asset:
            coin_id = cid
            break

    if not coin_id:
        return None

    data = await get_crypto_prices(True)

    item = data.get(coin_id)

    if not item:
        return None

    return float(item["usd"])


async def record_current_prices():
    try:
        gold = await get_gold_usd()
        save_history("GOLD", gold, "USD")
    except Exception:
        logger.exception("Could not record gold history")

    try:
        data = await get_crypto_prices(True)

        for coin_id, item in data.items():
            if item.get("usd") is None:
                continue

            symbol = CRYPTO_SYMBOLS.get(
                coin_id,
                coin_id.upper(),
            )

            save_history(
                symbol,
                float(item["usd"]),
                "USD",
            )

    except Exception:
        logger.exception(
            "Could not record crypto history"
        )


async def check_alerts(bot: Bot):
    rows = get_active_alerts()

    if not rows:
        return

    premium_cache = {}

    for alert in rows:
        user_id = alert["user_id"]
        asset = alert["asset"]
        target = float(alert["target_price"])
        direction = alert["direction"]

        try:
            current = await get_asset_price_usd(asset)

            if current is None:
                continue

            triggered = False

            if direction == "above" and current >= target:
                triggered = True

            elif direction == "below" and current <= target:
                triggered = True

            elif direction == "at":
                tolerance = max(
                    target * 0.001,
                    0.01,
                )

                if abs(current - target) <= tolerance:
                    triggered = True

            if not triggered:
                continue

            deactivate_alert(alert["id"])

            if user_id not in premium_cache:
                premium_cache[user_id] = is_premium(
                    user_id
                )

            lang_row = get_user(user_id)

            if not lang_row:
                continue

            lang = lang_row["language"]

            message = (
                "🔔 <b>PRICE ALERT</b>\n\n"
                f"Asset: <b>{asset}</b>\n"
                f"Current price: <b>"
                f"{format_number(current)}</b> USD\n"
                f"Target: <b>"
                f"{format_number(target)}</b> USD\n"
                f"Direction: <b>{direction}</b>"
            )

            try:
                await bot.send_message(
                    user_id,
                    message,
                )
            except Exception:
                logger.exception(
                    "Could not send alert to %s",
                    user_id,
                )

        except Exception:
            logger.exception(
                "Alert check failed for %s",
                alert["id"],
            )


async def market_worker(bot: Bot):
    while True:
        try:
            await record_current_prices()
        except Exception:
            logger.exception(
                "Market history worker failed"
            )

        await asyncio.sleep(900)


async def alert_worker(bot: Bot):
    while True:
        try:
            await check_alerts(bot)
        except Exception:
            logger.exception(
                "Alert worker failed"
            )

        await asyncio.sleep(60)


async def expiry_worker(bot: Bot):
    while True:
        try:
            conn = db()

            rows = conn.execute(
                """
                SELECT user_id
                FROM users
                WHERE is_premium = 1
                AND premium_until IS NOT NULL
                AND premium_until <= ?
                """,
                (now_ts(),),
            ).fetchall()

            for row in rows:
                user_id = row["user_id"]

                conn.execute(
                    """
                    UPDATE users
                    SET is_premium = 0,
                        premium_until = NULL
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )

                try:
                    user = get_user(user_id)

                    if user:
                        await bot.send_message(
                            user_id,
                            tr(
                                user["language"],
                                "premium_expired",
                            ),
                        )
                except Exception:
                    logger.exception(
                        "Could not notify expired user"
                    )

            conn.commit()
            conn.close()

        except Exception:
            logger.exception(
                "Expiry worker failed"
            )

        await asyncio.sleep(3600)


async def cleanup_worker():
    global memory_cache

    while True:
        try:
            current = time.time()

            async with cache_lock:
                memory_cache = {
                    key: value
                    for key, value in memory_cache.items()
                    if current - value["time"] < 7200
                }

        except Exception:
            logger.exception(
                "Cache cleanup failed"
            )

        await asyncio.sleep(1800)


@dp.message(Command("stats"))
async def stats_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        ensure_user(message.from_user.id)

        user = get_user(message.from_user.id)

        await message.answer(
            tr(
                user["language"],
                "admin_only",
            )
        )
        return

    users, premium, alerts = stats()

    await message.answer(
        "<b>Gold & Rates Pro — Admin Statistics</b>\n\n"
        f"👥 Total users: <b>{users}</b>\n"
        f"💎 Premium users: <b>{premium}</b>\n"
        f"🔔 Active alerts: <b>{alerts}</b>"
    )


@dp.message(Command("broadcast"))
async def broadcast_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        ensure_user(message.from_user.id)

        user = get_user(message.from_user.id)

        await message.answer(
            tr(
                user["language"],
                "admin_only",
            )
        )
        return

    text = message.text.partition(" ")[2].strip()

    if not text:
        await message.answer(
            "Usage: /broadcast your message"
        )
        return

    conn = db()

    users = conn.execute(
        "SELECT user_id FROM users"
    ).fetchall()

    conn.close()

    sent = 0

    for row in users:
        try:
            await message.bot.send_message(
                row["user_id"],
                text,
            )

            sent += 1

            await asyncio.sleep(0.05)

        except Exception:
            continue

    await message.answer(
        f"Broadcast completed.\nSent: {sent}"
    )


@dp.message(Command("id"))
async def id_handler(message: Message):
    await message.answer(
        f"Your Telegram ID:\n<code>{message.from_user.id}</code>"
    )


@dp.message(Command("premium"))
async def premium_command_handler(
    message: Message,
):
    ensure_user(message.from_user.id)

    user_id = message.from_user.id
    lang = get_user(user_id)["language"]

    if is_premium(user_id):
        user = get_user(user_id)

        expiry = datetime.fromtimestamp(
            user["premium_until"],
            timezone.utc,
        ).strftime("%Y-%m-%d")

        await message.answer(
            tr(lang, "already")
            + f"\n\nExpires: <b>{expiry}</b>"
        )

        return

    await message.answer(
        f"<b>{tr(lang, 'premium_title')}</b>\n\n"
        f"{tr(lang, 'premium_text')}",
        reply_markup=premium_keyboard(lang),
    )


@dp.message(Command("rates"))
async def rates_command_handler(
    message: Message,
):
    ensure_user(message.from_user.id)

    user_id = message.from_user.id
    user = get_user(user_id)
    lang = user["language"]

    try:
        gold = await format_gold(lang)
        currency = await format_currencies(lang)

        crypto = await format_crypto(
            lang,
            is_premium(user_id),
        )

        await message.answer(
            f"{gold}\n\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"{currency}\n\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"{crypto}"
        )

    except Exception:
        logger.exception(
            "Rates command failed"
        )

        await message.answer(
            tr(lang, "error")
        )


@dp.message(Command("digest"))
async def digest_command_handler(
    message: Message,
):
    ensure_user(message.from_user.id)

    user_id = message.from_user.id
    user = get_user(user_id)
    lang = user["language"]
    premium = is_premium(user_id)

    try:
        gold = await get_gold()
        fx = await get_fx_rates()
        crypto = await get_crypto_prices(premium)

        btc = crypto.get("bitcoin", {})
        eth = crypto.get("ethereum", {})

        text = (
            f"<b>{tr(lang, 'digest')}</b>\n\n"
            f"🥇 Gold 24K:\n"
            f"{format_number(gold['sar_gram'])} SAR/g\n\n"
            f"💵 USD/SAR:\n"
            f"{format_number(fx.get('SAR', 3.75), 4)}\n\n"
            f"₿ BTC:\n"
            f"${format_number(btc.get('usd', 0))}\n\n"
            f"♦️ ETH:\n"
            f"${format_number(eth.get('usd', 0))}\n\n"
            f"ℹ️ Gold: goldprice.dev\n"
            f"ℹ️ FX: Frankfurter\n"
            f"ℹ️ Crypto: CoinGecko"
        )

        await message.answer(text)

    except Exception:
        await message.answer(
            tr(lang, "error")
        )


@dp.message()
async def fallback_handler(message: Message):
    if not message.from_user:
        return

    ensure_user(message.from_user.id)

    user = get_user(message.from_user.id)
    lang = user["language"]

    await message.answer(
        tr(lang, "welcome"),
        reply_markup=main_keyboard(
            lang,
            is_premium(message.from_user.id),
            user["interest"],
        ),
    )


async def main():
    global http_session

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. "
            "Add BOT_TOKEN to Replit Secrets."
        )

    init_db()

    bot = Bot(
        token=BOT_TOKEN
    )

    http_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(
            total=15
        )
    )

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    logger.info(
        "Gold & Rates Pro is starting..."
    )

    tasks = [
        asyncio.create_task(
            alert_worker(bot)
        ),
        asyncio.create_task(
            market_worker(bot)
        ),
        asyncio.create_task(
            expiry_worker(bot)
        ),
        asyncio.create_task(
            cleanup_worker()
        ),
    ]

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )

    finally:
        for task in tasks:
            task.cancel()

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        if http_session:
            await http_session.close()

        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info(
            "Gold & Rates Pro stopped."
        )
