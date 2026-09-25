from __future__ import annotations

import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
GROUNDING_DIR = BASE_DIR / "grounding"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Only checked on the /webhook route (app.py) - validates the
# X-Telegram-Bot-Api-Secret-Token header Telegram sends when a secret_token
# was registered via setWebhook, so random internet POSTs to the public
# endpoint can't trigger (and bill) the pipeline. Optional for local polling.
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
# Drafting is long-form and voice-sensitive; defaults to the same model as
# triage, but can be pointed at a stronger tier independently if the flash
# model's voice-matching isn't good enough.
GEMINI_DRAFT_MODEL = os.environ.get("GEMINI_DRAFT_MODEL", GEMINI_MODEL)

NOTIFY_ON_REJECT = os.environ.get("NOTIFY_ON_REJECT", "true").lower() == "true"

# Vercel's filesystem is read-only except /tmp, and each invocation may land
# on a different instance, so this state is best-effort, not durable - fine
# for the calendar-balance rubric metric, which only needs a rough recent
# history, not a guaranteed one. tempfile.gettempdir() resolves to /tmp on
# Vercel and the OS temp dir locally, so the same code works in both places
# without ever writing into the (read-only, git-tracked) project directory.
_TMP_DIR = Path(tempfile.gettempdir())
OFFSET_FILE = _TMP_DIR / "skinstinct_pipeline_offset.txt"
HISTORY_FILE = _TMP_DIR / "skinstinct_pipeline_history.json"

REQUIRED = {
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "GEMINI_API_KEY": GEMINI_API_KEY,
}


def check_required():
    missing = [k for k, v in REQUIRED.items() if not v]
    if missing:
        raise SystemExit(
            f"Missing required env vars: {', '.join(missing)}. "
            f"Set them in .env (see .env.example)."
        )
