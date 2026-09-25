import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
GROUNDING_DIR = BASE_DIR / "grounding"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
# Drafting is long-form and voice-sensitive; defaults to the same model as
# triage, but can be pointed at a stronger tier independently if the flash
# model's voice-matching isn't good enough.
GEMINI_DRAFT_MODEL = os.environ.get("GEMINI_DRAFT_MODEL", GEMINI_MODEL)

NOTIFY_ON_REJECT = os.environ.get("NOTIFY_ON_REJECT", "true").lower() == "true"

OFFSET_FILE = BASE_DIR / "offset.txt"
HISTORY_FILE = BASE_DIR / "post_history.json"

REQUIRED = {
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    "GEMINI_API_KEY": GEMINI_API_KEY,
}


def check_required():
    missing = [k for k, v in REQUIRED.items() if not v]
    if missing:
        raise SystemExit(
            f"Missing required env vars: {', '.join(missing)}. "
            f"Set them in .env (see .env.example)."
        )
