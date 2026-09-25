import requests
from config import TELEGRAM_BOT_TOKEN

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def get_updates(offset=None, timeout=30):
    params = {"timeout": timeout, "allowed_updates": ["message", "channel_post"]}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=timeout + 10)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"getUpdates failed: {data}")
    return data["result"]


def send_message(chat_id, text, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_file_path(file_id):
    resp = requests.get(f"{API_BASE}/getFile", params={"file_id": file_id}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"getFile failed: {data}")
    return data["result"]["file_path"]


def download_file(file_path):
    url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def extract_fragment(update):
    """Pull a normalized fragment dict out of a Telegram update, or None if unusable."""
    msg = update.get("message") or update.get("channel_post")
    if not msg:
        return None

    fragment_id = str(update["update_id"])
    timestamp = msg.get("date")
    chat_id = msg["chat"]["id"]

    if "text" in msg:
        return {
            "fragment_id": fragment_id,
            "timestamp": timestamp,
            "chat_id": chat_id,
            "kind": "text",
            "text": msg["text"],
        }

    if "voice" in msg:
        return {
            "fragment_id": fragment_id,
            "timestamp": timestamp,
            "chat_id": chat_id,
            "kind": "voice",
            "file_id": msg["voice"]["file_id"],
        }

    return None
