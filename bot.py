
import os
import json
import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

STATE_FILE = 'sent_news.json'

SOURCES = [
    ('زومیت', 'فناوری', 'https://www.zoomit.ir/feed/'),
    ('دیجیاتو', 'فناوری', 'https://digiato.com/feed/'),
    (
        'The Verge',
        'هوش مصنوعی',
        'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml'
    ),
    (
        'Search Engine Journal',
        'دیجیتال مارکتینگ',
        'https://www.searchenginejournal.com/feed/'
    ),
    (
        'Social Media Examiner',
        'مدیریت سوشال مدیا',
        'https://www.socialmediaexaminer.com/feed/'
    ),
]


def fetch_news(feed_url):
    request = urllib.request.Request(
        feed_url,
        headers={
            'User-Agent': 'Mozilla/5.0 (DigitalRadarBot/1.0)'
        }
    )

    with urllib.request.urlopen(
        request, timeout=20
    ) as response:
        data = response.read(1_500_000)

    root = ET.fromstring(data)
    atom = '{http://www.w3.org/2005/Atom}'

    if root.tag == atom + 'feed':
        entries = []

        for item in root.findall(atom + 'entry')[:25]:
            title = item.findtext(atom + 'title') or ''

            link = next(
                (
                    tag.get('href', '')
                    for tag in item.findall(atom + 'link')
                    if tag.get('rel', 'alternate') == 'alternate'
                ),
                ''
            )

            entries.append((title, link))

    else:
        entries = [
            (
                item.findtext('title') or '',
                item.findtext('link') or ''
            )
            for item in root.findall('.//item')[:25]
        ]

    news = []

    for title, link in entries:
        title = re.sub(
            r'\s+', ' ',
            html.unescape(
                re.sub(r'<[^>]+>', '', title)
            )
        ).strip()

        link = link.strip()

        if title and link.startswith(('https://', 'http://')):
            news.append((title[:210], link))

    return news


def send_to_telegram(message):
    token = os.environ.get('BOT_TOKEN', '').strip()
    chat_id = os.environ.get('CHAT_ID', '').strip()

    if not token or not chat_id:
        raise RuntimeError(
            'Missing BOT_TOKEN or CHAT_ID in Secrets'
        )

    url = f'https://api.telegram.org/bot{token}/sendMessage'

    payload = urllib.parse.urlencode({
        'chat_id': chat_id,
        'text': message,
        'disable_web_page_preview': 'true'
    }).encode('utf-8')

    request = urllib.request.Request(
        url, data=payload
    )

    with urllib.request.urlopen(
        request, timeout=30
    ) as response:
        result = json.load(response)

    if not result.get('ok'):
        raise RuntimeError(
            'Telegram rejected the message'
        )


def main():
    first_run = not os.path.exists(STATE_FILE)

    if first_run:
        history = []
    else:
        with open(
            STATE_FILE, 'r', encoding='utf-8'
        ) as file:
            history = json.load(file)['seen']

    seen = set(history)
    scanned = []
    sections = []
    chosen_links = set()
    successful_sources = 0

    for source, category, feed in SOURCES:
        try:
            items = fetch_news(feed)

        except Exception as error:
            print(
                f'Feed unavailable: {source}: '
                f'{type(error).__name__}'
            )
            continue

        if not items:
            print(f'No items in {source}')
            continue

        successful_sources += 1

        fresh = [
            (title, link)
            for title, link in items
            if link not in seen
            and link not in chosen_links
        ]

        limit = 1 if first_run else 2

        for title, link in fresh[:limit]:
            chosen_links.add(link)

            sections.append(
                f'🔹 {category} | {source}\n'
                f'{title}\n{link}'
            )

        scanned.extend(
            link for _, link in items
        )

        print(
            f'{source}: '
            f'{len(fresh[:limit])} selected'
        )

    if successful_sources == 0:
        raise RuntimeError(
            'All RSS sources are unavailable. History unchanged.'
        )

    if sections:
        prefix = (
            '📰 Digital Radar | خبرهای جدید\n\n'
        )

        message = prefix

        for section in sections:
            block = section + '\n\n'

            if len(message) + len(block) > 3500:
                send_to_telegram(message.rstrip())
                message = prefix

            message += block

        if message != prefix:
            send_to_telegram(message.rstrip())

        print(
            f'SUCCESS: sent {len(sections)} articles'
        )

    else:
        print(
            'No new stories; no Telegram message sent'
        )

    for link in scanned:
        if link not in seen:
            seen.add(link)
            history.append(link)

    history = history[-1200:]

    if first_run or scanned:
        with open(
            STATE_FILE, 'w', encoding='utf-8'
        ) as file:
            json.dump(
                {'seen': history},
                file,
                ensure_ascii=False,
                indent=2
            )
            file.write('\n')


if __name__ == '__main__':
    main()
