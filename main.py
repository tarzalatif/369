# referral_bot_event_milestone.py
import json
from telethon import TelegramClient, events, Button

# ========== CONFIG ==========
API_ID = 13463414                # your api_id from my.telegram.org
API_HASH = "625e043425a56fd0ae4e1f77e9098c3b"     # your api_hash
BOT_TOKEN = "8491575607:AAEl2SYh7LSyYx1qq7xz4HV4CtrX45sChAM"   # token from @BotFather

BOT_USERNAME = "MGreward_systembot"  # bot username, without @
CHANNEL_USERNAME = "muneer_gove"  # channel username, without @ (or -100.. id for private)
OWNER_IDS = [1719959197,921908800]               # your Telegram numeric user id

DATA_FILE = "ref_data.json"
MILESTONE = 2  # milestone for reward (you can set back to 10 later)

# ========== DATA STORAGE ==========
try:
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
except FileNotFoundError:
    data = {"referrals": {}, "ref_counts": {}, "rewarded": []}  # rewarded stores milestones already sent

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Pending referrals: inviter_id_str -> [new_user_id_str, ...]
pending_checks = {}

# ========== CLIENT ==========
client = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)


# ========== /start handler ==========
@client.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    sender = event.sender_id
    user_id_str = str(sender)
    parts = event.message.text.split()
    inviter_id_str = None

    if len(parts) > 1:
        inviter_id_str = parts[1]
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

    buttons = [[Button.inline("📈 My Referrals", data=b"myrefs")]]
    if sender in OWNER_IDS:
        buttons.append([Button.inline("📊 Leaderboard", data=b"leaderboard")])

    await event.respond(
        f"👋 Welcome!\n\n"
        f"📢 انضمام الی قناة: {channel_link}\n\n"
        f"🔗 رابط احالتك : \n{referral_link}\n\n",
        buttons=buttons,
        link_preview=False
    )


# ========== Handle channel join events ==========
@client.on(events.ChatAction(chats=CHANNEL_USERNAME))
async def channel_join_handler(event):
    # We handle both single and multiple users joining/being added.
    new_user_ids = []

    # Telethon might expose joined users in different attributes:
    if getattr(event, "user_id", None):
        try:
            new_user_ids.append(int(event.user_id))
        except Exception:
            pass

    # event.users can be a list of User objects
    users_attr = getattr(event, "users", None)
    if users_attr:
        for u in users_attr:
            try:
                # If u is an int id or a User object
                uid = int(u) if isinstance(u, (int, str)) else int(getattr(u, "id", None))
                if uid:
                    new_user_ids.append(uid)
            except Exception:
                pass

    # Fallback: sometimes action_message has from_id
    if not new_user_ids and getattr(event, "action_message", None):
        try:
            from_id = getattr(event.action_message.from_id, "user_id", None)
            if from_id:
                new_user_ids.append(int(from_id))
        except Exception:
            pass

    # If none found, nothing to do
    if not new_user_ids:
        return

    # Process each new user found
    for new_user_id in new_user_ids:
        new_user_str = str(new_user_id)

        # Iterate over pending checks (copy items to allow safe modification)
        for inviter_id_str, users_list in list(pending_checks.items()):
            if new_user_str in users_list:
                # Count referral
                refs = data["referrals"].get(inviter_id_str, [])
                if new_user_str not in refs:
                    refs.append(new_user_str)
                    data["referrals"][inviter_id_str] = refs
                    data["ref_counts"][inviter_id_str] = len(refs)
                    save_data()

                    count = len(refs)

                    # Regular join message
                    try:
                        await client.send_message(
                            int(inviter_id_str),
                            f"🎉 لقد انضم شخص إلى القناة باستخدام رابطك!\n"
                            f"👥 إجمالي الدعوات: {count}"
                        )
                    except Exception:
                        pass

                    # ✅ Milestone reward message
                    milestone_key = f"{inviter_id_str}_{MILESTONE}"
                    if count >= MILESTONE and milestone_key not in data["rewarded"]:
                        # Get the last MILESTONE users invited
                        milestone_users = refs[-MILESTONE:]

                        # Build numbered list with username or name + id
                        users_text = ""
                        for i, uid in enumerate(milestone_users, start=1):
                            try:
                                user_entity = await client.get_entity(int(uid))
                                # prefer username, otherwise full name, otherwise "User"
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

                        # Send milestone (Arabic + English header like you wanted)
                        try:
                            await client.send_message(
                                int(inviter_id_str),
                                f"🏆 مبروك ، ربحت معنا اشتراك شهري هدية تم اضافة {MILESTONE} اشخاص من خلال رابط احالتك !\n\n"
                                f"👥 الأعضاء الذين قمت بدعوتهم هم:\n{users_text}\n"
                                f"📞 تواصل مع دعمنا @harmonic_mg ."
                            )
                        except Exception:
                            pass

                        # Mark as rewarded
                        data["rewarded"].append(milestone_key)
                        save_data()

                # Remove from pending (and clean empty lists)
                try:
                    users_list.remove(new_user_str)
                except ValueError:
                    pass
                if not users_list:
                    pending_checks.pop(inviter_id_str, None)
                else:
                    pending_checks[inviter_id_str] = users_list

                # break out of inviter loop for this new_user
                break


# ========== Inline button handlers ==========
@client.on(events.CallbackQuery(data=b"myrefs"))
async def cb_myrefs(event):
    user_id_str = str(event.sender_id)
    bot_username = BOT_USERNAME or (await client.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id_str}"
    count = data["ref_counts"].get(user_id_str, 0)

    await event.edit(
        f"👥 لقد قمت بدعوة  {count} الأعضاء!\n\n"
        f"🔗 رابط احالتك :\n{referral_link}",
        buttons=[[Button.inline("⬅ Back", data=b"back")]],
        link_preview=False
    )


@client.on(events.CallbackQuery(data=b"leaderboard"))
async def cb_leaderboard(event):
    if event.sender_id not in OWNER_IDS:
        await event.answer("⛔ Only the owner can see the leaderboard", alert=True)
        return

    if not data["ref_counts"]:
        await event.edit("📊 لا توجد إحالات بعد.")
        return

    ranking = sorted(data["ref_counts"].items(), key=lambda x: x[1], reverse=True)[:10]
    text = "🏆 Referral Leaderboard 🏆\n\n"
    for i, (inviter, cnt) in enumerate(ranking, start=1):
        try:
            user = await client.get_entity(int(inviter))
            name = f"@{user.username}" if getattr(user, "username", None) else (getattr(user, "first_name", "User") or "User")
        except Exception:
            name = f"User {inviter}"
        text += f"{i}. {name} → {cnt} invites\n"

    await event.edit(text, buttons=[[Button.inline("⬅ Back", data=b"back")]], link_preview=False)


@client.on(events.CallbackQuery(data=b"back"))
async def cb_back(event):
    user_id_str = str(event.sender_id)
    bot_username = BOT_USERNAME or (await client.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id_str}"
    count = data["ref_counts"].get(user_id_str, 0)

    buttons = [[Button.inline("📈 My Referrals", data=b"myrefs")]]
    if event.sender_id in OWNER_IDS:
        buttons.append([Button.inline("📊 Leaderboard", data=b"leaderboard")])

    await event.edit(
        f"🔗 رابط احالتك::\n{referral_link}\n\n"
        f"👥 لقد قمت بدعوة {count} الأعضاء!",
        buttons=buttons,
        link_preview=False
    )


# ========== Run Bot ==========
print("🤖 Bot is running...")
client.run_until_disconnected()

