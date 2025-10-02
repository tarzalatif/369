import os
import sys
import json
import traceback
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# ================= Helper =================
def get_env(name, required=True):
    value = os.getenv(name)
    if required and not value:
        print(f"❌ ERROR: Environment variable '{name}' is not set!")
        sys.exit(1)
    return value

print("DEBUG: Listing all environment variables...")
for k, v in os.environ.items():
    print(f"{k} = {v}")

# ================= CONFIG =================
API_ID = int(get_env("API_ID"))
API_HASH = get_env("API_HASH")
BOT_TOKEN = get_env("BOT_TOKEN")
BOT_USERNAME = get_env("BOT_USERNAME")
CHANNEL_USERNAME = get_env("CHANNEL_USERNAME")
OWNER_IDS = list(map(int, get_env("OWNER_IDS").split(",")))

DATA_DIR = get_env("DATA_DIR", required=False) or "/data"
os.makedirs(DATA_DIR, exist_ok=True)

SESSION_FILE = os.path.join(DATA_DIR, "session.txt")
DATA_FILE = os.path.join(DATA_DIR, "ref_data.json")
MILESTONE = int(get_env("MILESTONE", required=False) or 2)

# ================= Load Data =================
try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    data = {"referrals": {}, "ref_counts": {}, "rewarded": []}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

pending_checks = {}

# ================= Client =================
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

# ================= /start handler =================
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

# ================= Channel join handler =================
@client.on(events.ChatAction(chats=CHANNEL_USERNAME))
async def channel_join_handler(event):
    new_user_ids = []

    if getattr(event, "user_id", None):
        try:
            new_user_ids.append(int(event.user_id))
        except Exception:
            pass

    users_attr = getattr(event, "users", None)
    if users_attr:
        for u in users_attr:
            try:
                uid = int(u) if isinstance(u, (int, str)) else int(getattr(u, "id", None))
                if uid:
                    new_user_ids.append(uid)
            except Exception:
                pass

    if not new_user_ids and getattr(event, "action_message", None):
        try:
            from_id = getattr(event.action_message.from_id, "user_id", None)
            if from_id:
                new_user_ids.append(int(from_id))
        except Exception:
            pass

    if not new_user_ids:
        return

    for new_user_id in new_user_ids:
        new_user_str = str(new_user_id)
        for inviter_id_str, users_list in list(pending_checks.items()):
            if new_user_str in users_list:
                refs = data["referrals"].get(inviter_id_str, [])
                if new_user_str not in refs:
                    refs.append(new_user_str)
                    data["referrals"][inviter_id_str] = refs
                    data["ref_counts"][inviter_id_str] = len(refs)
                    save_data()

                    count = len(refs)
                    try:
                        await client.send_message(
                            int(inviter_id_str),
                            f"🎉 لقد انضم شخص إلى القناة باستخدام رابطك!\n"
                            f"👥 إجمالي الدعوات: {count}"
                        )
                    except Exception:
                        pass

                    milestone_key = f"{inviter_id_str}_{MILESTONE}"
                    if count >= MILESTONE and milestone_key not in data["rewarded"]:
                        milestone_users = refs[-MILESTONE:]
                        users_text = ""
                        for i, uid in enumerate(milestone_users, start=1):
                            try:
                                user_entity = await client.get_entity(int(uid))
                                if getattr(user_entity, "username", None):
                                    name = f"@{user_entity.username}"
                                else:
                                    first = getattr(user_entity, "first_name", "") or ""
                                    last = getattr(user_entity, "last_name", "") or ""
                                    fullname = (first + " " + last).strip()
                                    name = fullname if fullname else "User"
                                users_text += f"{i}. {name} ({uid})\n"
                            except Exception:
                                users_text += f"{i}. User ({uid})\n"

                        try:
                            await client.send_message(
                                int(inviter_id_str),
                                f"🏆 مبروك! ربحت معنا اشتراك شهري هدية، تم إضافة {MILESTONE} أشخاص من خلال رابط إحالتك!\n\n"
                                f"👥 الأعضاء الذين قمت بدعوتهم:\n{users_text}\n"
                                f"📞 تواصل مع دعمنا: @harmonic_mg"
                            )
                        except Exception:
                            pass

                        data["rewarded"].append(milestone_key)
                        save_data()

                try:
                    users_list.remove(new_user_str)
                except ValueError:
                    pass
                if not users_list:
                    pending_checks.pop(inviter_id_str, None)
                else:
                    pending_checks[inviter_id_str] = users_list
                break

# ================= Inline button handlers =================
@client.on(events.CallbackQuery(data=b"myrefs"))
async def cb_myrefs(event):
    user_id_str = str(event.sender_id)
    bot_username = BOT_USERNAME or (await client.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id_str}"
    count = data["ref_counts"].get(user_id_str, 0)

    await event.edit(
        f"👥 لقد قمت بدعوة {count} الأعضاء!\n\n"
        f"🔗 رابط إحالتك:\n{referral_link}",
        buttons=[[Button.inline("⬅ العودة", data=b"back")]],
        link_preview=False
    )

@client.on(events.CallbackQuery(data=b"leaderboard"))
async def cb_leaderboard(event):
    if event.sender_id not in OWNER_IDS:
        await event.answer("⛔ فقط المالك يمكنه رؤية لوحة المتصدرين", alert=True)
        return

    if not data["ref_counts"]:
        await event.edit("📊 لا توجد إحالات بعد.")
        return

    ranking = sorted(data["ref_counts"].items(), key=lambda x: x[1], reverse=True)[:10]
    text = "🏆 لوحة المتصدرين للإحالات 🏆\n\n"
    for i, (inviter, cnt) in enumerate(ranking, start=1):
        try:
            user = await client.get_entity(int(inviter))
            name = f"@{user.username}" if getattr(user, "username", None) else (getattr(user, "first_name", "User") or "User")
        except Exception:
            name = f"User {inviter}"
        text += f"{i}. {name} → {cnt} دعوات\n"

    await event.edit(text, buttons=[[Button.inline("⬅ العودة", data=b"back")]], link_preview=False)

@client.on(events.CallbackQuery(data=b"back"))
async def cb_back(event):
    user_id
