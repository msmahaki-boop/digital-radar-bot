
import os
import html
import re
import json
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET

# منابع خبری
SOURCES = [
    (
        "زومیت",
        "فناوری",
        "https://www.zoomit.ir/feed/"
    ),
    (
        "دیجیاتو",
        "فناوری",
        "https://digiato.com/feed/"
    ),
    (
        "The Verge",
        "هوش مصنوعی",
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"
    ),
    (
        "Search Engine Journal",
        "بازاریابی دیجیتال",
        "https://www.searchenginejournal.com/feed/"
    ),
    (
        "Social Media Examiner",
        "مدیریت سوشال مدیا",
        "https://www.socialmediaexaminer.com/feed/"
    ),
]


def read_news(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (DigitalRadarBot/1.0)"
        }
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        content = response.read(1_000_000)

    root = ET.fromstring(content)
    entries = []

    # Atom feeds
    if root.tag.split("}")[-1] == "feed":
        atom = "{http://www.w3.org/2005/Atom}"

        for entry in root.findall(f"{atom}entry")[:3]:
            title = entry.findtext(f"{atom}title") or ""
            links = entry.findall(f"{atom}link")

            link = next(
                (
                    x.get("href", "")
                    for x in links
                    if x.get("rel", "alternate") == "alternate"
                ),
                ""
            )

            entries.append((title, link))

    # RSS feeds
    else:
        for entry in root.findall(".//item")[:3]:
            entries.append((
                entry.findtext("title") or "",
                entry.findtext("link") or ""
            ))

    for title, link in entries:
        title = html.unescape(
            re.sub(r"<[^>]*>", "", title)
        ).strip()

        title = re.sub(r"\s+", " ", title)[:200]

        if title and link.startswith(("https://", "http://")):
            return title, link.strip()

    return None


def send_message(message):
    token = os.environ.get("BOT_TOKEN", "").strip()
    chat_id = os.environ.get("CHAT_ID", "").strip()

    if not token or not chat_id:
        raise SystemExit(
            "BOT_TOKEN or CHAT_ID is missing."
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": "true"
    }).encode("utf-8")

    try:
        request = urllib.request.Request(url, data=data)

        with urllib.request.urlopen(
            request, timeout=30
        ) as response:
            result = json.load(response)

    except urllib.error.HTTPError as error:
        raise SystemExit(
            f"Telegram HTTP {error.code}. Check secrets."
        ) from None

    except urllib.error.URLError:
        raise SystemExit(
            "Unable to reach Telegram API."
        ) from None

    if not result.get("ok"):
        raise SystemExit("Telegram rejected the message.")


def main():
    sections = []

    for source, category, feed in SOURCES:
        try:
            news = read_news(feed)

            if news:
                title, link = news

                sections.append(
                    f"🔹 {category} | {source}\n"
                    f"{title}\n"
                    f"{link}"
                )

                print(f"OK: {source}")

            else:
                print(f"No news found: {source}")

        except Exception as error:
            print(
                f"Feed error ({source}): "
                f"{type(error).__name__}"
            )

    if not sections:
        raise SystemExit(
            "No readable news feeds found. Try again later."
        )

    message = (
        "📰 Digital Radar | تست خبرهای واقعی\n\n"
        + "\n\n".join(sections)
    )

    send_message(message)

    print(
        f"SUCCESS: Sent {len(sections)} news items."
    )


if __name__ == "__main__":
    main()
