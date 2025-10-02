import os
import sys
import traceback
import json
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

def get_env(name):
    value = os.getenv(name)
    if value is None:
        print(f"❌ ERROR: Environment variable {name} is not set!")
        sys.exit(1)
    return value
# ================= CONFIG =================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
OWNER_IDS = list(map(int, os.getenv("OWNER_IDS").split(",")))
MILESTONE = int(os.getenv("MILESTONE", "2"))

# Persistent data paths
DATA_DIR = os.getenv("DATA_DIR", "./data")  # Railway root folder
os.makedirs(DATA_DIR, exist_ok=True)

SESSION_FILE = os.path.join(DATA_DIR, "session.txt")
DATA_FILE = os.path.join(DATA_DIR, "ref_data.json")

# ================== SETUP ==================
# Load saved data
try:
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
except FileNotFoundError:
    data = {"referrals": {}, "ref_counts": {}, "rewarded": []}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

pending_checks = {}

# ================= CLIENT =================
try:
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            session_str = f.read().strip()
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH).start(bot_token=BOT_TOKEN)
    else:
        client = TelegramClient(StringSession(), API_ID, API_HASH).start(bot_token=BOT_TOKEN)
        with open(SESSION_FILE, "w") as f:
            f.write(client.session.save())
except Exception:
    print("🔥 Failed to start Telegram client!")
    traceback.print_exc()
    sys.exit(1)

print("🤖 Bot initialized successfully!")

# ========== /start handler ==========
@client.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    try:
        sender = event.sender_id
        user_id_str = str(sender)
        parts = event.message.text.split()
        inviter_id_str = parts[1] if len(parts) > 1 else None

        if inviter_id_str == user_id_str:
            inviter_id_str = None

        if inviter_id_str:
            already_referred = any(user_id_str in users for users in data["referrals"].values())
            if not already_referred:
                pending_checks.setdefault(inviter_id_str, []).append(user_id_str)

        bot_username = BOT_USERNAME or (await client.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user_id_str}"
        channel_link = f"https://t.me/{CHANNEL_USERNAME}" if not str(CHANNEL_USERNAME).startswith("-100") else f"https://t.me/c/{CHANNEL_USERNAME.replace('-100','')}"

        count = data["ref_counts"].get(user_id_str, 0)
        buttons = [[Button.inline("📈 إحالاتي", data=b"myrefs")]]
        if sender in OWNER_IDS:
            buttons.append([Button.inline("📊 لوحة المتصدرين", data=b"leaderboard")])

        await event.respond(
            f"👋 أهلاً بك!\n\n"
            f"📢 انضم للقناة: {channel_link}\n\n"
            f"🔗 رابط الإحالة الخاص بك:\n{referral_link}\n\n"
            f"👥 عدد الأشخاص الذين قمت بدعوتهم: {count}",
            buttons=buttons,
            link_preview=False
        )
    except Exception:
        print("🔥 Error in /start handler!")
        traceback.print_exc()

# ================= Other Handlers =================
# Add your callback query and channel join handlers here
# Always call save_data() after modifying data

# ================= Run Bot =================
try:
    print("🤖 Bot is now running...")
    client.run_until_disconnected()
except Exception:
    print("🔥 Bot crashed while running!")

    traceback.print_exc()
