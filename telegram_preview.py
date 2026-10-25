"""Acolad Telegram news preview -- read-only, NEVER SENDS MESSAGES.

Input:  stories_output/manifest.json from an existing Acolad Story Generator run.
Output: telegram_previews/*.txt, *.html, optional *.jpg, preview_manifest.json
This program does not import the Telegram API and does not require BOT_TOKEN.
"""
from __future__ import annotations

import argparse
import html
import ipaddress
import json
import math
import re
import socket
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps, UnidentifiedImageError

DEFAULT_LOGO = Path("assets/brand/logo_acolad.png")
OUTPUT = Path("telegram_previews")
FOOTER_TEXT = (
    "🌐 acolad.ir\n"
    "📢 کانال تلگرام: @acoladagency\n"
    "ارتباط و مشاوره: @acolad_agency"
)
FOOTER_HTML = (
    '🌐 <a href="https://acolad.ir/">acolad.ir</a>\n'
    '📢 کانال تلگرام: <a href="https://t.me/acoladagency">@acoladagency</a>\n'
    'ارتباط و مشاوره: <a href="https://t.me/acolad_agency">@acolad_agency</a>'
)
AGENT = {"User-Agent": "Mozilla/5.0 (compatible; AcoladTelegramPreview/1.0)"}
TOPICS = {"tech", "ai", "marketing", "social"}
CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4000


@dataclass
class PreviewResult:
    topic: str
    title: str
    source_url: str
    kind: str
    image_status: str
    photo_file: str | None
    caption_txt: str
    caption_html: str
    body_truncated: bool


def public_http_url(url: str) -> bool:
    """Basic safety check before visiting article-controlled URLs."""
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username:
            return False
        host = parts.hostname
        if host.lower() in ("localhost", "localhost.localdomain") or host.endswith(".local"):
            return False
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(x[4][0]).is_global for x in addresses)
    except (ValueError, OSError, socket.gaierror):
        return False


def guarded_get(url: str, *, stream=False, timeout=(6, 12)) -> requests.Response:
    """Revalidate each redirect before accessing another host."""
    for _ in range(4):
        if not public_http_url(url):
            raise ValueError("Unsafe or non-public HTTP URL")
        r = requests.get(url, headers=AGENT, stream=stream, timeout=timeout, allow_redirects=False)
        if r.is_redirect:
            target = urljoin(url, r.headers.get("Location", ""))
            r.close()
            url = target
            continue
        r.raise_for_status()
        return r
    raise ValueError("Too many redirects")


def article_image_url(article_url: str) -> str:
    with guarded_get(article_url, stream=True) as r:
        if "html" not in r.headers.get("Content-Type", "").lower():
            return ""
        data = bytearray()
        for chunk in r.iter_content(32768):
            data += chunk
            if len(data) > 1_500_000:
                break
    soup = BeautifulSoup(data.decode("utf-8", errors="replace"), "html.parser")
    for key in ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src"):
        meta = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if not meta:
            continue
        value = urljoin(article_url, meta.get("content", "").strip())
        stem = urlsplit(value).path.lower()
        if any(bad in stem for bad in ("logo", "avatar", "placeholder", "default-image", "pixel.gif")):
            continue
        if public_http_url(value):
            return value
    return ""


def fetch_relevant_photo(article_url: str, review_status: str) -> tuple[Image.Image | None, str]:
    # Reuse the existing editor's photo decision; don't invent a stock illustration.
    if not review_status.lower().startswith("article-specific"):
        return None, "editor did not approve an article-specific photo"
    try:
        url = article_image_url(article_url)
        if not url:
            return None, "article has no usable og:image"
        with guarded_get(url, stream=True) as r:
            if not r.headers.get("Content-Type", "").lower().startswith("image/"):
                return None, "image URL has non-image content"
            data = bytearray()
            for block in r.iter_content(65536):
                data += block
                if len(data) > 8_000_000:
                    return None, "image exceeds 8 MB"
        with Image.open(BytesIO(data)) as img:
            photo = ImageOps.exif_transpose(img).convert("RGB")
        w, h = photo.size
        if w < 750 or h < 450 or min(w, h) / max(w, h) < .32:
            return None, f"image dimensions unsuitable: {w}x{h}"
        return photo, f"approved article og:image {w}x{h}"
    except (requests.RequestException, UnidentifiedImageError, OSError, ValueError) as e:
        return None, f"photo not available: {type(e).__name__}"


def branded_photo(photo: Image.Image, logo: Image.Image) -> Image.Image:
    """Add an unobtrusive, soft white gradient ONLY near bottom-left and the original logo."""
    photo = ImageOps.exif_transpose(photo).convert("RGBA")
    if max(photo.size) > 1800:
        photo.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    w, h = photo.size
    low_w, low_h = 180, 120
    mask = Image.new("L", (low_w, low_h))
    pix = mask.load()
    for y in range(low_h):
        yy = y / (low_h - 1)
        vertical = max(0.0, min(1.0, (yy - .48) / .52)) ** 1.3
        for x in range(low_w):
            xx = x / (low_w - 1)
            horizontal = max(0.0, 1 - xx / .7) ** .85
            pix[x, y] = round(240 * vertical * horizontal)
    gradient = Image.new("RGBA", photo.size, (255, 255, 255, 0))
    gradient.putalpha(mask.resize(photo.size, Image.Resampling.BICUBIC))
    photo = Image.alpha_composite(photo, gradient)
    logo = logo.convert("RGBA")
    logo.thumbnail((max(150, int(w * .22)), max(90, int(h * .22))), Image.Resampling.LANCZOS)
    pad = max(20, round(min(w, h) * .035))
    x, y = pad, h - logo.height - pad
    photo.alpha_composite(logo, (x, y))
    return photo.convert("RGB")


