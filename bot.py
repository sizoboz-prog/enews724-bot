import os
import re
import asyncio
import textwrap
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ==================== الإعدادات ====================
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

TARGET_CHANNEL = "enews724"
SOURCE_CHANNELS = ["turkmenller", "alsabakpress"]

# الأخبار العادية تُجمع وتُنشر كل 30 دقيقة
news_queue = []
last_published_ids = set()

# ==================== كشف العاجل ====================
BREAKING_KEYWORDS = [
    "عاجل", "عاجلاً", "عاجلا", "breaking", "خبر عاجل",
    "للتو", "الآن", "انفجار", "اغتيال", "هجوم", "زلزال",
    "حريق", "كارثة", "طارئ", "طوارئ", "اعتقال", "مقتل"
]

def is_breaking(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in BREAKING_KEYWORDS)

# ==================== رسم النص العربي ====================
def get_font(size=40, bold=False):
    """محاولة تحميل خط عربي، وإلا الخط الافتراضي"""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                pass
    return ImageFont.load_default()

def wrap_arabic_text(text, max_chars=28):
    """تقسيم النص إلى أسطر"""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current += (" " if current else "") + word
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:4]  # max 4 lines

def get_source_name(channel):
    sources = {
        "turkmenller": "تركمان لر",
        "alsabakpress": "السباق برس",
    }
    return sources.get(channel, channel)

# ==================== تصميم الصورة ====================
def create_news_image(headline, source_channel, breaking=False, category="أخبار محلية"):
    W, H = 1280, 720

    # الألوان
    BG = "#0d1117"
    RED = "#e63946"
    BLUE = "#1c3f6e"
    GOLD = "#f4a300"
    WHITE = "#f0f6fc"
    GRAY = "#8b949e"
    DIVIDER = "#21262d"
    ACCENT = RED if breaking else BLUE
    BADGE_TEXT = "#ffffff" if breaking else "#7eb8f7"

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # الشريط العلوي
    draw.rectangle([(0, 0), (W, 8)], fill=ACCENT)

    # الشريط الجانبي
    draw.rectangle([(W-6, 8), (W, H)], fill=ACCENT)

    # ==================== اللوجو ====================
    logo_x, logo_y = 40, 30
    draw.rectangle([(logo_x, logo_y), (logo_x+130, logo_y+52)], fill=RED)

    font_logo = get_font(28, bold=True)
    draw.text((logo_x+10, logo_y+10), "7/24", font=font_logo, fill=WHITE)

    font_sub = get_font(18)
    draw.text((logo_x+145, logo_y+16), "e news", font=font_sub, fill=GRAY)

    # ==================== الوقت ====================
    now = datetime.now()
    days = ["الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"]
    day_name = days[now.weekday()]
    time_str = f"{day_name}، {now.strftime('%d/%m/%Y')}  |  {now.strftime('%I:%M %p')}"
    font_time = get_font(18)
    draw.text((W-400, logo_y+16), time_str, font=font_time, fill=GRAY)

    # ==================== بادج العاجل / الفئة ====================
    badge_y = 115
    badge_text = "⚡ عاجل" if breaking else f"● {category}"
    draw.rectangle([(40, badge_y), (40+180, badge_y+40)], fill=ACCENT)
    font_badge = get_font(20, bold=True)
    draw.text((55, badge_y+8), badge_text, font=font_badge, fill=WHITE)

    # الخط الفاصل
    draw.rectangle([(40, 170), (W-40, 172)], fill=DIVIDER)

    # ==================== العنوان ====================
    lines = wrap_arabic_text(headline, max_chars=30)
    font_headline = get_font(46, bold=True)
    y_text = 195
    for line in lines:
        draw.text((40, y_text), line, font=font_headline, fill=WHITE)
        y_text += 65

    # ==================== الشريط السفلي ====================
    draw.rectangle([(0, H-65), (W, H)], fill="#0a0a0f")
    draw.rectangle([(0, H-67), (W, H-65)], fill=ACCENT)

    font_footer = get_font(22, bold=True)
    draw.text((40, H-48), f"@{TARGET_CHANNEL}", font=font_footer, fill=GOLD)

    source_text = f"المصدر: {get_source_name(source_channel)}"
    draw.text((W-350, H-48), source_text, font=font_footer, fill=GRAY)

    # حفظ الصورة في الذاكرة
    buf = BytesIO()
    img.save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf

# ==================== تشغيل البوت ====================
async def main():
    global news_queue

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    print("✅ بوت الأخبار يعمل...")
    print(f"👀 يراقب: {SOURCE_CHANNELS}")
    print(f"📢 ينشر في: @{TARGET_CHANNEL}")

    # ==================== معالج الرسائل الجديدة ====================
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
        print(f"📨 خبر جديد من @{channel}: {text[:60]}...")

        if is_breaking(text):
            print("🔴 خبر عاجل! نشر فوري...")
            try:
                img_buf = create_news_image(text[:120], channel, breaking=True)
                caption = f"⚡ عاجل\n\n{text[:300]}\n\n📡 @{TARGET_CHANNEL}"
                await client.send_file(TARGET_CHANNEL, img_buf, caption=caption)
                last_published_ids.add(msg_id)
                print(f"✅ نُشر العاجل")
            except Exception as e:
                print(f"❌ خطأ في النشر: {e}")
        else:
            # أضف للقائمة للنشر الدوري
            news_queue.append({
                "text": text,
                "channel": channel,
                "id": msg_id
            })
            print(f"📋 أُضيف للقائمة ({len(news_queue)} خبر)")

    # ==================== النشر الدوري كل 30 دقيقة ====================
    async def periodic_publish():
        global news_queue
        while True:
            await asyncio.sleep(30 * 60)  # 30 دقيقة
            if news_queue:
                # نشر أول خبر في القائمة
                news = news_queue.pop(0)
                print(f"📰 نشر دوري: {news['text'][:50]}...")
                try:
                    img_buf = create_news_image(
                        news["text"][:120],
                        news["channel"],
                        breaking=False,
                        category="أخبار"
                    )
                    caption = f"📰 {news['text'][:300]}\n\n📡 @{TARGET_CHANNEL}"
                    await client.send_file(TARGET_CHANNEL, img_buf, caption=caption)
                    last_published_ids.add(news["id"])
                    print(f"✅ نُشر الخبر الدوري")
                except Exception as e:
                    print(f"❌ خطأ في النشر الدوري: {e}")
            else:
                print("📋 لا توجد أخبار في القائمة")

    # تشغيل النشر الدوري بالتوازي
    asyncio.create_task(periodic_publish())

    print("✅ البوت جاهز ويعمل...")
    await client.run_until_disconnected()

asyncio.run(main())
