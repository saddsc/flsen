import os
from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
import asyncio
import re
from aiohttp import web

# القيم المحدثة
api_id = 28058773
api_hash = "e9e57b0112979b26db98ed965b55ec23"
bot_token = "7561453887:AAEMHh30AV3MGw0sH9uS6sWyckmtiCc7Ues"
owner_id = 908814910

# إنشاء عميل Telegram
client = TelegramClient("bot_session", api_id, api_hash)

# تحميل المشرفين
admins_file = "admins.txt"
if not os.path.exists(admins_file):
    with open(admins_file, "w") as f:
        f.write(str(owner_id) + "\n")

def load_admins():
    with open(admins_file, "r") as f:
        return {int(line.strip()) for line in f.readlines()}

def save_admin(admin_id):
    with open(admins_file, "a") as f:
        f.write(str(admin_id) + "\n")

def remove_admin(admin_id):
    admins = load_admins()
    admins.discard(admin_id)
    with open(admins_file, "w") as f:
        for admin in admins:
            f.write(str(admin) + "\n")

admins = load_admins()

group_link_pattern = re.compile(r"(?:https?://)?t\.me/([a-zA-Z0-9_]+)|(-100\d+)")

def extract_chat_id(message_text):
    match = group_link_pattern.search(message_text)
    if match:
        return f"@{match.group(1)}" if match.group(1) else int(match.group(2))
    return None

async def handle_message(event):
    sender = await event.get_sender()
    sender_id = sender.id
    message_text = event.message.text

    if sender_id not in admins:
        await event.respond(
            "🚫 ليس لديك صلاحية لاستخدام هذا البوت!\n"
            "🔹 هذا البوت مخصص للمشرفين فقط.\n"
            "🔹 إذا كنت بحاجة إلى صلاحيات، يرجى التواصل مع المالك: @QOQ9y."
        )
        return

    if message_text.startswith("/رفع_مشرف"):
        if sender_id != owner_id:
            await event.respond("🚫 هذا الأمر متاح فقط للمالك.")
            return
        try:
            new_admin_id = int(message_text.split()[1])
            if new_admin_id in admins:
                await event.respond("✅ هذا المستخدم مشرف بالفعل.")
            else:
                save_admin(new_admin_id)
                admins.add(new_admin_id)
                await event.respond(f"✅ تم ترقية المستخدم {new_admin_id} إلى مشرف.")
        except (IndexError, ValueError):
            await event.respond("❌ يرجى إرسال الأمر بالشكل الصحيح: `/رفع_مشرف <ايدي_الشخص>`")
        return

    if message_text.startswith("/حذف_مشرف"):
        if sender_id != owner_id:
            await event.respond("🚫 هذا الأمر متاح فقط للمالك.")
            return
        try:
            admin_id = int(message_text.split()[1])
            if admin_id == owner_id:
                await event.respond("🚫 لا يمكنك إزالة المالك من المشرفين!")
                return
            if admin_id not in admins:
                await event.respond("❌ هذا المستخدم ليس مشرفًا بالفعل.")
            else:
                remove_admin(admin_id)
                admins.remove(admin_id)
                await event.respond(f"✅ تم إزالة المشرف {admin_id}.")
        except (IndexError, ValueError):
            await event.respond("❌ يرجى إرسال الأمر بالشكل الصحيح: `/حذف_مشرف <ايدي_الشخص>`")
        return

    if message_text.startswith("/عرض_المشرفين"):
        admin_list = "\n".join(map(str, admins))
        await event.respond(f"📌 قائمة المشرفين:\n{admin_list}")
        return

    chat_id = extract_chat_id(message_text)
    if not chat_id:
        await event.respond("❌ يرجى إرسال رابط مجموعة صحيح مثل:\n🔹 `t.me/MyGroup`\n🔹 أو معرف المجموعة مثل: `-1001234567890`")
        return

    await event.respond("✅ جاري حظر الأعضاء بسرعة...")

    offset = 0
    limit = 200
    all_users = []

    while True:
        participants = await client(GetParticipantsRequest(
            chat_id, ChannelParticipantsSearch(''), offset=offset, limit=limit, hash=0
        ))
        if not participants.users:
            break
        all_users.extend(participants.users)
        offset += len(participants.users)
        await event.respond(f"تم جلب {len(all_users)} عضو حتى الآن...")

    await event.respond(f"📌 إجمالي عدد الأعضاء في المجموعة: {len(all_users)}")

    banned_users = []
    failed_users = []

    for i in range(0, len(all_users), 100):
        tasks = []
        batch = all_users[i:i+100]
        for user in batch:
            if not user.is_self:
                tasks.append(client.kick_participant(chat_id, user.id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for user, result in zip(batch, results):
            if isinstance(result, Exception):
                failed_users.append(f"{user.first_name} ({user.id}): {result}")
            else:
                banned_users.append(f"{user.first_name} ({user.id})")

    report = "✅ تم حظر جميع الأعضاء بنجاح!\n\n"
    report += f"👥 عدد الأعضاء المحظورين: {len(banned_users)}\n"
    if failed_users:
        report += f"❌ الأعضاء الذين فشل حظرهم:\n" + "\n".join(failed_users)
    
    await event.respond(report)

# نقطة نهاية Webhook
async def webhook(request):
    update = await request.json()
    event = events.NewMessage.Event(update['message']) if 'message' in update else None
    if event:
        await handle_message(event)
    return web.Response(text="OK")

# إعداد التطبيق
app = web.Application()
app.router.add_post('/', webhook)

# بدء العميل عند تشغيل التطبيق
async def startup():
    await client.start(bot_token=bot_token)
    print("✅ البوت جاهز لاستقبال الطلبات...")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(startup())
    web.run_app(app, host='0.0.0.0', port=int(os.environ.get("PORT", 3000)))