def normalize_text(value: str) -> str:
    value = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    value = value.replace("\u200e", "").replace("\ufeff", "")
    value = re.sub(r"[ \t]+", " ", value)
    return re.sub(r"\n{3,}", "\n\n", value)


def shorten_at_sentence(text: str, budget: int) -> tuple[str, bool]:
    """Avoid chopping an incomplete sentence or inventing an AI paraphrase."""
    text = normalize_text(text)
    if len(text) <= budget:
        return text, False
    # Prioritize opening factual paragraphs; preserve complete sentences.
    first = text[:budget + 1]
    stops = list(re.finditer(r"[.!؟؛]\s|\n\n", first))
    last = (stops[-1].end() if stops else 0)
    if last < max(100, int(budget * .48)):
        space = first.rfind(" ")
        last = space if space > 70 else budget
    return first[:last].rstrip(" \n،؛"), True


def prepare_caption(title: str, body: str, *, photo: bool) -> tuple[str, str, bool]:
    title = normalize_text(title)
    body = normalize_text(body)
    overhead = len(title) + len(FOOTER_TEXT) + 4
    max_len = CAPTION_LIMIT if photo else MESSAGE_LIMIT
    budget = max_len - overhead
    if budget < 100:
        raise ValueError("Headline/footer too long for Telegram")
    main, shortened = shorten_at_sentence(body, budget)
    plain = f"{title}\n\n{main}\n\n{FOOTER_TEXT}"
    if len(plain) > max_len:
        raise ValueError("Caption exceeds Telegram limits")
    formatted = f"<b>{html.escape(title)}</b>\n\n{html.escape(main)}\n\n{FOOTER_HTML}"
    return plain, formatted, shortened


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="downloaded_stories/manifest.json")
    parser.add_argument("--logo", default=str(DEFAULT_LOGO))
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--output", default=str(OUTPUT))
    parser.add_argument("--test-image", default="", help="For offline tests ONLY, overlay this local photo on a relevant news item")
    args = parser.parse_args()
    if args.count not in (1, 2):
        raise SystemExit("Stage 1 previews only one or two items")
    path = Path(args.manifest)
    if not path.is_file():
        raise SystemExit(f"Manifest not found: {path}")
    logo_file = Path(args.logo)
    if not logo_file.is_file():
        raise SystemExit(f"Official brand logo missing: {logo_file} (upload the real logo to assets/brand)")
    with Image.open(logo_file) as im:
        logo = im.convert("RGBA")
        if logo.width < 200 or logo.height < 100:
            raise SystemExit("Logo seems too small to watermark cleanly")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entries = manifest.get("articles") or []
    if not isinstance(entries, list) or not entries:
        raise SystemExit("No selected articles in manifest")
    selected = [a for a in entries if isinstance(a, dict) and a.get("topic") in TOPICS][:args.count]
    if not selected:
        raise SystemExit("No supported categories in manifest")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    previews: list[PreviewResult] = []
    for idx, item in enumerate(selected, 1):
        topic = item["topic"]
        title = item.get("headline", "").strip()
        body = item.get("story_text", "").strip()
        source_url = item.get("article_url_for_editor_only", "")
        status = item.get("image_review_status", "")
        if not title or not body:
            print(f"SKIP {idx}: no headline or article explanation")
            continue
        photo = None
        note = "no approved image"
        if args.test_image and idx == 1:
            with Image.open(args.test_image) as im:
                photo = im.convert("RGB")
            note = "LOCAL DEMO IMAGE, NOT FROM ARTICLE"
        elif source_url.startswith(("https://", "http://")):
            photo, note = fetch_relevant_photo(source_url, status)
        filename = None
        if photo is not None:
            filename = f"{idx:02d}_{topic}_branded.jpg"
            branded_photo(photo, logo).save(out / filename, "JPEG", quality=89, optimize=True)
        txt, html_caption, shorter = prepare_caption(title, body, photo=bool(photo))
        stem = f"{idx:02d}_{topic}"
        (out / f"{stem}_caption.txt").write_text(txt, encoding="utf-8")
        (out / f"{stem}_caption.html.txt").write_text(html_caption, encoding="utf-8")
        previews.append(PreviewResult(
            topic=topic, title=title, source_url=source_url,
            kind="PHOTO" if photo is not None else "TEXT_ONLY",
            image_status=note, photo_file=filename,
            caption_txt=f"{stem}_caption.txt", caption_html=f"{stem}_caption.html.txt",
            body_truncated=shorter,
        ))
        print(f"PREVIEW OK: {stem} kind={previews[-1].kind} img={note} shortened={shorter}")
    if not previews:
        raise SystemExit("No previews generated")
    (out / "preview_manifest.json").write_text(
        json.dumps({"status": "PREVIEW ONLY — NEVER SENT TO TELEGRAM", "posts": [asdict(x) for x in previews]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"SUCCESS: {len(previews)} Telegram preview post(s). NEVER SENDS TO TELEGRAM.")


if __name__ == "__main__":
    main()
