"""Acolad Telegram Stage 2: check bot channel permissions or explicitly send ONE approved post.

Inputs: Telegram Stage 1 artifact content (preview_manifest.json + captions/photos).
No automation, no scheduling, no modifications to the existing Telegram news bot.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests

API_TIMEOUT = 35
CAPTION_MAX = 1024
MESSAGE_MAX = 4096


def bot_call(token: str, method: str, *, data=None, files=None) -> dict:
    # Avoid printing request exception URLs; Telegram embeds sensitive bot token in URL.
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            data=data or {}, files=files, timeout=API_TIMEOUT,
        )
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise RuntimeError(f"Telegram {method}: connection error (token not logged)") from None
    if not response.ok or not payload.get("ok"):
        # Descriptions from Telegram are useful and normally contain no secret; cap output.
        reason = str(payload.get("description", f"HTTP {response.status_code}"))[:260]
        raise RuntimeError(f"Telegram {method}: {reason}")
    return payload["result"]


def preflight(token: str, channel: str) -> dict:
    bot = bot_call(token, "getMe")
    chat = bot_call(token, "getChat", data={"chat_id": channel})
    if chat.get("type") != "channel":
        raise RuntimeError("Target must be a Telegram CHANNEL, not a personal or group chat")
    member = bot_call(token, "getChatMember", data={"chat_id": channel, "user_id": bot["id"]})
    role = member.get("status", "unknown")
    can_post = role == "creator" or (role == "administrator" and member.get("can_post_messages") is True)
    print(f"BOT OK: @{bot.get('username', '')} (token hidden)")
    print(f"CHANNEL OK: {chat.get('title', '')} [{channel}]")
    print(f"BOT ROLE: {role}; can_post_messages={member.get('can_post_messages', 'not reported')}")
    if not can_post:
        raise RuntimeError("Bot is not confirmed as channel admin with Post Messages permission")
    return {"bot": bot.get("username", ""), "chat_title": chat.get("title", "")}


def validate_posts(root: Path) -> list[dict]:
    path = root / "preview_manifest.json"
    if not path.is_file():
        raise RuntimeError(f"Missing: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    items = obj.get("posts", [])
    if not items or not isinstance(items, list):
        raise RuntimeError("No posts in preview_manifest.json")
    validated = []
    for i, x in enumerate(items):
        if not isinstance(x, dict):
            raise RuntimeError(f"Malformed post #{i+1}")
        cap = x.get("caption_html", "")
        if not isinstance(cap, str) or Path(cap).name != cap:
            raise RuntimeError(f"Unsafe/missing caption filename at post #{i+1}")
        caption_path = root / cap
        if not caption_path.is_file():
            raise RuntimeError(f"Missing caption: {cap}")
        caption = caption_path.read_text(encoding="utf-8").strip()
        kind = x.get("kind")
        if kind not in ("PHOTO", "TEXT_ONLY"):
            raise RuntimeError(f"Unexpected post kind: {kind}")
        max_length = CAPTION_MAX if kind == "PHOTO" else MESSAGE_MAX
        if len(caption) > max_length + 200:  # HTML markup is excluded from Telegram's visible character limit.
            raise RuntimeError(f"Caption too long for {kind}: {cap}")
        photo = None
        if kind == "PHOTO":
            name = x.get("photo_file", "")
            if not isinstance(name, str) or Path(name).name != name:
                raise RuntimeError("Invalid photo filename")
            photo = root / name
            if not photo.is_file() or photo.stat().st_size < 3000:
                raise RuntimeError(f"Photo missing or invalid: {name}")
        validated.append({"kind": kind, "caption": caption, "photo": photo, "topic": x.get("topic", "")})
    return validated


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="downloaded_telegram")
    ap.add_argument("--mode", choices=["check", "send_one"], default="check")
    ap.add_argument("--approval", default="")
    args = ap.parse_args()
    token = os.getenv("BOT_TOKEN", "").strip()
    channel = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    if not token or not channel:
        raise SystemExit("Missing GitHub BOT_TOKEN secret or TELEGRAM_CHANNEL_ID variable")
    if not (channel.startswith("@") or channel.startswith("-100")):
        raise SystemExit("TELEGRAM_CHANNEL_ID must be @public_channel or numeric -100... channel ID")
    meta = preflight(token, channel)
    posts = validate_posts(Path(args.input))
    print(f"PREVIEW ARTIFACT VERIFIED: {len(posts)} post(s)")
    # Prefer the first photo to test the branded image as well as caption.
    chosen = next((p for p in posts if p["kind"] == "PHOTO"), posts[0])
    print(f"TEST POST: category={chosen['topic']} type={chosen['kind']}")
    if args.mode == "check":
        print("CHECK PASSED. No message was sent to channel.")
        return
    if args.approval != "SEND_ONE_TO_CHANNEL":
        raise SystemExit("To send ONE public post, type SEND_ONE_TO_CHANNEL as approval")
    data = {"chat_id": channel, "caption" if chosen["kind"] == "PHOTO" else "text": chosen["caption"], "parse_mode": "HTML"}
    if chosen["kind"] == "PHOTO":
        with chosen["photo"].open("rb") as f:
            result = bot_call(token, "sendPhoto", data=data, files={"photo": (chosen["photo"].name, f, "image/jpeg")})
    else:
        result = bot_call(token, "sendMessage", data=data)
    receipt = {"message_id": result.get("message_id"), "chat_id": result.get("chat", {}).get("id"),
               "channel": channel, "topic": chosen["topic"], "kind": chosen["kind"]}
    out = Path("telegram_stage2_receipt.json")
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"SENT ONE POST SUCCESSFULLY: id={receipt['message_id']} channel={channel}")
    print("STOP: do not rerun send_one; it will send another message.")


if __name__ == "__main__":
    main()
