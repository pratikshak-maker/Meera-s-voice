"""Vercel entrypoint. Telegram pushes each update here via webhook instead of
this process polling getUpdates - required because Vercel functions are
short-lived request handlers, not long-running processes (main.py's polling
loop can't run there at all).

All pipeline logic (triage -> news -> draft -> reply) is unchanged and lives
in pipeline.py; this file only swaps how an update arrives.
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, request

from config import REQUIRED, WEBHOOK_SECRET
from pipeline import process_update
from telegram_client import extract_fragment, send_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("app")

app = Flask(__name__)


@app.get("/")
def health():
    # Reports which required env vars are actually set on this deployment
    # (never the values) - Vercel needs a redeploy to pick up env var
    # changes on an existing deployment, so this is the fastest way to
    # confirm they landed without digging through function logs.
    status = {k: ("set" if v else "MISSING") for k, v in REQUIRED.items()}
    lines = ["Skinstinct content pipeline is running.", ""] + [
        f"{k}: {v}" for k, v in status.items()
    ]
    return "\n".join(lines), 200, {"Content-Type": "text/plain"}


@app.post("/webhook")
def webhook():
    missing = [k for k, v in REQUIRED.items() if not v]
    if missing:
        log.error("Missing required env vars: %s", missing)
        return jsonify({"ok": False, "error": f"Missing env vars: {missing}"}), 500

    if WEBHOOK_SECRET:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if header != WEBHOOK_SECRET:
            log.warning("Rejected webhook call with bad/missing secret token")
            return jsonify({"ok": False}), 401

    update = request.get_json(silent=True)
    if not update:
        return jsonify({"ok": False, "error": "no JSON body"}), 400

    try:
        process_update(update)
    except Exception as exc:
        # Always 200 back to Telegram regardless of our own failure - a
        # non-200 makes Telegram retry the same update repeatedly, which
        # would re-run (and re-bill) the Gemini calls for no benefit.
        log.exception("Failed to process update %s", update.get("update_id"))
        # A silent failure looks identical to "still processing" from the
        # Telegram side - reply with what broke so it's visible without
        # digging through Vercel's logs every time.
        try:
            fragment = extract_fragment(update)
            if fragment:
                send_message(
                    fragment["chat_id"],
                    f"Something went wrong processing that: {exc.__class__.__name__}: {exc}",
                )
        except Exception:
            log.exception("Also failed to send the error notice back to Telegram")

    return jsonify({"ok": True}), 200
