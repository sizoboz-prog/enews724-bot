import os
import re
import asyncio
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ==================== الإعدادات ====================
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

TARGET_CHANNEL = "enews724"
SOURCE_CHANNELS = ["turkmenller", "alsabakpress"]

news_queue = []
last_published_ids = set()

# ==================== كشف العاجل ====================
BREAKING_KEYWORDS = [
    "عاجل", "عاجلاً", "عاجلا", "breaking", "خبر عاجل",
    "للتو", "الآن", "انفجار", "اغتيال", "هجوم", "زلزال",
    "حريق", "كارثة", "طارئ", "طوارئ", "اعتقال", "مقتل"
]

def is_breaking(text):
    return any(kw in text for kw in BREAKING_KEYWORDS)

def get_source_name(channel):
    sources = {
        "turkmenller": "تركمان لر",
        "alsabakpress": "السباق برس",
    }
    return sources.get(channel, channel)

# ==================== بناء الرسالة ====================
def build_breaking_message(text, channel):
    now = datetime.now()
    days = ["الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"]
    day = days[now.weekday()]
    time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%d/%m/%Y")
    source = get_source_name(channel)

    return f"""⚡️ **عاجل**

{text}

━━━━━━━━━━━━━━━
🕐 {day} | {date_str} | {time_str}
📡 المصدر: {source}
📲 @{TARGET_CHANNEL}"""

def build_normal_message(text, channel):
    now = datetime.now()
    days = ["الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"]
    day = days[now.weekday()]
    time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%d/%m/%Y")
    source = get_source_name(channel)

    return f"""📰 **أخبار**

{text}

━━━━━━━━━━━━━━━
🕐 {day} | {date_str} | {time_str}
📡 المصدر: {source}
📲 @{TARGET_CHANNEL}"""

# ==================== تشغيل البوت ====================
async def main():
    global news_queue

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    print("✅ بوت الأخبار يعمل...")

    @client.on(events.NewMessage(chats=SOURCE_CHANNELS))
    async def handler(event):
        global news_queue, last_published_ids

        msg_id = event.message.id
        if msg_id in last_published_ids:
            return

        text = event.message.text or event.message.message or ""
        if not text or len(text) < 20:
            return

        channel = event.chat.username or ""
        print(f"📨 خبر من @{channel}: {text[:60]}...")

        if is_breaking(text):
            print("🔴 عاجل! نشر فوري...")
            try:
                msg = build_breaking_message(text[:500], channel)
                await client.send_message(TARGET_CHANNEL, msg, parse_mode="md")
                last_published_ids.add(msg_id)
                print("✅ نُشر العاجل")
            except Exception as e:
                print(f"❌ خطأ: {e}")
        else:
            news_queue.append({
                "text": text,
                "channel": channel,
                "id": msg_id
            })
            print(f"📋 أُضيف للقائمة ({len(news_queue)} خبر)")

    async def periodic_publish():
        global news_queue
        while True:
            await asyncio.sleep(30 * 60)
            if news_queue:
                news = news_queue.pop(0)
                print(f"📰 نشر دوري...")
                try:
                    msg = build_normal_message(news["text"][:500], news["channel"])
                    await client.send_message(TARGET_CHANNEL, msg, parse_mode="md")
                    last_published_ids.add(news["id"])
                    print("✅ نُشر الخبر الدوري")
                except Exception as e:
                    print(f"❌ خطأ: {e}")
            else:
                print("📋 لا توجد أخبار في القائمة")

    asyncio.create_task(periodic_publish())
    print("✅ البوت جاهز...")
    await client.run_until_disconnected()

asyncio.run(main())
