
import os
import json
import urllib.parse
import urllib.request

# دریافت امن توکن از GitHub
TOKEN = os.environ.get("BOT_TOKEN", "").strip()

if not TOKEN:
    raise SystemExit("BOT_TOKEN is missing.")


def telegram(method, **params):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode("utf-8")

    request = urllib.request.Request(url, data=data)

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    if not result.get("ok"):
        raise RuntimeError("Telegram request failed.")

    return result["result"]


# پیدا کردن گفت‌وگوی خصوصی صاحب ربات
updates = telegram("getUpdates", limit=100, timeout=0)

chats = set()

for update in updates:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    text = (message.get("text") or "").strip()

    if chat.get("type") != "private":
        continue

    if text.split(" ")[0].split("@")[0] == "/start":
        chats.add(chat["id"])

if len(chats) != 1:
    raise SystemExit(
        "Please send /start to your bot. "
        "Exactly one private chat must be found."
    )

chat_id = chats.pop()

# ارسال پیام آزمایشی
message = (
    "✅ ربات خبری با موفقیت راه‌اندازی شد!\n\n"
    "📰 Digital Radar Bot\n\n"
    "🤖 اتصال ربات به تلگرام برقرار است.\n\n"
    "به‌زودی اخبار هوش مصنوعی، تکنولوژی، "
    "بازاریابی دیجیتال و سوشال مدیا "
    "را از همین‌جا دریافت می‌کنی."
)

telegram("sendMessage", chat_id=chat_id, text=message)

print("SUCCESS: Test message sent!")
print(f"CHAT_ID: {chat_id}")
